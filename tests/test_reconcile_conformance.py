"""Conformance-suite exercise for views_frames_reconcile (Epic 11 S5, #136).

Runs ``assert_reconcile_contract`` across scenarios — the frozen oracle fixture,
synthetic probabilistic + single-sample frames, and an all-zero-country edge — and
proves the cm↔pgm mapping is **injected** (a permuted mapping changes the result, so it
is used, not fetched/ignored). numpy + views-frames only.
"""

from pathlib import Path

import numpy as np
import pytest

from views_frames import SpatialLevel
from views_frames_reconcile import ReconciliationModule
from views_frames_reconcile.conformance import assert_reconcile_contract
from views_frames_reconcile.frames import prediction_frame_from_arrays

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"


def _synthetic(seed, *, samples, all_zero_country=False):
    """Build a (cm, pgm, map_keys, map_vals) scenario: 2 countries, 1 month."""
    rng = np.random.default_rng(seed)
    month = 500
    # country 1 owns gids 1000-1002, country 2 owns gids 2000-2001
    layout = {1: [1000, 1001, 1002], 2: [2000, 2001]}
    cm_t, cm_u, cm_v, pg_t, pg_u, pg_v, mk, mv = [], [], [], [], [], [], [], []
    for c, gids in layout.items():
        cm_t.append(month)
        cm_u.append(c)
        cm_v.append(rng.gamma(2.0, 50.0, size=samples).astype(np.float32))
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


def test_contract_with_all_zero_country():
    # a country whose grid cells are all zero stays zero (documented edge), not summed.
    assert_reconcile_contract(*_synthetic(7, samples=32, all_zero_country=True))


def test_injected_mapping_is_honored():
    # Reconciling with a mapping that reassigns cells to the other country must change
    # the result — proof the mapping is the injected one, used not fetched/ignored.
    cm, pgm, mk, mv = _synthetic(3, samples=24)
    correct = ReconciliationModule(mk, mv).reconcile(cm, pgm)
    swapped_vals = np.where(mv == 1, 2, 1)  # flip every cell's country
    swapped = ReconciliationModule(mk, swapped_vals).reconcile(cm, pgm)
    assert not np.array_equal(correct.values, swapped.values)
