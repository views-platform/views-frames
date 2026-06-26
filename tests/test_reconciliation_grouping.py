"""S2 (#34): the grouping core reproduces the oracle's reconciled grid (parity).

Offline — builds cm/pgm frames from the committed S0 fixture, runs
`reconcile_pgm_to_cm`, and asserts it reproduces the oracle's `recon__*` (the
frozen views-reporting output captured in S0). Needs only numpy + views-frames.
"""

from pathlib import Path

import numpy as np
import pytest

from views_frames import SpatialLevel
from views_frames_reconcile.frames import prediction_frame_from_arrays
from views_frames_reconcile.grouping import reconcile_pgm_to_cm

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"
_TARGETS = ["pred_ged_sb", "pred_ged_ns"]


@pytest.fixture(scope="module")
def fix():
    return np.load(_FIX)


def _frames(fix, target):
    pgm = prediction_frame_from_arrays(
        fix["pg_time"], fix["pg_unit"], fix[f"pg__{target}"], level=SpatialLevel.PGM
    )
    cm = prediction_frame_from_arrays(
        fix["cm_time"], fix["cm_unit"], fix[f"cm__{target}"], level=SpatialLevel.CM
    )
    map_keys = np.stack([fix["pg_time"], fix["pg_unit"]], axis=1)
    map_vals = fix["pg_country"]
    return pgm, cm, map_keys, map_vals


class TestGroupingParity:
    @pytest.mark.parametrize("target", _TARGETS)
    def test_reproduces_oracle(self, fix, target):
        pgm, cm, mk, mv = _frames(fix, target)
        out = reconcile_pgm_to_cm(pgm, cm, mk, mv)
        np.testing.assert_allclose(
            out.values, fix[f"recon__{target}"], rtol=1e-5, atol=1e-6,
            err_msg=f"grouping core drifts from the oracle on {target}",
        )

    def test_de_mutated(self, fix):
        pgm, cm, mk, mv = _frames(fix, "pred_ged_sb")
        before = pgm.values.copy()
        out = reconcile_pgm_to_cm(pgm, cm, mk, mv)
        assert out is not pgm
        np.testing.assert_array_equal(pgm.values, before)  # input untouched


class TestGuards:
    def test_missing_country_forecast_raises(self, fix):
        # Drop a country from the cm frame -> its grid group has no total.
        keep = fix["cm_unit"] != fix["cm_unit"][0]
        cm = prediction_frame_from_arrays(
            fix["cm_time"][keep], fix["cm_unit"][keep],
            fix["cm__pred_ged_sb"][keep], level=SpatialLevel.CM,
        )
        pgm = prediction_frame_from_arrays(
            fix["pg_time"], fix["pg_unit"], fix["pg__pred_ged_sb"], level=SpatialLevel.PGM
        )
        mk = np.stack([fix["pg_time"], fix["pg_unit"]], axis=1)
        with pytest.raises(ValueError, match="no country forecast"):
            reconcile_pgm_to_cm(pgm, cm, mk, fix["pg_country"])
