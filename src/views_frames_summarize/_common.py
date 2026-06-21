"""Shared helpers for the summarize package.

Rebuilds a frame of the same concrete type with new values, preserving the index
and metadata — the structural plumbing every reducer needs.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames import FeatureFrame, PredictionFrame, TargetFrame

AnyFrame = PredictionFrame | FeatureFrame | TargetFrame


def rebuild(frame: AnyFrame, values: NDArray[np.float32]) -> AnyFrame:
    """Return a frame of the same type as ``frame`` with new ``values``.

    The index, metadata, and (for `FeatureFrame`) `feature_names` are preserved;
    the new values are validated by the frame's constructor.
    """
    if isinstance(frame, FeatureFrame):
        return FeatureFrame(values, frame.index, frame.feature_names, frame.metadata)
    if isinstance(frame, PredictionFrame):
        return PredictionFrame(values, frame.index, frame.metadata)
    if isinstance(frame, TargetFrame):
        return TargetFrame(values, frame.index, frame.metadata)
    raise TypeError(f"unsupported frame type: {type(frame).__name__}")
