"""H2: copy-vs-view memory properties (register C-07) + alignment-law properties."""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import (
    FeatureFrame,
    Frame,
    FrameMetadata,
    Persistable,
    PredictionFrame,
    Sampled,
    SpatialLevel,
    SpatioTemporalIndex,
    SpatioTemporalIndexed,
    TargetFrame,
)


def _index(n=4):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(n, dtype=np.int32),
        level=SpatialLevel.PGM,
    )


def _frames():
    return [
        PredictionFrame(np.ones((4, 3), dtype=np.float32), _index(4)),
        FeatureFrame(np.ones((4, 2, 3), dtype=np.float32), _index(4), ["a", "b"]),
        TargetFrame(np.ones((4, 1), dtype=np.float32), _index(4)),
    ]


def test_with_metadata_shares_the_values_buffer():
    # Structural / metadata-only ops must NOT copy the (potentially multi-GB) buffer.
    for frame in _frames():
        other = frame.with_metadata(FrameMetadata(model="x"))
        assert np.shares_memory(frame.values, other.values)
        assert other.metadata.model == "x"


def test_intersect_is_commutative_and_associative_on_self():
    a = SpatioTemporalIndex(
        np.array([1, 2, 3], dtype=np.int64),
        np.array([10, 20, 30], dtype=np.int32),
        SpatialLevel.PGM,
    )
    b = SpatioTemporalIndex(
        np.array([2, 3, 4], dtype=np.int64),
        np.array([20, 30, 40], dtype=np.int32),
        SpatialLevel.PGM,
    )
    assert a.intersect(b) == b.intersect(a)
    assert a.intersect(a) == a


def test_reindex_round_trips_self():
    a = _index(5)
    pos = a.reindex(a)
    assert np.array_equal(a.time[pos], a.time)
    assert np.array_equal(a.unit[pos], a.unit)


@pytest.mark.parametrize(
    "protocol", [Frame, SpatioTemporalIndexed, Sampled, Persistable]
)
def test_frames_satisfy_runtime_checkable_protocols(protocol):
    # 🟩 Green: the Protocols CIC section-3 guarantee, asserted directly (C-37).
    # Every frame is a runtime instance of each @runtime_checkable protocol
    # (Frame, SpatioTemporalIndexed, Sampled, Persistable), not just its own class.
    for frame in _frames():
        assert isinstance(frame, protocol), (
            f"{type(frame).__name__} must satisfy the {protocol.__name__} protocol"
        )
