"""Capture the reconciliation parity oracle from the *untouched* views-reporting.

Runs views-reporting's torch `ForecastReconciler.reconcile_forecast` over a
battery of inputs and freezes ``(grid, country, expected)`` to a committed npz,
so the numpy port (`views_frames_reconcile.reconcile_proportional`)
can be proven to reproduce it in CI **without torch or views-reporting**.

Run once, locally, from this repo's checkout (needs torch + views-reporting):

    PYTHONPATH=.:/home/simon/Documents/scripts/views_platform/views-reporting \\
      python scripts/gen_reconciliation_parity_fixture.py

This script READS/RUNS the oracle; it never edits views-reporting (parity).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from views_reporting.statistics import ForecastReconciler

_OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "reconciliation_parity.npz"

# views-reporting/tests/test_statistics.py _PROB_CASES / _POINT_CASES.
_PROB_CASES = [
    (1000, 100, 0.3, 1.2, "prob-basic"),
    (1000, 100, 1.0, 1.2, "prob-all-zeros"),
    (1000, 100, 0.2, 10, "prob-extreme-skew"),
    (1000, 100, 0.95, 1.2, "prob-sparse-95pct"),
    (1000, 100, 0.3, 10, "prob-extreme-scaling"),
    (1000, 100, 0.5, 1e-5, "prob-float-precision"),
    (1000, 100, 0.7, 5, "prob-mixed-zeros-large"),
    (500, 500, 0.5, 1.1, "prob-large-ish"),
]
_POINT_CASES = [
    (100, 0.3, 1.2, "point-basic"),
    (100, 1.0, 1.2, "point-all-zeros"),
    (100, 0.2, 10, "point-extreme-skew"),
    (100, 0.95, 1.2, "point-sparse-95pct"),
    (100, 0.3, 10, "point-extreme-scaling"),
    (100, 0.5, 1e-5, "point-float-precision"),
    (100, 0.7, 5, "point-mixed-zeros-large"),
]


def _prob_grid_country(num_samples, num_grid_cells, zero_fraction, scaling_factor):
    """Reproduce the test fixture's exact construction (country = grid.sum * k)."""
    torch.manual_seed(42)
    zero_mask = torch.rand((num_samples, num_grid_cells)) < zero_fraction
    grid = torch.randint(1, 100, (num_samples, num_grid_cells), dtype=torch.float32)
    grid[zero_mask] = 0
    country = grid.sum(dim=1) * scaling_factor
    return grid, country


def _point_grid_country(num_grid_cells, zero_fraction, scaling_factor):
    torch.manual_seed(42)
    zero_mask = torch.rand(num_grid_cells) < zero_fraction
    grid = torch.randint(1, 100, (num_grid_cells,), dtype=torch.float32)
    grid[zero_mask] = 0
    country = grid.sum().item() * scaling_factor
    return grid, country


def main() -> int:
    rec = ForecastReconciler(device="cpu")
    cases: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []

    for num_samples, n_cells, zf, sf, label in _PROB_CASES:
        grid, country = _prob_grid_country(num_samples, n_cells, zf, sf)
        adjusted = rec.reconcile_forecast(grid, country)
        cases.append((label, grid.numpy(), country.numpy(), adjusted.cpu().numpy()))

    for n_cells, zf, sf, label in _POINT_CASES:
        grid, country = _point_grid_country(n_cells, zf, sf)
        adjusted = rec.reconcile_forecast(grid, country)
        cases.append(
            (label, grid.numpy(), np.float32(country), adjusted.cpu().numpy())
        )

    # Extra: the realistic case the test suite never probes — country drawn
    # INDEPENDENTLY of the grid (separate model), so index-pairing matters.
    torch.manual_seed(7)
    grid = torch.randint(0, 80, (300, 50), dtype=torch.float32)
    country = torch.rand(300) * 5000.0  # independent of grid.sum
    adjusted = rec.reconcile_forecast(grid, country)
    cases.append(
        ("prob-independent-country", grid.numpy(), country.numpy(), adjusted.cpu().numpy())
    )

    # Extra: negatives present (the >0 mask drops them) and an all-zero draw.
    grid = torch.tensor(
        [[-5.0, 10.0, 0.0, 30.0], [0.0, 0.0, 0.0, 0.0], [2.0, -1.0, 4.0, 0.0]],
        dtype=torch.float32,
    )
    country = torch.tensor([100.0, 50.0, 12.0], dtype=torch.float32)
    adjusted = rec.reconcile_forecast(grid, country)
    cases.append(
        ("prob-negatives-and-zero-draw", grid.numpy(), country.numpy(), adjusted.cpu().numpy())
    )

    out: dict[str, np.ndarray] = {"n_cases": np.int64(len(cases))}
    labels = []
    for i, (label, g, c, e) in enumerate(cases):
        out[f"grid_{i}"] = g.astype(np.float32)
        out[f"country_{i}"] = np.asarray(c, dtype=np.float32)
        out[f"expected_{i}"] = e.astype(np.float32)
        labels.append(label)
    out["labels"] = np.array(labels)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(_OUT, **out)
    print(f"wrote {len(cases)} parity cases -> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
