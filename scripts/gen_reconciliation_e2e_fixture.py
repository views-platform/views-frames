"""Capture the END-TO-END reconciliation oracle from the *untouched* views-reporting.

Story S0 (#32) of the reconciliation epic (#31). Slice 1 froze the leaf math;
this freezes the **whole pipeline**: build a realistic cm + pgm sample, run
views-reporting's `ReconciliationModule` fully OFFLINE (inject the country->grids
mapping so no viewser; patch WandB; CPU), and save (cm, pgm, per-grid country,
reconciled pgm) to a committed npz. The frames-native module (S1-S4) must then
reproduce `recon__*` exactly — the parity gate (S5).

The grouping is by VIEWS `country_id` (injected) — the only id system that lets
us match the oracle (the GAUL-vs-VIEWS choice is deferred to S7; see
`docs/reconciliation_migration.md`).

Run once, in the views_pipeline env (needs pipeline-core + views-reporting + torch):

    PYTHONPATH=.:/home/simon/Documents/scripts/views_platform/views-reporting \\
      /home/simon/anaconda3/envs/views_pipeline/bin/python \\
      scripts/gen_reconciliation_e2e_fixture.py

READS/RUNS the oracle; never edits views-reporting (parity).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch
from views_pipeline_core.data.handlers import CMDataset, PGMDataset
from views_reporting.reconciliation.reconciliation import ReconciliationModule

_OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "reconciliation_e2e_parity.npz"

# Realistic-but-small hierarchy: 5 countries of varying size, 3 months, 2 targets.
_GRIDS = {1: [100, 101], 2: [102, 103, 104], 3: [105, 106],
          4: [107, 108, 109, 110], 5: [111, 112]}
_MONTHS = [528, 529, 530]
_TARGETS = ["pred_ged_sb", "pred_ged_ns"]
_SAMPLES = 100


def _cm_df(rng):
    rows = [(m, c) for m in _MONTHS for c in _GRIDS]
    idx = pd.MultiIndex.from_tuples(rows, names=["month_id", "country_id"])
    # Country totals drawn INDEPENDENTLY of the grid (the realistic case).
    data = {t: [rng.gamma(3.0, 20.0, _SAMPLES).astype(np.float64) for _ in rows]
            for t in _TARGETS}
    return pd.DataFrame(data, index=idx)


def _pg_df(rng):
    rows = [(m, g) for m in _MONTHS for c in _GRIDS for g in _GRIDS[c]]
    idx = pd.MultiIndex.from_tuples(rows, names=["month_id", "priogrid_id"])
    data = {}
    for t in _TARGETS:
        cells = []
        for _ in rows:
            v = rng.gamma(2.0, 5.0, _SAMPLES).astype(np.float64)
            v[rng.random(_SAMPLES) < 0.3] = 0.0  # ~30% zeros, per cell
            cells.append(v)
        data[t] = cells
    return pd.DataFrame(data, index=idx)


def _stack(df, target):
    """(N, S) float32 from an object-dtype column of per-cell sample arrays."""
    return np.stack([np.asarray(v, dtype=np.float32) for v in df[target].to_numpy()])


def main() -> int:
    rng = np.random.default_rng(20260624)
    c_df, pg_df = _cm_df(rng), _pg_df(rng)
    grid_to_country = {g: c for c, gs in _GRIDS.items() for g in gs}

    c_ds = CMDataset(source=c_df)
    pg_ds = PGMDataset(source=pg_df)
    # Inject the country<->grid mapping so build_country_to_grids_cache skips viewser.
    pg_ds._country_to_grids_cache = {c: list(gs) for c, gs in _GRIDS.items()}
    pg_ds._entity_metadata_cache = pd.DataFrame(
        {"country_id": [grid_to_country[g] for (_, g) in pg_df.index]},
        index=pg_df.index,
    )

    with patch("views_reporting.reconciliation.reconciliation.WandBModule"):
        rm = ReconciliationModule(c_ds, pg_ds, wandb_notifications=False)
        rm._device = torch.device("cpu")
        reconciled = rm.reconcile(max_workers=2)

    # --- assemble the fixture ------------------------------------------------
    cm_rows = list(c_df.index)
    pg_rows = list(pg_df.index)
    out: dict[str, np.ndarray] = {
        "targets": np.array(_TARGETS),
        "cm_time": np.array([m for (m, _) in cm_rows], dtype=np.int64),
        "cm_unit": np.array([c for (_, c) in cm_rows], dtype=np.int64),
        "pg_time": np.array([m for (m, _) in pg_rows], dtype=np.int64),
        "pg_unit": np.array([g for (_, g) in pg_rows], dtype=np.int64),
        "pg_country": np.array([grid_to_country[g] for (_, g) in pg_rows], dtype=np.int64),
    }
    for t in _TARGETS:
        out[f"cm__{t}"] = _stack(c_df, t)
        out[f"pg__{t}"] = _stack(pg_df, t)
        out[f"recon__{t}"] = _stack(reconciled, t)

    # --- smoke check: the oracle conserves country totals per draw EXCEPT where a
    # country's grid cells are all-zero for that draw (no proportions to distribute
    # -> the cells stay zero; the algorithm's documented edge case). Verify exactly
    # that, so the fixture is trusted before S1-S5 build against it.
    worst_active = 0.0
    n_allzero = 0
    for t in _TARGETS:
        recon = {row: out[f"recon__{t}"][i] for i, row in enumerate(pg_rows)}
        pg_in = {row: out[f"pg__{t}"][i] for i, row in enumerate(pg_rows)}
        cm = {row: out[f"cm__{t}"][i] for i, row in enumerate(cm_rows)}
        for m in _MONTHS:
            for c, gs in _GRIDS.items():
                inp = np.stack([pg_in[(m, g)] for g in gs])
                allzero = (inp == 0).all(axis=0)  # per-draw: whole country zero
                grid_sum = np.stack([recon[(m, g)] for g in gs]).sum(axis=0)
                n_allzero += int(allzero.sum())
                assert (grid_sum[allzero] == 0).all(), "all-zero draw must stay zero"
                if (~allzero).any():
                    worst_active = max(worst_active, float(
                        np.max(np.abs(grid_sum[~allzero] - cm[(m, c)][~allzero]))))
    print(f"smoke: worst |grid_sum - country| on active draws = {worst_active:.3e} "
          f"(~0 expected); {n_allzero} all-zero country-draws left at zero "
          f"(the oracle's edge case, captured for parity)")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(_OUT, **out)
    print(f"wrote e2e parity fixture ({len(pg_rows)} grids x {_SAMPLES} samples x "
          f"{len(_TARGETS)} targets) -> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
