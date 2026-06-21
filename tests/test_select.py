"""F12: frame-level row selection — `select(positions|mask)` and `reindex(other)`.

Closes the round-02 consumer gap (faoapi/postprocessing subset by time/entity on
every request): the index returned *positions*; nothing applied them to a frame's
values + identifiers and returned a new frame.
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


def _index(times, units, level=SpatialLevel.PGM):
    return SpatioTemporalIndex(
        np.array(times, dtype=np.int64), np.array(units, dtype=np.int32), level
    )


def _pf(times, units, s=3, meta=None):
    idx = _index(times, units)
    values = np.arange(len(times) * s, dtype=np.float32).reshape(len(times), s)
    return PredictionFrame(values, idx, meta)


# --- index.select primitive --------------------------------------------------


def test_index_select_positions_reorders():
    idx = _index([1, 1, 2], [10, 11, 10])
    out = idx.select(np.array([2, 0], dtype=np.intp))
    assert np.array_equal(out.time, [2, 1])
    assert np.array_equal(out.unit, [10, 10])
    assert out.level is SpatialLevel.PGM


def test_index_select_boolean_mask_filters():
    idx = _index([1, 1, 2], [10, 11, 10])
    out = idx.select(np.array([True, False, True]))
    assert np.array_equal(out.time, [1, 2])
    assert np.array_equal(out.unit, [10, 10])


# --- frame.select ------------------------------------------------------------


def test_select_positions_reorders_values_and_index():
    pf = _pf([1, 1, 2], [10, 11, 10])
    out = pf.select(np.array([2, 0], dtype=np.intp))
    assert out.n_rows == 2
    assert np.array_equal(out.values, pf.values[[2, 0]])
    assert np.array_equal(out.identifiers["time"], [2, 1])


def test_select_boolean_mask_filters():
    pf = _pf([1, 1, 2], [10, 11, 10])
    out = pf.select(np.array([True, False, True]))
    assert out.n_rows == 2
    assert np.array_equal(out.values, pf.values[[0, 2]])


def test_select_empty_is_allowed():
    pf = _pf([1, 1, 2], [10, 11, 10])
    out = pf.select(np.array([False, False, False]))
    assert out.n_rows == 0
    assert out.values.shape == (0, 3)


def test_select_copies_does_not_share_buffer():
    pf = _pf([1, 2], [10, 10])
    out = pf.select(np.array([0, 1], dtype=np.intp))
    assert not np.shares_memory(out.values, pf.values)


def test_select_preserves_metadata():
    meta = FrameMetadata(model="m", run_type="forecast")
    pf = _pf([1, 2], [10, 10], meta=meta)
    out = pf.select(np.array([1], dtype=np.intp))
    assert out.metadata == meta


def test_feature_frame_select_preserves_feature_names():
    idx = _index([1, 2], [10, 10])
    ff = FeatureFrame(np.ones((2, 2, 4), dtype=np.float32), idx, ["a", "b"])
    out = ff.select(np.array([1], dtype=np.intp))
    assert out.feature_names == ["a", "b"]
    assert out.values.shape == (1, 2, 4)


def test_target_frame_select():
    idx = _index([1, 2, 3], [10, 10, 10])
    tf = TargetFrame(np.array([[1.0], [2.0], [3.0]], dtype=np.float32), idx)
    out = tf.select(np.array([True, False, True]))
    assert np.array_equal(out.values, [[1.0], [3.0]])


# --- frame.reindex(other) ----------------------------------------------------


def test_reindex_aligns_to_other_when_superset():
    pf = _pf([1, 1, 2], [10, 11, 10])  # 3 rows
    other = _index([2, 1], [10, 11])  # a subset, reordered
    out = pf.reindex(other)
    assert out.n_rows == 2
    assert np.array_equal(out.identifiers["time"], [2, 1])
    assert np.array_equal(out.identifiers["unit"], [10, 11])
    # row (2,10) was pf row 2; row (1,11) was pf row 1
    assert np.array_equal(out.values, pf.values[[2, 1]])


def test_reindex_non_superset_raises():
    pf = _pf([1, 2], [10, 10])
    other = _index([1, 3], [10, 10])  # (3,10) absent in pf
    with pytest.raises(ValueError, match="superset"):
        pf.reindex(other)


def test_reindex_round_trips_with_self():
    pf = _pf([1, 2, 3], [10, 10, 10])
    out = pf.reindex(pf.index)
    assert np.array_equal(out.values, pf.values)
    assert np.array_equal(out.identifiers["time"], pf.identifiers["time"])
