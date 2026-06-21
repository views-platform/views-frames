"""Point estimates over the sample axis (ADR-017) — return a `(N, …, 1)` frame.

`map_estimate` is the maximum-a-posteriori estimate as faoapi/reporting compute it:
the empirical density peak (histogram), with a zero-mass→0 rule for the
zero-inflated conflict distributions. The mechanism reduces the **trailing** axis;
the leaf guarantees that axis is the sample axis (ADR-012).

The histogram is computed **batched in row-blocks** (no per-row Python loop) so
it scales to the full grid (register C-22). Blocking caps peak memory at
``O(block * bins)`` regardless of row count — a whole-grid batch would allocate a
``rows × bins`` counts matrix and re-introduce the #181 OOM. The batched binning
reproduces ``numpy.histogram``'s uniform-bin algorithm, so it selects the same
densest bin as the per-row reference; the bin centre matches to float32 precision
(proven by `test_summarize_scale.py`).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import AnyFrame, rebuild

# Row-block size for the batched histogram — bounds peak memory the same way
# numpy.histogram blocks its own fast path. Vectorized within a block; constant
# memory across blocks.
_ROW_BLOCK = 1 << 16


def map_estimate(
    frame: AnyFrame, *, bins: int = 100, zero_mass_threshold: float = 0.3
) -> AnyFrame:
    """Per-row MAP estimate over the sample axis → a `(N, …, 1)` frame.

    For each row: if a fraction ``>= zero_mass_threshold`` of the samples is ~0 the
    MAP is ``0.0``; otherwise it is the centre of the densest histogram bin (the
    same density peak ``numpy.histogram(..., density=True)`` finds).
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    # Bin in the input dtype, exactly as the v0.2.0 per-row np.histogram did —
    # upcasting to float64 would shift the bin edges and pick a different mode.
    flat = np.ascontiguousarray(values).reshape(-1, s)

    result = np.empty(flat.shape[0], dtype=np.float32)
    for start in range(0, flat.shape[0], _ROW_BLOCK):
        block = flat[start : start + _ROW_BLOCK]
        centers = _batched_map(block, bins)
        mass_at_zero = np.mean(np.isclose(block, 0.0, atol=1e-8), axis=1)
        result[start : start + _ROW_BLOCK] = np.where(
            mass_at_zero >= zero_mass_threshold, 0.0, centers
        )

    reduced = result.reshape(lead)[..., np.newaxis]
    return rebuild(frame, reduced)


def _batched_map(flat: NDArray[np.float32], bins: int) -> NDArray[np.float32]:
    """Centre of the densest histogram bin for each row of a row-block ``(M, S)``.

    Reproduces ``numpy.histogram``'s uniform-bin path row-by-row but vectorized:
    same dtype, same edges (``linspace``), same float-rounding correction, so the
    per-row bin counts — and therefore the argmax and bin centre — are identical.
    """
    m = flat.shape[0]
    dtype = flat.dtype
    first = flat.min(axis=1)
    last = flat.max(axis=1)
    # all-equal rows: numpy widens the range to (v - 0.5, v + 0.5).
    degenerate = first == last
    half = np.array(0.5, dtype=dtype)
    first = np.where(degenerate, first - half, first)
    last = np.where(degenerate, last + half, last)
    span = last - first

    # Per-row bin edges — numpy.histogram builds these with linspace at bin dtype.
    edges = np.linspace(first, last, bins + 1, axis=1).astype(dtype)  # (M, bins + 1)

    # numpy's uniform-bin index: ((a - first) / span) * bins, then the exact
    # float-rounding correction against the gathered edges.
    f_idx = ((flat - first[:, None]) / span[:, None]) * bins
    idx = f_idx.astype(np.intp)
    idx[idx == bins] = bins - 1
    left = np.take_along_axis(edges, idx, axis=1)
    idx[flat < left] -= 1
    right = np.take_along_axis(edges, idx + 1, axis=1)
    idx[(flat >= right) & (idx != bins - 1)] += 1

    # Batched bincount: offset each row into its own length-``bins`` block.
    offsets = idx + (np.arange(m)[:, None] * bins)
    counts = np.bincount(offsets.ravel(), minlength=m * bins).reshape(m, bins)

    # Pick the densest bin the way ``np.histogram(..., density=True)`` does:
    # density = counts / width (per-bin width cast to float64). The per-row total
    # is constant so it drops out of the argmax — but the float64 widths are not
    # exactly equal, and that tie-break must match the v0.2.0 reference.
    widths = np.diff(edges, axis=1).astype(np.float64)
    density = counts / widths
    densest = np.argmax(density, axis=1)

    lo = np.take_along_axis(edges, densest[:, None], axis=1)[:, 0]
    hi = np.take_along_axis(edges, (densest + 1)[:, None], axis=1)[:, 0]
    return np.asarray((lo + hi) / 2.0, dtype=np.float32)
