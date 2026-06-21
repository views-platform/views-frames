"""Tests for `_validation`, `SpatioTemporalIndex`, and `cross_level_align` (E1-E3)."""

from __future__ import annotations

import numpy as np
import pytest

from views_frames._validation import validate_identifiers, validate_values
from views_frames.index import SpatioTemporalIndex
from views_frames.spatial_level import SpatialLevel


def _idx(times, units, level=SpatialLevel.PGM):
    return SpatioTemporalIndex(
        time=np.array(times, dtype=np.int64),
        unit=np.array(units, dtype=np.int32),
        level=level,
    )


# --- E1: _validation ---------------------------------------------------------


def test_validate_identifiers_missing_required():
    with pytest.raises(ValueError, match="Missing required identifier: 'unit'"):
        validate_identifiers({"time": np.array([1], dtype=np.int64)}, n_rows=1)


def test_validate_identifiers_non_integer_raises_type_error():
    ids = {"time": np.array([1.0], dtype=np.float64), "unit": np.array([1])}
    with pytest.raises(TypeError, match="integer dtype"):
        validate_identifiers(ids, n_rows=1)


def test_validate_identifiers_length_mismatch():
    ids = {
        "time": np.array([1, 2], dtype=np.int64),
        "unit": np.array([1], dtype=np.int64),
    }
    with pytest.raises(ValueError, match="length"):
        validate_identifiers(ids, n_rows=2)


def test_validate_values_object_dtype_banned():
    with pytest.raises(ValueError, match="object dtype"):
        validate_values(np.array([[1], [2]], dtype=object))


def test_validate_values_requires_float32():
    with pytest.raises(TypeError, match="float32"):
        validate_values(np.zeros((2, 1), dtype=np.float64))


def test_validate_values_requires_trailing_axis():
    with pytest.raises(ValueError, match="trailing sample axis"):
        validate_values(np.zeros((2,), dtype=np.float32))


def test_validate_values_accepts_valid():
    validate_values(np.zeros((3, 2), dtype=np.float32))  # no raise


# --- E2: SpatioTemporalIndex -------------------------------------------------


def test_construction_and_properties():
    idx = _idx([1, 1, 2], [10, 20, 10])
    assert idx.n_rows == 3
    assert len(idx) == 3
    assert idx.level is SpatialLevel.PGM
    assert set(idx.identifiers) == {"time", "unit"}


def test_index_is_immutable():
    idx = _idx([1, 2], [10, 20])
    with pytest.raises(ValueError):
        idx.time[0] = 99


def test_bad_level_type_raises():
    with pytest.raises(TypeError, match="SpatialLevel"):
        SpatioTemporalIndex(np.array([1]), np.array([1]), level="pgm")  # type: ignore[arg-type]


def test_searchsorted_self_is_identity_roundtrip():
    idx = _idx([2, 1, 2], [10, 10, 20])
    pos = idx.searchsorted(idx)
    assert np.array_equal(idx.time[pos], idx.time)
    assert np.array_equal(idx.unit[pos], idx.unit)


def test_searchsorted_missing_rows_return_minus_one():
    a = _idx([1, 2], [10, 10])
    b = _idx([1, 3], [10, 10])
    pos = a.searchsorted(b)
    assert pos[0] >= 0  # (1,10) present
    assert pos[1] == -1  # (3,10) absent


def test_intersect_is_commutative():
    a = _idx([1, 2, 3], [10, 10, 10])
    b = _idx([2, 3, 4], [10, 10, 10])
    assert a.intersect(b) == b.intersect(a)


def test_is_superset_of_is_reflexive():
    a = _idx([1, 2], [10, 20])
    assert a.is_superset_of(a) is True
    assert a.is_superset_of(_idx([1], [10])) is True
    assert a.is_superset_of(_idx([9], [99])) is False


def test_same_level_required():
    a = _idx([1], [10], level=SpatialLevel.PGM)
    b = _idx([1], [10], level=SpatialLevel.CM)
    with pytest.raises(ValueError, match="same-level"):
        a.intersect(b)


# --- C-21: row-uniqueness stance ---------------------------------------------


def test_has_unique_rows_true_for_distinct_rows():
    idx = _idx([1, 1, 2], [10, 11, 10])
    assert idx.has_unique_rows() is True


def test_has_unique_rows_false_on_duplicate_time_unit():
    # same (time, unit) twice — allowed to construct, but flagged on demand.
    idx = _idx([1, 1], [10, 10])
    assert idx.has_unique_rows() is False


def test_duplicate_rows_are_allowed_at_construction():
    # uniqueness is NOT a construction invariant (cross_level_align produces dups).
    idx = _idx([1, 1], [10, 10])
    assert idx.n_rows == 2


# --- E3: cross_level_align ---------------------------------------------------


def test_cross_level_align_with_injected_mapping():
    pgm = _idx([1, 1, 2], [10, 11, 10], level=SpatialLevel.PGM)
    # mapping is keyed by (time, unit): two priogrid cells -> one country.
    mapping = {(1, 10): 100, (1, 11): 100, (2, 10): 100}
    cm = pgm.cross_level_align(mapping, target_level=SpatialLevel.CM)
    assert cm.level is SpatialLevel.CM
    assert np.array_equal(cm.unit, np.array([100, 100, 100], dtype=np.int32))
    assert np.array_equal(cm.time, pgm.time)


def test_cross_level_align_is_time_varying():
    # C-20: the same priogrid cell belongs to different countries in different
    # months (e.g. a border change). A (time, unit)-keyed mapping must honour it;
    # a static unit->country map could not express this.
    pgm = _idx([1, 2], [10, 10], level=SpatialLevel.PGM)
    mapping = {(1, 10): 100, (2, 10): 200}  # cell 10: country 100 in t=1, 200 in t=2
    cm = pgm.cross_level_align(mapping, target_level=SpatialLevel.CM)
    assert np.array_equal(cm.unit, np.array([100, 200], dtype=np.int32))
    assert np.array_equal(cm.time, np.array([1, 2], dtype=np.int64))


def test_cross_level_align_requires_mapping():
    pgm = _idx([1], [10])
    with pytest.raises(ValueError, match="requires an injected"):
        pgm.cross_level_align({}, target_level=SpatialLevel.CM)


def test_cross_level_align_rejects_unit_only_mapping():
    # the old static {unit: target} shape is now a fail-loud error (C-20).
    pgm = _idx([1], [10])
    with pytest.raises(ValueError, match="keyed by .time, unit. pairs"):
        pgm.cross_level_align({10: 100}, target_level=SpatialLevel.CM)  # type: ignore[dict-item]


def test_cross_level_align_unmapped_row_raises():
    pgm = _idx([1], [10])
    with pytest.raises(ValueError, match="no entry in the injected mapping"):
        pgm.cross_level_align({(9, 9): 1}, target_level=SpatialLevel.CM)


def test_cross_level_align_bad_target_level():
    pgm = _idx([1], [10])
    with pytest.raises(TypeError, match="SpatialLevel"):
        pgm.cross_level_align({(1, 10): 1}, target_level="cm")  # type: ignore[arg-type]


# --- C-26: columnar cross_level_align_arrays ---------------------------------


def test_cross_level_align_arrays_matches_dict():
    pgm = _idx([1, 1, 2], [10, 11, 10], level=SpatialLevel.PGM)
    mapping = {(1, 10): 100, (1, 11): 100, (2, 10): 200}
    via_dict = pgm.cross_level_align(mapping, SpatialLevel.CM)
    map_keys = np.array([[1, 10], [1, 11], [2, 10]], dtype=np.int64)
    map_vals = np.array([100, 100, 200], dtype=np.int64)
    via_arrays = pgm.cross_level_align_arrays(map_keys, map_vals, SpatialLevel.CM)
    assert np.array_equal(via_arrays.unit, via_dict.unit)
    assert np.array_equal(via_arrays.time, via_dict.time)
    assert via_arrays.unit.dtype == pgm.unit.dtype  # cast to the index's unit dtype


def test_cross_level_align_arrays_validates_shapes():
    pgm = _idx([1], [10])
    with pytest.raises(ValueError, match="must be an .M, 2. array"):
        pgm.cross_level_align_arrays(
            np.array([1, 10], dtype=np.int64), np.array([100]), SpatialLevel.CM
        )
    with pytest.raises(ValueError, match="length-M array"):
        pgm.cross_level_align_arrays(
            np.array([[1, 10]], dtype=np.int64),
            np.array([100, 200]),
            SpatialLevel.CM,
        )
    with pytest.raises(ValueError, match="non-empty"):
        pgm.cross_level_align_arrays(
            np.empty((0, 2), dtype=np.int64), np.empty(0, np.int64), SpatialLevel.CM
        )


def test_cross_level_align_arrays_unmapped_row_raises():
    pgm = _idx([1], [10])
    with pytest.raises(ValueError, match="no entry in the injected mapping"):
        pgm.cross_level_align_arrays(
            np.array([[9, 9]], dtype=np.int64), np.array([1]), SpatialLevel.CM
        )
