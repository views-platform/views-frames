"""Interval estimates over the sample axis (ADR-017).

Return numpy arrays **aligned to the input frame's index** (the caller holds the
index): `hdi` → `(N, …, 2)` lower/upper; `quantiles` → `(N, …, len(qs))`.

Both reduce the **trailing** sample axis and are vectorized (no per-row Python
loop). They run in **row-blocks** (`block_rows`) so peak memory is bounded by one
block's working set rather than a full-grid sorted copy — the same discipline as
`map_estimate`, so the whole reduction family stays under the #181 OOM (register
C-25).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, block_apply


def hdi(
    frame: AnyFrame, mass: float = 0.9, *, block_rows: int = ROW_BLOCK
) -> NDArray[np.float32]:
    """Per-row highest-density interval over the sample axis → `(N, …, 2)`.

    The shortest interval containing ``floor(mass * S)`` samples (empirical HDI),
    computed vectorized over the trailing axis, in row-blocks of ``block_rows``.
    """
    s = frame.values.shape[-1]
    k = int(np.floor(mass * s))

    def _hdi_block(vals: NDArray[np.float32]) -> NDArray[np.float32]:
        srt = np.sort(vals, axis=-1)
        if k < 1:
            lower = srt[..., 0]
            return np.stack([lower, lower], axis=-1)
        # widest-to-narrowest: for each candidate start i, width = srt[i+k] - srt[i];
        # the narrowest window is the HDI. argmin returns the first minimum.
        widths = srt[..., k:] - srt[..., : s - k]
        i = np.argmin(widths, axis=-1)
        lower = np.take_along_axis(srt, i[..., np.newaxis], axis=-1)[..., 0]
        upper = np.take_along_axis(srt, (i + k)[..., np.newaxis], axis=-1)[..., 0]
        return np.stack([lower, upper], axis=-1)

    out = block_apply(frame.values, block_rows, _hdi_block)
    return np.asarray(out, dtype=np.float32)


def quantiles(
    frame: AnyFrame, qs: Sequence[float], *, block_rows: int = ROW_BLOCK
) -> NDArray[np.float32]:
    """Per-row quantiles over the sample axis → `(N, …, len(qs))`, index-aligned."""
    q_levels = np.asarray(qs, dtype=np.float64)

    def _q_block(vals: NDArray[np.float32]) -> NDArray[np.float32]:
        q = np.quantile(vals, q_levels, axis=-1)
        return np.moveaxis(np.asarray(q, dtype=np.float32), 0, -1)

    out = block_apply(frame.values, block_rows, _q_block)
    return np.asarray(out, dtype=np.float32)
