"""Shared helpers for the summarize package.

Rebuilds a frame of the same concrete type with new values, preserving the index
and metadata — the structural plumbing every reducer needs.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from views_frames import (
    FeatureFrame,
    PredictionFrame,
    SpatioTemporalIndex,
    TargetFrame,
)

AnyFrame = PredictionFrame | FeatureFrame | TargetFrame

# Default row-block size for the memory-bounded estimators. Blocking caps the peak
# memory of an estimator at ``O(block * …)`` regardless of row count, so the
# full-grid reduction path stays well under the #181 OOM (register C-22, C-25).
ROW_BLOCK = 1 << 16


def block_apply(
    values: NDArray[np.float32],
    block_rows: int,
    fn: Callable[[NDArray[np.float32]], NDArray[np.float32]],
) -> NDArray[np.float32]:
    """Apply ``fn`` to row-blocks of ``values`` (over axis 0), concatenating results.

    ``fn`` maps a ``(block, …)`` slice to a ``(block, …)`` result (same axis-0
    length). Peak memory is bounded by one block's working set, not the whole grid.
    Frames at or below ``block_rows`` rows take the single-shot path (no copy).
    """
    n = values.shape[0]
    if n <= block_rows:
        return fn(values)
    parts = [
        fn(values[start : start + block_rows]) for start in range(0, n, block_rows)
    ]
    return np.concatenate(parts, axis=0)


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
