"""Dense-grid fill (ADR-026): `SpatioTemporalIndex.cartesian` + `reindex_fill`.

Closes the faoapi ingestion gap (#203 — "views-frames has no fill primitive"):
materialize a complete (time × unit) grid from a sparse frame without pandas.
The fill rides the existing same-level join (`searchsorted` returns -1 for
absent rows) and owns the -1 sentinel once — a consumer hand-rolling
`values[pos]` would silently pick the *last* row for absent cells.
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
from views_frames.conformance import assert_reindex_fill_law


def _index(times, units, level=SpatialLevel.PGM):
    return SpatioTemporalIndex(
        np.array(times, dtype=np.int64), np.array(units, dtype=np.int32), level
    )


def _pf(times, units, s=3, meta=None):
    idx = _index(times, units)
    values = np.arange(len(times) * s, dtype=np.float32).reshape(len(times), s)
    return PredictionFrame(values, idx, meta)


def _times(*vals):
    return np.array(vals, dtype=np.int64)


def _units(*vals):
    return np.array(vals, dtype=np.int32)


# --- SpatioTemporalIndex.cartesian -------------------------------------------


def test_cartesian_product_is_time_major():
    idx = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11, 12), SpatialLevel.PGM
    )
    assert idx.n_rows == 6
    assert np.array_equal(idx.time, [1, 1, 1, 2, 2, 2])
    assert np.array_equal(idx.unit, [10, 11, 12, 10, 11, 12])
    assert idx.level is SpatialLevel.PGM


def test_cartesian_preserves_input_dtypes():
    idx = SpatioTemporalIndex.cartesian(_times(1), _units(10), SpatialLevel.CM)
    assert idx.time.dtype == np.int64
    assert idx.unit.dtype == np.int32


def test_cartesian_rows_are_unique():
    idx = SpatioTemporalIndex.cartesian(
        _times(1, 2, 3), _units(10, 11), SpatialLevel.PGM
    )
    assert idx.has_unique_rows()


def test_cartesian_empty_times_yields_empty_index():
    idx = SpatioTemporalIndex.cartesian(
        np.array([], dtype=np.int64), _units(10, 11), SpatialLevel.PGM
    )
    assert idx.n_rows == 0


def test_cartesian_non_array_raises_type_error():
    with pytest.raises(TypeError, match="times must be a numpy array"):
        SpatioTemporalIndex.cartesian([1, 2], _units(10), SpatialLevel.PGM)


def test_cartesian_non_integer_dtype_raises_type_error():
    with pytest.raises(TypeError, match="units must be an integer dtype"):
        SpatioTemporalIndex.cartesian(_times(1), np.array([10.0]), SpatialLevel.PGM)


def test_cartesian_non_1d_raises():
    with pytest.raises(ValueError, match="times must be 1-D"):
        SpatioTemporalIndex.cartesian(
            np.array([[1, 2]], dtype=np.int64), _units(10), SpatialLevel.PGM
        )


def test_cartesian_duplicate_times_raise():
    # a duplicated product input manufactures duplicate rows → undefined joins
    # (register C-21); always a caller bug, so it fails loud.
    with pytest.raises(ValueError, match="times contains duplicate"):
        SpatioTemporalIndex.cartesian(_times(1, 1), _units(10), SpatialLevel.PGM)


def test_cartesian_duplicate_units_raise():
    with pytest.raises(ValueError, match="units contains duplicate"):
        SpatioTemporalIndex.cartesian(_times(1), _units(10, 10), SpatialLevel.PGM)


def test_cartesian_bad_level_raises_type_error():
    with pytest.raises(TypeError, match="level must be a SpatialLevel"):
        SpatioTemporalIndex.cartesian(_times(1), _units(10), "pgm")


# --- frame.reindex_fill: sparse → dense --------------------------------------


def test_reindex_fill_sparse_to_dense():
    # rows (1,10) and (2,11) exist; the dense 2×2 grid gains (1,11) and (2,10).
    frame = _pf([1, 2], [10, 11])
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )
    filled = frame.reindex_fill(target, fill_value=0.0)
    assert filled.n_rows == 4
    # present rows bit-exact
    assert np.array_equal(filled.values[0], frame.values[0])  # (1,10)
    assert np.array_equal(filled.values[3], frame.values[1])  # (2,11)
    # absent rows filled
    assert np.array_equal(filled.values[1], np.zeros(3, dtype=np.float32))
    assert np.array_equal(filled.values[2], np.zeros(3, dtype=np.float32))
    assert filled.values.dtype == np.float32


def test_reindex_fill_result_index_is_target():
    frame = _pf([1], [10])
    target = _index([1, 2], [10, 10])
    filled = frame.reindex_fill(target, fill_value=0.0)
    assert filled.index is target  # immutable, shared — zero-copy identity


def test_reindex_fill_nan_fill_is_legal():
    frame = _pf([1], [10])
    target = _index([1, 2], [10, 10])
    filled = frame.reindex_fill(target, fill_value=float("nan"))
    assert np.array_equal(filled.values[0], frame.values[0])
    assert np.isnan(filled.values[1]).all()


def test_reindex_fill_superset_equals_reindex():
    # idempotence: with every target row present, filling adds nothing.
    frame = _pf([1, 2, 3], [10, 10, 10])
    target = _index([3, 1], [10, 10])
    filled = frame.reindex_fill(target, fill_value=-99.0)
    assert np.array_equal(filled.values, frame.reindex(target).values)


def test_reindex_fill_empty_self_fills_everything():
    frame = _pf([], [])
    target = _index([1, 2], [10, 10])
    filled = frame.reindex_fill(target, fill_value=7.0)
    assert np.array_equal(filled.values, np.full((2, 3), 7.0, dtype=np.float32))


def test_reindex_fill_empty_target_yields_empty_frame():
    frame = _pf([1], [10])
    filled = frame.reindex_fill(_index([], []), fill_value=0.0)
    assert filled.n_rows == 0
    assert filled.values.shape == (0, 3)


def test_reindex_fill_duplicate_target_rows_repeat():
    # cross_level_align legitimately produces duplicate-row targets; positions
    # simply repeat.
    frame = _pf([1], [10])
    target = _index([1, 1], [10, 10])
    filled = frame.reindex_fill(target, fill_value=0.0)
    assert np.array_equal(filled.values[0], filled.values[1])


def test_reindex_fill_preserves_metadata():
    meta = FrameMetadata(model="m")
    frame = _pf([1], [10], meta=meta)
    filled = frame.reindex_fill(_index([1, 2], [10, 10]), fill_value=0.0)
    assert filled.metadata.model == "m"


def test_reindex_fill_level_mismatch_raises():
    frame = _pf([1], [10])
    with pytest.raises(ValueError, match="same-level"):
        frame.reindex_fill(_index([1], [10], level=SpatialLevel.CM), fill_value=0.0)


def test_feature_frame_reindex_fill():
    idx = _index([1, 2], [10, 11])
    values = np.arange(2 * 2 * 3, dtype=np.float32).reshape(2, 2, 3)
    frame = FeatureFrame(values, idx, ["a", "b"])
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )
    filled = frame.reindex_fill(target, fill_value=0.0)
    assert filled.values.shape == (4, 2, 3)
    assert filled.feature_names == ["a", "b"]
    assert np.array_equal(filled.values[0], values[0])
    assert np.array_equal(filled.values[1], np.zeros((2, 3), dtype=np.float32))


def test_target_frame_reindex_fill():
    idx = _index([1, 2], [10, 11])
    frame = TargetFrame(np.array([[1.0], [2.0]], dtype=np.float32), idx)
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )
    filled = frame.reindex_fill(target, fill_value=0.0)
    assert filled.values.shape == (4, 1)
    assert np.array_equal(
        filled.values[:, 0], np.array([1.0, 0.0, 0.0, 2.0], dtype=np.float32)
    )


# --- the published conformance law -------------------------------------------


def test_fill_law_holds_for_builtin_frames():
    frames = [
        _pf([1, 2], [10, 11]),
        FeatureFrame(
            np.ones((2, 2, 3), dtype=np.float32), _index([1, 2], [10, 11]), ["a", "b"]
        ),
        TargetFrame(np.ones((2, 1), dtype=np.float32), _index([1, 2], [10, 11])),
    ]
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )
    for frame in frames:
        assert_reindex_fill_law(frame, target, 0.0)


def test_fill_law_holds_with_nan_fill():
    frame = _pf([1, 2], [10, 11])
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )
    assert_reindex_fill_law(frame, target, float("nan"))


def test_fill_law_covers_the_superset_degeneracy():
    # every target row present → the reindex-equality arm of the law runs.
    frame = _pf([1, 2], [10, 10])
    assert_reindex_fill_law(frame, _index([2], [10]), 0.0)


# The law's job is to REJECT a lying implementation; each structural reject gets a
# direct adversarial test (register C-51 — branch coverage does not exercise an
# `assert`'s raise-path).


class _Lying:
    """Wraps a real frame but corrupts what `reindex_fill` returns."""

    def __init__(self, frame, corrupt):
        self._frame = frame
        self._corrupt = corrupt
        self.index = frame.index
        self.values = frame.values

    def reindex_fill(self, other, *, fill_value):
        return self._corrupt(self._frame, other, fill_value)

    def reindex(self, other):
        return self._frame.reindex(other)


def test_fill_law_catches_wrong_fill_value():
    frame = _pf([1, 2], [10, 11])
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )
    lying = _Lying(frame, lambda f, o, fv: f.reindex_fill(o, fill_value=fv + 1.0))
    with pytest.raises(AssertionError, match="absent row"):
        assert_reindex_fill_law(lying, target, 0.0)


def test_fill_law_catches_corrupted_present_rows():
    frame = _pf([1, 2], [10, 11])
    target = SpatioTemporalIndex.cartesian(
        _times(1, 2), _units(10, 11), SpatialLevel.PGM
    )

    def corrupt(f, o, fv):
        good = f.reindex_fill(o, fill_value=fv)
        return PredictionFrame(good.values + 1.0, good.index, good.metadata)

    with pytest.raises(AssertionError, match="bit-exact"):
        assert_reindex_fill_law(_Lying(frame, corrupt), target, 0.0)


def test_fill_law_catches_wrong_result_index():
    frame = _pf([1, 2], [10, 11])
    target = _index([1, 2], [10, 11])

    def corrupt(f, o, fv):
        good = f.reindex_fill(o, fill_value=fv)
        reversed_pos = np.arange(o.n_rows, dtype=np.intp)[::-1]
        return good.select(reversed_pos)

    with pytest.raises(AssertionError, match="equal the target"):
        assert_reindex_fill_law(_Lying(frame, corrupt), target, 0.0)
