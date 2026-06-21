"""Shared helpers for the summarize package.

Rebuilds a frame of the same concrete type with new values, preserving the index
and metadata — the structural plumbing every reducer needs.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames import (
    FeatureFrame,
    PredictionFrame,
    SpatioTemporalIndex,
    TargetFrame,
)

AnyFrame = PredictionFrame | FeatureFrame | TargetFrame


def rebuild(
    frame: AnyFrame,
    values: NDArray[np.float32],
    index: SpatioTemporalIndex | None = None,
) -> AnyFrame:
    """Return a frame of the same type as ``frame`` with new ``values``.

    The metadata (and, for `FeatureFrame`, `feature_names`) is preserved. The index
    defaults to the input frame's; pass ``index`` to rebuild at a different index
    (e.g. after cross-level aggregation). The new values are validated by the
    frame's constructor.
    """
    idx = frame.index if index is None else index
    if isinstance(frame, FeatureFrame):
        return FeatureFrame(values, idx, frame.feature_names, frame.metadata)
    if isinstance(frame, PredictionFrame):
        return PredictionFrame(values, idx, frame.metadata)
    if isinstance(frame, TargetFrame):
        return TargetFrame(values, idx, frame.metadata)
    raise TypeError(f"unsupported frame type: {type(frame).__name__}")
