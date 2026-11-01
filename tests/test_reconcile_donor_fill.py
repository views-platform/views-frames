"""Donor fill (ADR-030, #288): what the new pass does and does not change.

``test_reconcile_mass_placement.py`` checks the outcome (every draw sums to its
country, a filled draw copies a donor). This file pins the mechanics: the kernel,
reproducibility, independence from call chunking, that draws not filled are exactly the
2.x output, and the count reported on the result.
"""

from __future__ import annotations

import numpy as np
import pytest
from sparse_reconcile_case import country_totals, group_sums, sparse_case

from views_frames import SpatialLevel
from views_frames_reconcile import METHOD_DONOR_FILL, ReconciliationModule
from views_frames_reconcile.donor_fill import fill_empty_draws, fill_empty_grid_draws
from views_frames_reconcile.frames import prediction_frame_from_arrays
from views_frames_reconcile.grouping import reconcile_pgm_to_cm


def _module(case, seed=0):
    return ReconciliationModule(case.map_keys, case.map_vals, seed=seed)


def _filled_mask(case):
    """``(N_pg, S)``: the cells of draws that need filling (empty grid, country > 0)."""
    grid = group_sums(case, np.where(case.pgm.values > 0, case.pgm.values, 0))
    needs = (country_totals(case, grid.shape[1]) > 0) & (grid == 0)
    return needs[case.group]


def _month(frame, month, level):
    rows = np.asarray(frame.index.time) == month
    return prediction_frame_from_arrays(
        frame.index.time[rows], frame.index.unit[rows], frame.values[rows], level=level
    )


class TestKernel:
    def test_nothing_to_fill_returns_the_input_object(self):
        grid = np.array([[1.0, 0.0], [0.0, 2.0]], dtype=np.float32)
        out, n = fill_empty_draws(grid, np.array([3.0, 4.0]), np.random.default_rng(0))
        assert out is grid and n == 0

    def test_fills_only_empty_draws_with_a_positive_country(self):
        grid = np.array(
            [[1.0, 0.0, 3.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
            dtype=np.float32,
        )
        country = np.array([5.0, 7.0, 0.0, 1.0], dtype=np.float32)
        before = grid.copy()
        out, n = fill_empty_draws(grid, country, np.random.default_rng(0))
        assert n == 1
        assert any(np.array_equal(out[1], grid[d]) for d in (0, 3))  # copied a donor
        assert (out[2] == 0).all()  # country 0: nothing to place
        np.testing.assert_array_equal(out[[0, 3]], grid[[0, 3]])  # donors untouched
        np.testing.assert_array_equal(grid, before)  # input never modified

    def test_donor_choice_is_uniform_over_donors(self):
        grid = np.zeros((402, 2), dtype=np.float32)
        grid[0, 0] = 1.0  # donor A
        grid[1, 1] = 1.0  # donor B
        out, n = fill_empty_draws(grid, np.ones(402), np.random.default_rng(1))
        assert n == 400
        share_a = float((out[2:, 0] > 0).mean())
        assert 0.4 < share_a < 0.6


class TestReproducibility:
    def test_same_seed_same_output(self):
        case = sparse_case(20)
        a = _module(case, seed=7).reconcile(case.cm, case.pgm)
        b = _module(case, seed=7).reconcile(case.cm, case.pgm)
        np.testing.assert_array_equal(a.values, b.values)

    def test_another_seed_changes_only_filled_draws(self):
        case = sparse_case(21)
        a = _module(case, seed=0).reconcile(case.cm, case.pgm).values
        b = _module(case, seed=1).reconcile(case.cm, case.pgm).values
        filled = _filled_mask(case)
        np.testing.assert_array_equal(a[~filled], b[~filled])
        assert not np.array_equal(a[filled], b[filled])

    def test_month_by_month_equals_all_months_at_once(self):
        # pipeline-core reconciles one month per call; the result must not depend on it
        case = sparse_case(22, months=3)
        whole = _module(case).reconcile(case.cm, case.pgm)
        for month in (500, 501, 502):
            part = _module(case).reconcile(
                _month(case.cm, month, SpatialLevel.CM),
                _month(case.pgm, month, SpatialLevel.PGM),
            )
            rows = np.asarray(whole.index.time) == month
            np.testing.assert_array_equal(part.values, whole.values[rows])


def _twin_groups(times, units):
    """Two groups with identical grids and country values, so only the seed key differs.

    ``times``/``units`` are the two groups' ``(time, country)``. Each group has 5 cells
    and 200 draws: draws 0–99 are distinct donors, draws 100–199 are empty with a
    positive country value and must be filled.
    """
    rng = np.random.default_rng(0)
    donors = rng.gamma(1.0, 5.0, size=(5, 100)) * (rng.random((5, 100)) > 0.5)
    donors[0] += 1.0  # every donor has mass
    grid = np.concatenate([donors, np.zeros((5, 100))], axis=1).astype(np.float32)
    pg_t, pg_u, pg_v, mk, mv = [], [], [], [], []
    for t, c in zip(times, units, strict=True):
        for k in range(5):
            pg_t.append(t)
            pg_u.append(c * 1000 + k)
            pg_v.append(grid[k])
            mk.append((t, c * 1000 + k))
            mv.append(c)
    cm = prediction_frame_from_arrays(
        np.array(times), np.array(units), np.full((2, 200), 50.0), level=SpatialLevel.CM
    )
    pgm = prediction_frame_from_arrays(
        np.array(pg_t), np.array(pg_u), np.array(pg_v), level=SpatialLevel.PGM
    )
    out = ReconciliationModule(np.array(mk), np.array(mv)).reconcile(cm, pgm)
    return np.asarray(out.values)[:5, 100:], np.asarray(out.values)[5:, 100:]


class TestGroupsDrawIndependently:
    """Each (time, country) group has its own generator (ADR-030 §Decision 4).

    A seed key missing ``time`` or ``country`` stays reproducible and chunk-independent,
    so the tests above miss it; but identical groups would then pick identical donors,
    so filled draws would be correlated across months or countries (S5 audit, #289).
    """

    def test_same_country_in_two_months_picks_different_donors(self):
        a, b = _twin_groups([500, 501], [7, 7])
        assert not np.array_equal(a, b)

    def test_two_countries_in_one_month_pick_different_donors(self):
        a, b = _twin_groups([500, 500], [7, 8])
        assert not np.array_equal(a, b)


class TestUnchangedOutsideFilledDraws:
    def test_draws_not_filled_are_bit_identical_to_2x(self):
        case = sparse_case(23, samples=96)
        new = _module(case).reconcile(case.cm, case.pgm).values
        old = reconcile_pgm_to_cm(
            case.pgm, case.cm, case.map_keys, case.map_vals
        ).values
        keep = ~_filled_mask(case)
        np.testing.assert_array_equal(new[keep], old[keep])
        assert (old[~keep] == 0).all()  # where 2.x lost the mass

    def test_nothing_to_fill_returns_the_same_frame(self):
        case = sparse_case(24, empty_draw_share=0.0, zero_share=0.0)
        frame, n = fill_empty_grid_draws(
            case.pgm, case.cm, case.map_keys, case.map_vals, 0
        )
        assert frame is case.pgm and n == 0

    def test_point_country_is_broadcast_before_filling(self):
        case = sparse_case(25, cm_samples=1)
        out = _module(case).reconcile(case.cm, case.pgm)
        np.testing.assert_allclose(
            group_sums(case, out.values),
            country_totals(case, out.sample_count),
            rtol=1e-4,
            atol=1e-3,
        )


class TestResult:
    def test_reports_method_and_filled_count(self):
        case = sparse_case(26)
        result = _module(case).reconcile_result(case.cm, case.pgm)
        assert result.method == METHOD_DONOR_FILL
        grid = group_sums(case, np.where(case.pgm.values > 0, case.pgm.values, 0))
        needs = (country_totals(case, grid.shape[1]) > 0) & (grid == 0)
        assert result.filled_draws == int(needs.sum()) > 0

    @pytest.mark.parametrize("seed", [-1, 1.5, True, "0", None])
    def test_seed_must_be_a_non_negative_int(self, seed):
        case = sparse_case(27)
        with pytest.raises(ValueError, match="seed must be a non-negative int"):
            ReconciliationModule(case.map_keys, case.map_vals, seed=seed)

    def test_numpy_int_seed_is_accepted(self):
        case = sparse_case(28)
        ReconciliationModule(case.map_keys, case.map_vals, seed=np.int64(3))


class TestNoDonor:
    """ADR-030 §Decision 5: mass with nowhere to go raises, it is never dropped."""

    def test_kernel_raises_when_no_draw_has_grid_mass(self):
        grid = np.zeros((3, 4), dtype=np.float32)
        with pytest.raises(ValueError, match=r"2 of 3 draw\(s\).*no donor pattern"):
            fill_empty_draws(grid, np.array([1.0, 0.0, 2.0]), np.random.default_rng(0))

    def test_group_with_no_donor_raises_naming_time_and_country(self):
        case = sparse_case(30, no_donor=(3,), zero_country_share=0.0)
        with pytest.raises(ValueError, match=r"time 500, country 3: .*no donor"):
            _module(case).reconcile(case.cm, case.pgm)

    def test_single_draw_grid_with_empty_country_raises(self):
        case = sparse_case(31, samples=1, no_donor=(2,), zero_country_share=0.0)
        with pytest.raises(ValueError, match=r"country 2: .*1 of 1 draw"):
            _module(case).reconcile(case.cm, case.pgm)

    def test_point_country_against_an_empty_group_raises(self):
        case = sparse_case(32, cm_samples=1, no_donor=(1,), zero_country_share=0.0)
        with pytest.raises(ValueError, match=r"country 1: .*no donor"):
            _module(case).reconcile(case.cm, case.pgm)

    def test_zero_country_with_empty_grid_is_not_an_error(self):
        # nothing to place: the empty grid is already the right answer
        case = sparse_case(33, no_donor=(2,), zero_country_share=1.0)
        out = _module(case).reconcile(case.cm, case.pgm)
        assert (np.asarray(out.values) == 0).all()

    def test_raises_without_touching_the_input(self):
        case = sparse_case(34, no_donor=(4,), zero_country_share=0.0)
        before = np.array(case.pgm.values, copy=True)
        with pytest.raises(ValueError):
            _module(case).reconcile(case.cm, case.pgm)
        np.testing.assert_array_equal(case.pgm.values, before)
