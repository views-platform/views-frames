"""Tests for views_frames_summarize.collapse (I2) — the generic sample-axis fold."""

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
from views_frames_summarize import collapse


def _index(n=3):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=SpatialLevel.PGM,
    )


def test_collapse_prediction_frame_mean():
    pf = PredictionFrame(
        np.array([[1.0, 3.0], [10.0, 20.0], [0.0, 0.0]], dtype=np.float32), _index(3)
    )
    out = collapse(pf, np.mean)
    assert isinstance(out, PredictionFrame)
    assert out.values.shape == (3, 1)
    assert np.allclose(out.values[:, 0], [2.0, 15.0, 0.0])
    assert out.is_sample is False
    assert np.array_equal(out.identifiers["time"], pf.identifiers["time"])


def test_collapse_accepts_any_axis_reducer():
    pf = PredictionFrame(np.array([[1.0, 2.0, 9.0]], dtype=np.float32), _index(1))
    assert np.allclose(collapse(pf, np.median).values[:, 0], [2.0])
    assert np.allclose(collapse(pf, np.max).values[:, 0], [9.0])


def test_collapse_feature_frame_preserves_features_and_names():
    ff = FeatureFrame(np.ones((3, 2, 4), dtype=np.float32), _index(3), ["a", "b"])
    out = collapse(ff, np.mean)
    assert isinstance(out, FeatureFrame)
    assert out.values.shape == (3, 2, 1)
    assert out.feature_names == ["a", "b"]


def test_collapse_target_frame_is_identity_shape():
    tf = TargetFrame(np.array([[5.0], [6.0], [7.0]], dtype=np.float32), _index(3))
    out = collapse(tf, np.mean)
    assert isinstance(out, TargetFrame)
    assert out.values.shape == (3, 1)
    assert np.allclose(out.values[:, 0], [5.0, 6.0, 7.0])


def test_collapse_bad_reducer_fails_loud():
    pf = PredictionFrame(np.ones((3, 2), dtype=np.float32), _index(3))
    # a reducer that drops rows -> rebuilt frame fails index/row validation
    with pytest.raises((ValueError, TypeError)):
        collapse(pf, lambda values, axis: values[:1, 0])
