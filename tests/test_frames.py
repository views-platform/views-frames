"""Tests for the frames (F1-F4): FrameMetadata + Prediction/Feature/TargetFrame.

Mines the behavioural contract from the sibling source classes (collapse semantics,
save/load round-trip, mmap, validation), adapted to the views-frames contract
(numpy-only validation; always-explicit trailing axis).
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import (
    FeatureFrame,
    FrameMetadata,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
    TargetFrame,
)


def _index(n=3, level=SpatialLevel.PGM):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=level,
    )


# --- F1: FrameMetadata -------------------------------------------------------


def test_metadata_to_from_dict_roundtrip():
    md = FrameMetadata(model="hydranet", run_type="calibration", seed=7)
    assert md.to_dict() == {"model": "hydranet", "run_type": "calibration", "seed": 7}
    assert FrameMetadata.from_dict(md.to_dict()) == md


def test_metadata_ignores_unknown_keys():
    md = FrameMetadata.from_dict({"model": "x", "unknown": 1})
    assert md.model == "x"


def test_metadata_is_frozen():
    md = FrameMetadata(model="x")
    with pytest.raises(AttributeError):
        md.model = "y"  # type: ignore[misc]


def test_metadata_generic_provenance_fields_default_none():
    # run_id / data_version are optional generic provenance (ADR-020, C-47 guard):
    # absent by default, so adding them is additive/MINOR and they omit from to_dict.
    md = FrameMetadata(model="x")
    assert md.run_id is None
    assert md.data_version is None
    assert "run_id" not in md.to_dict()
    assert "data_version" not in md.to_dict()


def test_metadata_provenance_roundtrip():
    md = FrameMetadata(run_id="abc123", data_version="v2024.1")
    assert md.to_dict() == {"run_id": "abc123", "data_version": "v2024.1"}
    assert FrameMetadata.from_dict(md.to_dict()) == md


# --- F2: PredictionFrame -----------------------------------------------------


def test_prediction_frame_construction_and_props():
    pf = PredictionFrame(np.ones((3, 5), dtype=np.float32), _index(3))
    assert pf.n_rows == 3
    assert pf.sample_count == 5
    assert pf.is_sample is True
    assert set(pf.identifiers) == {"time", "unit"}


def test_prediction_frame_coerces_float64():
    pf = PredictionFrame(np.ones((3, 2), dtype=np.float64), _index(3))
    assert pf.values.dtype == np.float32


def test_prediction_frame_bans_object_dtype():
    with pytest.raises(ValueError, match="object dtype"):
        PredictionFrame(np.array([[1], [2], [3]], dtype=object), _index(3))


def test_prediction_frame_row_mismatch_raises():
    with pytest.raises(ValueError, match="rows"):
        PredictionFrame(np.ones((2, 5), dtype=np.float32), _index(3))


# Sample-axis reduction (collapse/MAP/HDI) lives in views_frames_summarize (ADR-017);
# its behaviour is tested in tests/test_summarize_*.py, not here.


def test_prediction_frame_save_load_roundtrip(tmp_path):
    pf = PredictionFrame(
        np.arange(6, dtype=np.float32).reshape(3, 2),
        _index(3),
        FrameMetadata(model="m", seed=1),
    )
    pf.save(tmp_path)
    loaded = PredictionFrame.load(tmp_path)
    assert np.array_equal(loaded.values, pf.values)
    assert np.array_equal(loaded.identifiers["time"], pf.identifiers["time"])
    assert loaded.metadata == pf.metadata
    assert loaded.index.level is SpatialLevel.PGM


def test_prediction_frame_mmap_load(tmp_path):
    pf = PredictionFrame(np.ones((4, 3), dtype=np.float32), _index(4))
    pf.save(tmp_path)
    loaded = PredictionFrame.load(tmp_path, mmap=True)
    assert isinstance(loaded.values, np.memmap)
    assert np.array_equal(loaded.values, pf.values)


def test_prediction_frame_with_metadata_shares_buffer():
    pf = PredictionFrame(np.ones((3, 2), dtype=np.float32), _index(3))
    other = pf.with_metadata(FrameMetadata(model="x"))
    assert other.metadata.model == "x"
    assert np.shares_memory(pf.values, other.values)  # copy-vs-view (C-07)


# --- F3: FeatureFrame --------------------------------------------------------


def test_feature_frame_requires_3d():
    with pytest.raises(ValueError, match="3D"):
        FeatureFrame(np.ones((3, 2), dtype=np.float32), _index(3), ["a", "b"])


def test_feature_frame_from_2d_lifts_axis():
    ff = FeatureFrame.from_2d(np.ones((3, 2), dtype=np.float32), _index(3), ["a", "b"])
    assert ff.values.shape == (3, 2, 1)
    assert ff.n_features == 2
    assert ff.is_sample is False


def test_feature_frame_feature_names_length_checked():
    with pytest.raises(ValueError, match="feature_names"):
        FeatureFrame(np.ones((3, 2, 1), dtype=np.float32), _index(3), ["only_one"])


def test_feature_frame_save_load_preserves_names(tmp_path):
    ff = FeatureFrame(np.ones((3, 2, 4), dtype=np.float32), _index(3), ["a", "b"])
    ff.save(tmp_path)
    loaded = FeatureFrame.load(tmp_path)
    assert loaded.feature_names == ["a", "b"]
    assert loaded.values.shape == (3, 2, 4)


def test_feature_frame_has_no_from_grid():
    assert not hasattr(FeatureFrame, "from_grid")


# --- F4: TargetFrame ---------------------------------------------------------


def test_target_frame_shape_and_props():
    tf = TargetFrame(np.ones((3, 1), dtype=np.float32), _index(3))
    assert tf.sample_count == 1
    assert tf.is_sample is False


def test_target_frame_rejects_multi_sample():
    with pytest.raises(ValueError, match=r"\(N, 1\)"):
        TargetFrame(np.ones((3, 2), dtype=np.float32), _index(3))


def test_target_frame_rejects_1d():
    with pytest.raises(ValueError):
        TargetFrame(np.ones((3,), dtype=np.float32), _index(3))


def test_target_frame_save_load_roundtrip(tmp_path):
    tf = TargetFrame(np.arange(3, dtype=np.float32).reshape(3, 1), _index(3))
    tf.save(tmp_path)
    loaded = TargetFrame.load(tmp_path)
    assert np.array_equal(loaded.values, tf.values)
    assert loaded.is_sample is False
