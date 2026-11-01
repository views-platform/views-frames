"""Conformance-suite exercise for views_frames_reconcile (Epic 11 S5, #136).

Runs ``assert_reconcile_contract`` across scenarios — the frozen oracle fixture,
synthetic probabilistic + single-sample frames, and an all-zero-country edge — and
proves the cm↔pgm mapping is **injected** (a permuted mapping changes the result, so it
is used, not fetched/ignored). numpy + views-frames only.
"""

from pathlib import Path

import numpy as np
import pytest
from sparse_reconcile_case import sparse_case

from views_frames import PredictionFrame, SpatialLevel
from views_frames_reconcile import ReconciliationModule
from views_frames_reconcile import conformance as _conformance
from views_frames_reconcile.conformance import assert_reconcile_contract
from views_frames_reconcile.frames import prediction_frame_from_arrays
from views_frames_reconcile.grouping import reconcile_pgm_to_cm

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"


def _synthetic(seed, *, samples, all_zero_country=False, cm_samples=None):
    """Build a (cm, pgm, map_keys, map_vals) scenario: 2 countries, 1 month.

    ``cm_samples`` (default = ``samples``) lets the country frame carry a different
    sample count than the grid — set ``cm_samples=1`` for the point-broadcast case.
    """
    rng = np.random.default_rng(seed)
    month = 500
    n_cm = samples if cm_samples is None else cm_samples
    # country 1 owns gids 1000-1002, country 2 owns gids 2000-2001
    layout = {1: [1000, 1001, 1002], 2: [2000, 2001]}
    cm_t, cm_u, cm_v, pg_t, pg_u, pg_v, mk, mv = [], [], [], [], [], [], [], []
    for c, gids in layout.items():
        cm_t.append(month)
        cm_u.append(c)
        cm_v.append(rng.gamma(2.0, 50.0, size=n_cm).astype(np.float32))
        for g in gids:
            pg_t.append(month)
            pg_u.append(g)
            if all_zero_country and c == 2:
                cell = np.zeros(samples, dtype=np.float32)
            else:
                draws = rng.gamma(0.5, 5.0, size=samples) * (rng.random(samples) > 0.3)
                cell = draws.astype(np.float32)
            pg_v.append(cell)
            mk.append((month, g))
            mv.append(c)
    cm = prediction_frame_from_arrays(
        np.array(cm_t), np.array(cm_u), np.array(cm_v), level=SpatialLevel.CM
    )
    pgm = prediction_frame_from_arrays(
        np.array(pg_t), np.array(pg_u), np.array(pg_v), level=SpatialLevel.PGM
    )
    return cm, pgm, np.array(mk, dtype=np.int64), np.array(mv, dtype=np.int64)


def test_contract_on_oracle_fixture():
    fix = np.load(_FIX)
    cm = prediction_frame_from_arrays(
        fix["cm_time"], fix["cm_unit"], fix["cm__pred_ged_sb"], level=SpatialLevel.CM
    )
    pgm = prediction_frame_from_arrays(
        fix["pg_time"], fix["pg_unit"], fix["pg__pred_ged_sb"], level=SpatialLevel.PGM
    )
    mk = np.stack([fix["pg_time"], fix["pg_unit"]], axis=1)
    assert_reconcile_contract(cm, pgm, mk, fix["pg_country"])


@pytest.mark.parametrize("samples", [1, 16, 100])
def test_contract_on_synthetic(samples):
    assert_reconcile_contract(*_synthetic(samples, samples=samples))


def test_contract_with_all_zero_country_raises():
    # A country whose grid is zero in every draw while the country forecast is positive
    # has no donor pattern: until 3.0.0 it silently stayed zero (the mass was lost,
    # #283); now reconcile raises rather than return a grid short of the country
    # (ADR-030).
    with pytest.raises(ValueError, match="no donor pattern"):
        assert_reconcile_contract(*_synthetic(7, samples=32, all_zero_country=True))


def test_contract_on_point_country():
    # S1 (#143): a point country (sample_count == 1) vs a draws grid is broadcast inside
    # reconcile; the full contract must still hold (sum-to-country, zeros, non-negative,
    # draws kept).
    assert_reconcile_contract(*_synthetic(11, samples=64, cm_samples=1))


def test_injected_mapping_is_honored():
    # Reconciling with a mapping that reassigns cells to the other country must change
    # the result — proof the mapping is the injected one, used not fetched/ignored.
    cm, pgm, mk, mv = _synthetic(3, samples=24)
    correct = ReconciliationModule(mk, mv).reconcile(cm, pgm)
    swapped_vals = np.where(mv == 1, 2, 1)  # flip every cell's country
    swapped = ReconciliationModule(mk, swapped_vals).reconcile(cm, pgm)
    assert not np.array_equal(correct.values, swapped.values)


def test_conformance_rejects_a_non_conforming_reconciler(monkeypatch):
    # The conformance suite must have TEETH: every positive test above runs the REAL
    # (conforming) ReconciliationModule, so none exercises an assertion's raise-path
    # (100% branch coverage does not — cf. the leaf's register C-51 envelope negatives).
    # Substitute a deliberately broken reconciler (returns all -1.0 → violates the
    # non-negativity law) and prove assert_reconcile_contract fails loud on it.
    cm, pgm, mk, mv = _synthetic(5, samples=16)

    class _BadModule:
        def __init__(self, _mk, _mv):
            pass

        def reconcile(self, _cm, pgm_frame):
            bad = np.full_like(pgm_frame.values, -1.0)  # non-negativity-violating
            return PredictionFrame(bad, pgm_frame.index, pgm_frame.metadata)

    monkeypatch.setattr(_conformance, "ReconciliationModule", _BadModule)
    with pytest.raises(AssertionError, match="non-negative"):
        assert_reconcile_contract(cm, pgm, mk, mv)


def _group_rows(pgm, mk, mv):
    """``[(rows, (time, country))]`` per group, for building broken reconcilers."""
    cm_units = pgm.index.cross_level_align_arrays(mk, mv, SpatialLevel.CM).unit
    keys = np.stack([pgm.index.time, cm_units], axis=1)
    return [(np.all(keys == g, axis=1), g) for g in np.unique(keys, axis=0)]


def _cm_row(cm, g):
    return int(np.flatnonzero((cm.index.time == g[0]) & (cm.index.unit == g[1]))[0])


def _broken(monkeypatch, make_values):
    """Swap in a reconciler whose output is ``make_values(cm, pgm)``."""

    class _BadModule:
        def __init__(self, _mk, _mv):
            pass

        def reconcile(self, cm_frame, pgm_frame):
            vals = make_values(cm_frame, pgm_frame).astype(np.float32)
            return PredictionFrame(vals, pgm_frame.index, pgm_frame.metadata)

    monkeypatch.setattr(_conformance, "ReconciliationModule", _BadModule)


class TestEachLawHasTeeth:
    """ADR-030 restated laws 3 and 4; each must reject a reconciler that breaks it.

    Before 3.0.0 the sum-to-country law had no negative test, and weakening or deleting
    it left the suite green (baseline mutation audit, #285).
    """

    def test_rejects_the_2x_reconciler_that_drops_empty_draw_mass(self, monkeypatch):
        case = sparse_case(40)
        _broken(
            monkeypatch,
            lambda cm, pgm: (
                reconcile_pgm_to_cm(pgm, cm, case.map_keys, case.map_vals).values
            ),
        )
        with pytest.raises(AssertionError, match="Not equal to tolerance"):
            assert_reconcile_contract(case.cm, case.pgm, case.map_keys, case.map_vals)

    def test_rejects_a_reconciler_that_misses_the_total_by_a_little(self, monkeypatch):
        case = sparse_case(41)
        good = ReconciliationModule(case.map_keys, case.map_vals).reconcile(
            case.cm, case.pgm
        )
        _broken(monkeypatch, lambda cm, pgm: good.values * 1.01)
        with pytest.raises(AssertionError, match="Not equal to tolerance"):
            assert_reconcile_contract(case.cm, case.pgm, case.map_keys, case.map_vals)

    def test_rejects_mass_moved_into_a_zero_cell(self, monkeypatch):
        case = sparse_case(42)
        good = np.array(
            ReconciliationModule(case.map_keys, case.map_vals)
            .reconcile(case.cm, case.pgm)
            .values,
            dtype=np.float64,
        )

        def leak(_cm, pgm):
            vals = good.copy()
            grid_in = np.asarray(pgm.values)
            for rows, _ in _group_rows(pgm, case.map_keys, case.map_vals):
                block = vals[rows]
                for s in np.flatnonzero((grid_in[rows] > 0).any(axis=0)):
                    zero = np.flatnonzero(grid_in[rows][:, s] == 0)
                    if zero.size:  # move 10% of the draw's mass into a zero cell
                        moved = 0.1 * block[:, s].sum()
                        block[:, s] *= 0.9
                        block[zero[0], s] += moved
                        vals[rows] = block
                        return vals
            raise AssertionError("fixture has no draw with a zero cell")

        _broken(monkeypatch, leak)
        with pytest.raises(AssertionError, match="zeros preserved"):
            assert_reconcile_contract(case.cm, case.pgm, case.map_keys, case.map_vals)

    def test_rejects_a_fill_that_smears_mass_over_every_cell(self, monkeypatch):
        # the mean-pattern alternative ADR-030 rejected: conserves, but copies no donor
        case = sparse_case(43)
        good = np.array(
            ReconciliationModule(case.map_keys, case.map_vals)
            .reconcile(case.cm, case.pgm)
            .values,
            dtype=np.float64,
        )

        def smear(cm, pgm):
            vals = good.copy()
            grid_in = np.asarray(pgm.values)
            for rows, g in _group_rows(pgm, case.map_keys, case.map_vals):
                empty = ~(grid_in[rows] > 0).any(axis=0)
                country = np.asarray(cm.values)[_cm_row(cm, g)]
                block = vals[rows]
                block[:, empty] = country[empty] / rows.sum()
                vals[rows] = block
            return vals

        _broken(monkeypatch, smear)
        with pytest.raises(AssertionError, match="copy the pattern of a donor"):
            assert_reconcile_contract(case.cm, case.pgm, case.map_keys, case.map_vals)

    def test_rejects_mass_placed_where_no_draw_had_any(self, monkeypatch):
        # A group empty in every draw has no donor; placing mass there invents a
        # pattern. Every other group has no empty draw, so the 2.x output is correct
        # there and only the invented group can trip the suite.
        case = sparse_case(
            44,
            zero_share=0.5,
            empty_draw_share=0.0,
            no_donor=(2,),
            zero_country_share=0.0,
        )

        def invent(cm, pgm):
            vals = np.array(
                reconcile_pgm_to_cm(pgm, cm, case.map_keys, case.map_vals).values,
                dtype=np.float64,
            )
            for rows, g in _group_rows(pgm, case.map_keys, case.map_vals):
                if g[1] == 2:
                    vals[rows] = np.asarray(cm.values)[_cm_row(cm, g)] / rows.sum()
            return vals

        _broken(monkeypatch, invent)
        with pytest.raises(AssertionError, match="no draw had mass"):
            assert_reconcile_contract(case.cm, case.pgm, case.map_keys, case.map_vals)
