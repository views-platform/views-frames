"""Transitional new-vs-old bit-identity gate (Epic 11 S4, #135).

Proves the relocated ``views_frames_reconcile`` is **bit-identical** to the old,
stranded ``views_postprocessing.reconciliation`` it was faithfully ported from — on
fresh random synthetic seeds (point + probabilistic + edge cases), at both the leaf
(``reconcile_proportional``) and the orchestrator (``ReconciliationModule.reconcile``).

One-shot / transitional: it needs **both** packages importable, so it runs locally (vpp
checked out adjacently, or ``VIEWS_POSTPROCESSING_SRC`` set) and is **skipped** in CI,
where vpp is absent. numpy + views-frames only (the old reconciler imports the same
``views_frames`` types).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_reconcile import ReconciliationModule, reconcile_proportional


def _import_old():
    """Import the old vpp reconciler, or skip the module if the sibling is absent."""
    candidates = [
        os.environ.get("VIEWS_POSTPROCESSING_SRC"),
        str(Path(__file__).resolve().parents[2] / "views-postprocessing"),
    ]
    for cand in candidates:
        if cand and (
            Path(cand) / "views_postprocessing" / "reconciliation" / "__init__.py"
        ).exists():
            if cand not in sys.path:
                sys.path.insert(0, cand)
            break
    return pytest.importorskip("views_postprocessing.reconciliation")


_OLD = _import_old()
_old_proportional = _OLD.reconcile_proportional
_OldModule = _OLD.ReconciliationModule


# ── leaf: reconcile_proportional ────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(60))
def test_proportional_bit_identical(seed):
    """Probabilistic (S, N) grids over zero-inflated draws + random country totals."""
    rng = np.random.default_rng(seed)
    s = int(rng.integers(1, 64))
    n = int(rng.integers(1, 40))
    grid = rng.gamma(0.4, 5.0, size=(s, n)).astype(np.float32)
    grid *= rng.random((s, n)) > 0.3  # zero-inflate
    country = rng.gamma(2.0, 50.0, size=s).astype(np.float32)
    new = reconcile_proportional(grid, country)
    old = _old_proportional(grid, country)
    assert np.array_equal(new, old), f"seed={seed} shape={grid.shape}"


@pytest.mark.parametrize("seed", range(40))
def test_proportional_point_bit_identical(seed):
    """Point (1-D) grids + scalar country total."""
    rng = np.random.default_rng(1000 + seed)
    n = int(rng.integers(1, 50))
    grid = (rng.gamma(0.5, 4.0, size=n) * (rng.random(n) > 0.25)).astype(np.float32)
    country = float(rng.gamma(2.0, 40.0))
    new = reconcile_proportional(grid, country)
    old = _old_proportional(grid, country)
    assert np.array_equal(new, old), f"seed={seed} n={n}"


@pytest.mark.parametrize(
    "grid, country",
    [
        (np.zeros(5, dtype=np.float32), 100.0),  # all-zero point
        (np.zeros((3, 5), dtype=np.float32), np.array([1.0, 2.0, 3.0])),  # zero prob
        (np.array([7.0], dtype=np.float32), 42.0),  # single cell
        (np.array([1.0, 2.0, 3.0], dtype=np.float32), 0.0),  # zero country total
        (np.array([[1.0, 0.0, 0.0]], dtype=np.float32), np.array([9.0])),  # one nonzero
        (np.full((2, 4), 1e7, dtype=np.float32), np.array([1.0, 2.0])),  # large mag
    ],
)
def test_proportional_edge_cases_bit_identical(grid, country):
    new = reconcile_proportional(grid, country)
    old = _old_proportional(grid, country)
    assert np.array_equal(new, old)


# ── orchestrator: ReconciliationModule.reconcile ─────────────────────────────


def _scenario(seed):
    """Build a synthetic (pgm, cm) frame pair + injected mapping for one scenario."""
    rng = np.random.default_rng(2000 + seed)
    n_countries = int(rng.integers(1, 6))
    months = np.arange(500, 500 + int(rng.integers(1, 4)))
    s = int(rng.integers(1, 40))
    # each country owns a random number of grid cells; cells globally unique gids
    gid = 1000
    cm_t, cm_u, cm_v, pg_t, pg_u, pg_v, mk, mv = [], [], [], [], [], [], [], []
    for m in months:
        for c in range(1, n_countries + 1):
            n_cells = int(rng.integers(1, 8))
            cells = np.arange(gid, gid + n_cells)
            gid += n_cells
            cm_t.append(m)
            cm_u.append(c)
            cm_v.append(rng.gamma(2.0, 50.0, size=s).astype(np.float32))
            for g in cells:
                pg_t.append(m)
                pg_u.append(int(g))
                pg_v.append(
                    (rng.gamma(0.4, 5.0, size=s) * (rng.random(s) > 0.3)).astype(
                        np.float32
                    )
                )
                mk.append((int(m), int(g)))
                mv.append(c)
    cm = PredictionFrame(
        np.asarray(cm_v, dtype=np.float32),
        SpatioTemporalIndex(
            np.asarray(cm_t, dtype=np.int64),
            np.asarray(cm_u, dtype=np.int32),
            SpatialLevel.CM,
        ),
    )
    pgm = PredictionFrame(
        np.asarray(pg_v, dtype=np.float32),
        SpatioTemporalIndex(
            np.asarray(pg_t, dtype=np.int64),
            np.asarray(pg_u, dtype=np.int32),
            SpatialLevel.PGM,
        ),
    )
    return cm, pgm, np.asarray(mk, dtype=np.int64), np.asarray(mv, dtype=np.int64)


@pytest.mark.parametrize("seed", range(30))
def test_module_reconcile_bit_identical(seed):
    cm, pgm, mk, mv = _scenario(seed)
    new = ReconciliationModule(mk, mv).reconcile(cm, pgm)
    old = _OldModule(mk, mv).reconcile(cm, pgm)
    assert np.array_equal(new.values, old.values), f"seed={seed}"
    assert new.index.level is old.index.level is SpatialLevel.PGM
