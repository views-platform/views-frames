"""H1: run the published conformance suite against the built-in frames.

This is the local "consumer" smoke test — it exercises `views_frames.conformance`
exactly as a downstream repo would against its own adapter output.
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
from views_frames.conformance import (
    CONFORMANCE_FLOOR,
    assert_cross_level_alignment_law,
    assert_frame_contract,
    assert_index_alignment_laws,
)


def _index(n=3):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=SpatialLevel.PGM,
    )


@pytest.mark.parametrize(
    "frame",
    [
        PredictionFrame(np.ones((3, 4), dtype=np.float32), _index(3)),
        FeatureFrame(np.ones((3, 2, 4), dtype=np.float32), _index(3), ["a", "b"]),
        TargetFrame(np.ones((3, 1), dtype=np.float32), _index(3)),
    ],
)
def test_builtin_frames_satisfy_the_contract(frame):
    assert_frame_contract(frame)


def test_index_alignment_laws():
    a = SpatioTemporalIndex(
        np.array([1, 2, 3], dtype=np.int64),
        np.array([10, 10, 10], dtype=np.int32),
        SpatialLevel.PGM,
    )
    b = SpatioTemporalIndex(
        np.array([2, 3, 4], dtype=np.int64),
        np.array([10, 10, 10], dtype=np.int32),
        SpatialLevel.PGM,
    )
    assert_index_alignment_laws(a, b)


def test_cross_level_alignment_law_is_time_varying():
    # the same pgm cell (unit 10) maps to different countries across two months.
    idx = SpatioTemporalIndex(
        np.array([1, 2], dtype=np.int64),
        np.array([10, 10], dtype=np.int32),
        SpatialLevel.PGM,
    )
    mapping = {(1, 10): 100, (2, 10): 200}
    assert_cross_level_alignment_law(idx, mapping, SpatialLevel.CM)


def test_conformance_floor_is_published():
    assert CONFORMANCE_FLOOR == "0.1.0"
