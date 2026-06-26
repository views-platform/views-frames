"""Parity: the numpy reconciler reproduces the views-reporting torch oracle.

Phase 2, slice 1. The fixture (``tests/fixtures/reconciliation_parity.npz``) was
captured from the *untouched* views-reporting ``ForecastReconciler`` by
``scripts/gen_reconciliation_parity_fixture.py``. This test needs neither torch
nor views-reporting — it proves the pure-numpy port matches the frozen oracle,
which is the gate for migrating reconciliation here (views-reporting issue #72).

Parity tolerance is relative (``rtol=1e-5``): the only expected difference is
float32 summation-order noise between torch and numpy; a genuinely different
algorithm diverges by O(value), not O(1e-5).
"""

from pathlib import Path

import numpy as np
import pytest

from views_frames_reconcile import reconcile_proportional

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "reconciliation_parity.npz"


@pytest.fixture(scope="module")
def parity_cases():
    data = np.load(_FIXTURE)
    labels = data["labels"]
    return [
        (str(labels[i]), data[f"grid_{i}"], data[f"country_{i}"], data[f"expected_{i}"])
        for i in range(int(data["n_cases"]))
    ]


class TestParityWithOracle:
    def test_reproduces_oracle_every_case(self, parity_cases):
        assert parity_cases, "fixture is empty — regenerate it"
        for label, grid, country, expected in parity_cases:
            arg_country = float(country) if grid.ndim == 1 else country
            got = reconcile_proportional(grid, arg_country)
            assert got.shape == expected.shape, f"shape drift in {label}"
            np.testing.assert_allclose(
                got, expected, rtol=1e-5, atol=1e-6,
                err_msg=f"parity drift in case {label}",
            )


class TestProperties:
    def test_sum_constraint_per_draw(self):
        rng = np.random.default_rng(0)
        grid = rng.integers(1, 100, (1000, 100)).astype(np.float32)
        country = grid.sum(axis=1) * np.float32(1.2)
        adjusted = reconcile_proportional(grid, country)
        np.testing.assert_allclose(adjusted.sum(axis=1), country, rtol=1e-4)

    def test_zeros_preserved(self):
        rng = np.random.default_rng(1)
        grid = rng.integers(1, 100, (200, 50)).astype(np.float32)
        grid[rng.random((200, 50)) < 0.4] = 0
        country = grid.sum(axis=1) * np.float32(1.5)
        adjusted = reconcile_proportional(grid, country)
        assert np.all(adjusted[grid == 0] == 0)

    def test_non_negative(self):
        rng = np.random.default_rng(2)
        grid = rng.standard_normal((100, 50)).astype(np.float32)  # has negatives
        country = np.abs(grid).sum(axis=1).astype(np.float32)
        assert reconcile_proportional(grid, country).min() >= 0

    def test_point_shape_sum_and_zero(self):
        grid = np.array([10.0, 20.0, 30.0, 0.0, 15.0], dtype=np.float32)
        adjusted = reconcile_proportional(grid, 100.0)
        assert adjusted.shape == grid.shape
        assert abs(float(adjusted.sum()) - 100.0) < 1e-2
        assert adjusted[3] == 0.0

    def test_sample_count_mismatch_raises(self):
        grid = np.zeros((100, 50), dtype=np.float32)
        country = np.zeros(200, dtype=np.float32)
        with pytest.raises(ValueError, match="Mismatch in sample count"):
            reconcile_proportional(grid, country)
