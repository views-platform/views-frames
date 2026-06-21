"""Interval estimates over the sample axis (ADR-017).

Return numpy arrays **aligned to the input frame's index** (the caller holds the
index): `hdi` → `(N, …, 2)` lower/upper; `quantiles` → `(N, …, len(qs))`.

Both reduce the **trailing** sample axis and are fully vectorized (no per-row
Python loop) so they scale to the full grid (register C-22).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import AnyFrame


def hdi(frame: AnyFrame, mass: float = 0.9) -> NDArray[np.float32]:
    """Per-row highest-density interval over the sample axis → `(N, …, 2)`.

    The shortest interval containing ``floor(mass * S)`` samples (empirical HDI),
    computed vectorized over the trailing axis.
    """
    values = frame.values
    s = values.shape[-1]
    srt = np.sort(values, axis=-1)
    k = int(np.floor(mass * s))
    if k < 1:
        lower = srt[..., 0]
        return np.asarray(np.stack([lower, lower], axis=-1), dtype=np.float32)
    # widest-to-narrowest: for each candidate start i, width = srt[i+k] - srt[i];
    # the narrowest window is the HDI. argmin returns the first minimum, matching
    # the per-row reference exactly.
    widths = srt[..., k:] - srt[..., : s - k]
    i = np.argmin(widths, axis=-1)
    lower = np.take_along_axis(srt, i[..., np.newaxis], axis=-1)[..., 0]
    upper = np.take_along_axis(srt, (i + k)[..., np.newaxis], axis=-1)[..., 0]
    return np.asarray(np.stack([lower, upper], axis=-1), dtype=np.float32)


def quantiles(frame: AnyFrame, qs: Sequence[float]) -> NDArray[np.float32]:
    """Per-row quantiles over the sample axis → `(N, …, len(qs))`, index-aligned."""
    q = np.quantile(frame.values, np.asarray(qs, dtype=np.float64), axis=-1)
    return np.moveaxis(np.asarray(q, dtype=np.float32), 0, -1)
