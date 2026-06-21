"""Interval estimates over the sample axis (ADR-017).

Return numpy arrays **aligned to the input frame's index** (the caller holds the
index): `hdi` → `(N, …, 2)` lower/upper; `quantiles` → `(N, …, len(qs))`.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import AnyFrame


def hdi(frame: AnyFrame, mass: float = 0.9) -> NDArray[np.float32]:
    """Per-row highest-density interval over the sample axis → `(N, …, 2)`.

    The shortest interval containing ``floor(mass * S)`` samples (empirical HDI).
    """
    out = np.apply_along_axis(_hdi_1d, -1, frame.values, mass)
    return np.asarray(out, dtype=np.float32)


def quantiles(frame: AnyFrame, qs: Sequence[float]) -> NDArray[np.float32]:
    """Per-row quantiles over the sample axis → `(N, …, len(qs))`, index-aligned."""
    q = np.quantile(frame.values, np.asarray(qs, dtype=np.float64), axis=-1)
    return np.moveaxis(np.asarray(q, dtype=np.float32), 0, -1)


def _hdi_1d(samples: NDArray[np.float32], mass: float) -> NDArray[np.float32]:
    srt = np.sort(samples)
    n = int(srt.shape[0])
    k = int(np.floor(mass * n))
    if k < 1:
        return np.array([srt[0], srt[0]], dtype=np.float32)
    widths = srt[k:] - srt[: n - k]
    i = int(np.argmin(widths))
    return np.array([srt[i], srt[i + k]], dtype=np.float32)
