"""H1: run the published conformance suite against the built-in frames.

This is the local "consumer" smoke test — it exercises `views_frames.conformance`
exactly as a downstream repo would against its own adapter output.
"""

from __future__ import annotations

import os

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
    assert_frame_envelope,
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
    assert CONFORMANCE_FLOOR == "1.0.0"


# --- the published frame-envelope checker (ADR-020, C-46) --------------------
#
# `assert_frame_envelope` is the subset of the contract that any frame-like type —
# spatiotemporal *or not* — must satisfy: float32 values, an explicit trailing axis,
# and a save/load round-trip. views-evaluation runs it against its non-spatiotemporal
# `MetricFrame` so the shared envelope has one written authority instead of drifting.


class _MetricLikeFrame:
    """A non-spatiotemporal frame-like (string axes) standing in for a `MetricFrame`.

    Satisfies the shared envelope but NOT the spatiotemporal `(time, unit)` contract.
    """

    def __init__(self, values, identifiers):
        self.values = values
        self.identifiers = identifiers

    @property
    def n_rows(self):
        return self.values.shape[0]

    def save(self, directory):
        path = os.path.join(directory, "frame.npz")
        cols = {f"id_{k}": v for k, v in self.identifiers.items()}
        np.savez(path, values=self.values, **cols)

    @classmethod
    def load(cls, directory):
        data = np.load(os.path.join(directory, "frame.npz"), allow_pickle=False)
        identifiers = {k[3:]: data[k] for k in data.files if k.startswith("id_")}
        return cls(data["values"], identifiers)


def _metric_like(dtype=np.float32):
    return _MetricLikeFrame(
        np.ones((3, 1), dtype=dtype),
        {
            "target": np.array(["ged_sb", "ged_ns", "ged_os"]),
            "metric": np.array(["crps", "crps", "crps"]),
        },
    )


@pytest.mark.parametrize(
    "frame",
    [
        PredictionFrame(np.ones((3, 4), dtype=np.float32), _index(3)),
        FeatureFrame(np.ones((3, 2, 4), dtype=np.float32), _index(3), ["a", "b"]),
        TargetFrame(np.ones((3, 1), dtype=np.float32), _index(3)),
    ],
)
def test_builtin_frames_satisfy_the_envelope(frame):
    # the full contract implies the envelope.
    assert_frame_envelope(frame)


def test_envelope_accepts_a_non_spatiotemporal_frame_like():
    # a string-keyed MetricFrame-like passes the shared envelope...
    assert_frame_envelope(_metric_like())


def test_full_contract_rejects_a_non_spatiotemporal_frame_like():
    # ...but NOT the spatiotemporal contract (no integer (time, unit) identifiers).
    with pytest.raises(AssertionError):
        assert_frame_contract(_metric_like())


def test_envelope_rejects_non_float32_values():
    with pytest.raises(AssertionError):
        assert_frame_envelope(_metric_like(dtype=np.float64))
