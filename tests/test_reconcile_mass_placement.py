"""Reconciliation places every country's mass (#283, ADR-030).

On the first production run 2.9–7.3% of the country fatality mass was lost: a draw whose
grid is all zeros cannot be scaled up to a positive country value. The old suites never
built that input. These tests do, at realistic sparsity (``sparse_reconcile_case``), and
check mass, not just shapes.

The three ``TestMassPlacement`` tests fail on the 2.x reconciler (ADR-030 §Context) and
were held as strict ``xfail`` until S3 (#288) landed the donor fill.
"""

from __future__ import annotations

import numpy as np
import pytest
from sparse_reconcile_case import country_totals, group_sums, sparse_case

from views_frames_reconcile import ReconciliationModule


def _reconcile(case):
    return ReconciliationModule(case.map_keys, case.map_vals).reconcile(
        case.cm, case.pgm
    )


class TestSparseCaseBuilder:
    """The builder makes what the tests rely on, or the tests below are vacuous."""

    def test_grid_is_conflict_sparse(self):
        case = sparse_case(0, countries=6, cells=40, samples=128)
        zero_share = float((np.asarray(case.pgm.values) == 0).mean())
        assert 0.94 <= zero_share <= 0.99

    def test_has_empty_draws_with_donors(self):
        case = sparse_case(1)
        grid = group_sums(case, case.pgm.values)
        country = country_totals(case, grid.shape[1])
        empty = (country > 0) & (grid == 0)
        assert empty.sum() >= 20, "too few empty-grid draws to test anything"
        donors = (grid > 0).any(axis=1)
        assert donors[empty.any(axis=1)].all(), "empty draw, no donor"

    def test_has_zero_country_draws_with_grid_mass(self):
        # the other direction: the country says 0, the grid has mass and must be emptied
        case = sparse_case(2)
        grid = group_sums(case, case.pgm.values)
        country = country_totals(case, grid.shape[1])
        assert ((country == 0) & (grid > 0)).any()

    def test_no_donor_country_is_empty_in_every_draw(self):
        case = sparse_case(3, no_donor=(2,))
        grid = group_sums(case, case.pgm.values)
        cm_unit = np.asarray(case.cm.index.unit)[case.group_cm_row]
        assert (grid[cm_unit == 2] == 0).all()
        assert (grid[cm_unit != 2] > 0).any(axis=1).all()

    def test_point_country_and_single_draw_grid(self):
        assert sparse_case(4, cm_samples=1).cm.sample_count == 1
        assert sparse_case(5, samples=1).pgm.sample_count == 1


class TestMassPlacement:
    """What ADR-030 requires of the reconciled grid."""

    def test_total_mass_placed_equals_total_country_mass(self):
        case = sparse_case(10, countries=6, months=3, samples=128)
        out = _reconcile(case)
        placed = float(np.asarray(out.values, dtype=np.float64).sum())
        wanted = float(country_totals(case, out.sample_count).sum())
        assert placed == pytest.approx(wanted, rel=1e-5)

    def test_every_draw_sums_to_its_country(self):
        case = sparse_case(11, samples=64)
        out = _reconcile(case)
        np.testing.assert_allclose(
            group_sums(case, out.values),
            country_totals(case, out.sample_count),
            rtol=1e-4,
            atol=1e-3,
        )

    def test_filled_draw_is_a_scaled_copy_of_a_donor_from_its_group(self):
        case = sparse_case(12, samples=64)
        out = np.asarray(_reconcile(case).values, dtype=np.float64)
        grid_in = np.asarray(case.pgm.values, dtype=np.float64)
        country = country_totals(case, grid_in.shape[1])
        in_sums = group_sums(case, grid_in)
        checked = 0
        for g in range(in_sums.shape[0]):
            rows = case.group == g
            donors = grid_in[rows][:, in_sums[g] > 0]
            donor_shares = donors / donors.sum(axis=0)
            for s in np.nonzero((country[g] > 0) & (in_sums[g] == 0))[0]:
                col = out[rows, s]
                assert col.sum() > 0, f"group {g}, draw {s}: mass not placed"
                share = col / col.sum()
                match = np.isclose(donor_shares, share[:, None], atol=1e-6).all(axis=0)
                assert match.any(), f"group {g}, draw {s}: not a copy of any donor"
                checked += 1
        assert checked >= 20
