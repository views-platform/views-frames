"""🟥 Construction / validation failure modes (ADR-005 red-team blind spot).

Fills the fail-loud branches the v1.0 suite left untested: wrong-ndim frame
construction, row-count mismatch on FeatureFrame/TargetFrame, the `from_2d`
shim, and the `_validation` guards for malformed identifiers/values. ADR-005
§Enforcement: a known-untested failure mode is debt — these close it.
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import (
    FeatureFrame,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
    TargetFrame,
)
from views_frames._validation import validate_identifiers, validate_values


def _index(n):
    return SpatioTemporalIndex(
        np.arange(n, dtype=np.int64), np.arange(n, dtype=np.int32), SpatialLevel.PGM
    )


# --- frame construction: wrong ndim / row mismatch ---------------------------


def test_prediction_frame_rejects_3d():
    # validate_values passes (ndim >= 2); the frame's own ndim != 2 guard fires.
    with pytest.raises(ValueError, match="2D"):
        PredictionFrame(np.ones((3, 2, 2), dtype=np.float32), _index(3))


def test_feature_frame_row_mismatch_raises():
    with pytest.raises(ValueError, match="rows"):
        FeatureFrame(np.ones((2, 2, 1), dtype=np.float32), _index(3), ["a", "b"])


def test_target_frame_row_mismatch_raises():
    with pytest.raises(ValueError, match="rows"):
        TargetFrame(np.ones((2, 1), dtype=np.float32), _index(3))


def test_feature_frame_from_2d_rejects_non_2d():
    with pytest.raises(ValueError, match="from_2d expects a 2D"):
        FeatureFrame.from_2d(
            np.ones((3, 2, 1), dtype=np.float32), _index(3), ["a", "b"]
        )


# --- _validation guards ------------------------------------------------------


def test_validate_identifiers_non_array_raises_type_error():
    ids = {"time": [1, 2], "unit": np.array([1, 2], dtype=np.int64)}
    with pytest.raises(TypeError, match="numpy array"):
        validate_identifiers(ids, n_rows=2)  # type: ignore[arg-type]


def test_validate_identifiers_non_1d_raises_value_error():
    ids = {
        "time": np.array([[1], [2]], dtype=np.int64),  # 2-D
        "unit": np.array([1, 2], dtype=np.int64),
    }
    with pytest.raises(ValueError, match="1-D"):
        validate_identifiers(ids, n_rows=2)


def test_validate_values_non_array_raises_type_error():
    with pytest.raises(TypeError, match="numpy array"):
        validate_values([[1.0], [2.0]])  # type: ignore[arg-type]


# --- construction: `index` must actually be an index -------------------------
#
# Until 2.0.0 the constructors read exactly one attribute off `index` — `n_rows` —
# and a frame has one, so `PredictionFrame(values, another_frame)` constructed
# silently and the malformed frame then passed `assert_summarizer_contract`
# (falsify audit 2026-08-18; ADR-028).


def test_prediction_frame_rejects_a_frame_as_its_index():
    decoy = PredictionFrame(np.zeros((3, 4), dtype=np.float32), _index(3))
    with pytest.raises(TypeError, match="index must be a SpatioTemporalIndex"):
        PredictionFrame(np.zeros((3, 4), dtype=np.float32), decoy)


def test_feature_frame_rejects_a_frame_as_its_index():
    decoy = PredictionFrame(np.zeros((3, 4), dtype=np.float32), _index(3))
    with pytest.raises(TypeError, match="index must be a SpatioTemporalIndex"):
        FeatureFrame(np.zeros((3, 2, 4), dtype=np.float32), decoy, ["a", "b"])


def test_target_frame_rejects_a_frame_as_its_index():
    decoy = PredictionFrame(np.zeros((3, 4), dtype=np.float32), _index(3))
    with pytest.raises(TypeError, match="index must be a SpatioTemporalIndex"):
        TargetFrame(np.zeros((3, 1), dtype=np.float32), decoy)


def test_construction_rejects_any_object_that_merely_exposes_n_rows():
    """`n_rows` was the whole duck-type, which is why a frame slipped through."""

    class NotAnIndex:
        n_rows = 3

    with pytest.raises(TypeError, match="got NotAnIndex"):
        PredictionFrame(np.zeros((3, 4), dtype=np.float32), NotAnIndex())
