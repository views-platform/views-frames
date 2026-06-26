"""S3 (#35): fail-loud validation guards for reconciliation inputs.

Offline — builds frames from the committed S0 fixture; numpy + views-frames only.
"""

from pathlib import Path

import numpy as np
import pytest

from views_frames import SpatialLevel
from views_frames_reconcile.frames import prediction_frame_from_arrays
from views_frames_reconcile.validation import validate_reconciliation_inputs

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"


@pytest.fixture(scope="module")
def fix():
    return np.load(_FIX)


def _cm(fix, time=None, unit=None, vals=None):
    return prediction_frame_from_arrays(
        fix["cm_time"] if time is None else time,
        fix["cm_unit"] if unit is None else unit,
        fix["cm__pred_ged_sb"] if vals is None else vals,
        level=SpatialLevel.CM,
    )


def _pgm(fix):
    return prediction_frame_from_arrays(
        fix["pg_time"], fix["pg_unit"], fix["pg__pred_ged_sb"], level=SpatialLevel.PGM
    )


def _mk(fix):
    return np.stack([fix["pg_time"], fix["pg_unit"]], axis=1), fix["pg_country"]


class TestValidInputsPass:
    def test_no_raise_on_consistent_inputs(self, fix):
        mk, mv = _mk(fix)
        validate_reconciliation_inputs(_cm(fix), _pgm(fix), mk, mv)  # must not raise


class TestGuards:
    def test_wrong_level_raises(self, fix):
        mk, mv = _mk(fix)
        # pass the pgm frame where a cm frame is expected
        with pytest.raises(ValueError, match="SpatialLevel.CM"):
            validate_reconciliation_inputs(_pgm(fix), _pgm(fix), mk, mv)

    def test_grid_wrong_level_raises(self, fix):
        mk, mv = _mk(fix)
        # pass a cm frame where the pgm (grid) frame is expected
        with pytest.raises(ValueError, match="SpatialLevel.PGM"):
            validate_reconciliation_inputs(_cm(fix), _cm(fix), mk, mv)

    def test_sample_count_mismatch_raises(self, fix):
        mk, mv = _mk(fix)
        cm = _cm(fix, vals=fix["cm__pred_ged_sb"][:, :50])  # half the samples
        with pytest.raises(ValueError, match="sample-count mismatch"):
            validate_reconciliation_inputs(cm, _pgm(fix), mk, mv)

    def test_time_mismatch_raises(self, fix):
        mk, mv = _mk(fix)
        keep = fix["cm_time"] != 530  # drop a month from cm
        cm = _cm(fix, time=fix["cm_time"][keep], unit=fix["cm_unit"][keep],
                 vals=fix["cm__pred_ged_sb"][keep])
        with pytest.raises(ValueError, match="different time steps"):
            validate_reconciliation_inputs(cm, _pgm(fix), mk, mv)

    def test_missing_country_raises(self, fix):
        mk, mv = _mk(fix)
        keep = fix["cm_unit"] != fix["cm_unit"][0]  # drop a country from cm
        cm = _cm(fix, time=fix["cm_time"][keep], unit=fix["cm_unit"][keep],
                 vals=fix["cm__pred_ged_sb"][keep])
        with pytest.raises(ValueError, match="no country forecast"):
            validate_reconciliation_inputs(cm, _pgm(fix), mk, mv)
