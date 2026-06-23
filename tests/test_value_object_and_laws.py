"""Green alignment-laws + value-object getter coverage (ADR-005 blind spot).

🟩 Green: value-object semantics (hash/eq/argsort), the SpatialLevel vocabulary,
and the two CIC-named alignment laws (align∘collapse order-independence;
reindex idempotent on a superset).
🟥 Red:   the columnar `cross_level_align_arrays` and summarize `rebuild` guards.
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_summarize import collapse
from views_frames_summarize._common import rebuild


def _idx(times, units, level=SpatialLevel.PGM):
    return SpatioTemporalIndex(
        np.array(times, dtype=np.int64), np.array(units, dtype=np.int32), level
    )


# --- SpatioTemporalIndex value-object semantics ------------------------------


def test_index_is_hashable_by_value():
    a = _idx([1, 2], [10, 20])
    b = _idx([1, 2], [10, 20])  # equal by value
    c = _idx([1, 3], [10, 20])  # different
    assert hash(a) == hash(b)
    assert len({a, b, c}) == 2  # a/b dedup; c distinct
    assert {a: "x"}[b] == "x"  # equal-by-value keys collide


def test_index_eq_against_non_index_is_false():
    a = _idx([1], [10])
    assert (a == "not an index") is False
    assert a != object()


def test_argsort_orders_time_major_then_unit():
    idx = _idx([2, 1, 2], [10, 5, 5])
    ordered = idx.select(idx.argsort())
    assert np.array_equal(ordered.time, [1, 2, 2])
    assert np.array_equal(ordered.unit, [5, 5, 10])


def test_spatial_level_vocabulary():
    assert SpatialLevel.PGM.entity_column == "priogrid_id"
    assert SpatialLevel.CM.entity_column == "country_id"
    assert SpatialLevel.PGM.index_names == ("month_id", "priogrid_id")
    assert SpatialLevel.CM.index_names == ("month_id", "country_id")


# --- green alignment laws ----------------------------------------------------


def test_collapse_and_reindex_commute():
    # CIC SpatioTemporalIndex §3: align ∘ collapse == collapse ∘ align.
    a = _idx([1, 2, 3], [10, 10, 10])
    pf = PredictionFrame(np.arange(12, dtype=np.float32).reshape(3, 4), a)
    other = _idx([3, 1], [10, 10])  # subset, reordered
    lhs = collapse(pf, np.mean).reindex(other)  # collapse then align
    rhs = collapse(pf.reindex(other), np.mean)  # align then collapse
    assert np.allclose(lhs.values, rhs.values)
    assert np.array_equal(lhs.identifiers["time"], rhs.identifiers["time"])


def test_reindex_is_idempotent_on_a_superset():
    a = _idx([1, 2, 3], [10, 10, 10])
    pf = PredictionFrame(np.arange(6, dtype=np.float32).reshape(3, 2), a)
    other = _idx([2, 3], [10, 10])
    once = pf.reindex(other)
    twice = once.reindex(other)  # other ⊆ once.index
    assert np.array_equal(once.values, twice.values)
    assert np.array_equal(once.identifiers["time"], twice.identifiers["time"])


# --- red guards on the columnar / summarize plumbing -------------------------


def test_cross_level_align_arrays_rejects_bad_target_level():
    pgm = _idx([1], [10])
    with pytest.raises(TypeError, match="SpatialLevel"):
        pgm.cross_level_align_arrays(
            np.array([[1, 10]], dtype=np.int64), np.array([100]), "cm"
        )  # type: ignore[arg-type]


def test_rebuild_rejects_non_frame():
    idx = _idx([1, 2], [10, 10])
    with pytest.raises(TypeError, match="unsupported frame type"):
        rebuild("not a frame", np.ones((2, 1), dtype=np.float32), index=idx)  # type: ignore[arg-type]
