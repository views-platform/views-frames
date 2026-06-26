"""S1 (#33): cm/pgm `PredictionFrame` adapters build contract-valid frames.

Offline — consumes the committed S0 fixture; needs only numpy + views-frames.
"""

from pathlib import Path

import numpy as np
import pytest

from views_frames import PredictionFrame, SpatialLevel
from views_frames.conformance import assert_frame_contract
from views_frames_reconcile.frames import prediction_frame_from_arrays

_FIX = Path(__file__).resolve().parent / "fixtures" / "reconciliation_e2e_parity.npz"


@pytest.fixture(scope="module")
def fix():
    return np.load(_FIX)


class TestPgmAdapter:
    def test_satisfies_contract_and_identity(self, fix):
        pf = prediction_frame_from_arrays(
            fix["pg_time"], fix["pg_unit"], fix["pg__pred_ged_sb"], level=SpatialLevel.PGM
        )
        assert_frame_contract(pf)
        assert isinstance(pf, PredictionFrame)
        assert pf.index.level is SpatialLevel.PGM
        assert pf.n_rows == len(fix["pg_time"])
        assert pf.sample_count == fix["pg__pred_ged_sb"].shape[1]
        np.testing.assert_array_equal(pf.index.time, fix["pg_time"])
        np.testing.assert_array_equal(pf.index.unit, fix["pg_unit"])  # priogrid_gid


class TestCmAdapter:
    def test_satisfies_contract_and_country_units(self, fix):
        cf = prediction_frame_from_arrays(
            fix["cm_time"], fix["cm_unit"], fix["cm__pred_ged_sb"], level=SpatialLevel.CM
        )
        assert_frame_contract(cf)
        assert cf.index.level is SpatialLevel.CM
        assert cf.n_rows == len(fix["cm_time"])
        np.testing.assert_array_equal(cf.index.unit, fix["cm_unit"])  # country_id


class TestBoundaryBehaviour:
    def test_values_preserved_and_input_not_mutated(self, fix):
        vals = fix["pg__pred_ged_ns"].copy()
        before = vals.copy()
        pf = prediction_frame_from_arrays(
            fix["pg_time"], fix["pg_unit"], vals, level=SpatialLevel.PGM
        )
        np.testing.assert_array_equal(pf.values, vals.astype(np.float32))
        np.testing.assert_array_equal(vals, before)  # adapter did not mutate input

    def test_non_2d_values_raise(self, fix):
        with pytest.raises(ValueError, match="2-D"):
            prediction_frame_from_arrays(
                fix["pg_time"], fix["pg_unit"], fix["pg_unit"], level=SpatialLevel.PGM
            )

    def test_length_mismatch_raises(self, fix):
        with pytest.raises(ValueError, match="length N"):
            prediction_frame_from_arrays(
                fix["pg_time"][:-1], fix["pg_unit"], fix["pg__pred_ged_sb"],
                level=SpatialLevel.PGM,
            )
