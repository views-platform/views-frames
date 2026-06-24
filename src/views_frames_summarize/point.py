"""Point estimates over the sample axis (ADR-017) — return a `(N, …, 1)` frame.

`map_estimate` is the maximum-a-posteriori estimate as faoapi/reporting compute it:
the empirical density peak (histogram), with a zero-mass→0 rule for the
zero-inflated conflict distributions. The mechanism reduces the **trailing** axis;
the leaf guarantees that axis is the sample axis (ADR-012).

The histogram is computed **batched in row-blocks** (no per-row Python loop) so
it scales to the full grid (register C-22). Blocking caps peak memory at
``O(block * bins)`` regardless of row count — a whole-grid batch would allocate a
``rows × bins`` counts matrix and re-introduce the #181 OOM. The batched binning
reproduces ``numpy.histogram``'s uniform-bin **counts** and breaks ties on the
integer counts (lowest-index), so the selected bin is **deterministic and
identical on every numpy version** (register C-24); the bin centre matches the
per-row reference to float32 precision (proven by `test_summarize_scale.py`).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, rebuild


def map_estimate(
    frame: AnyFrame,
    *,
    bins: int = 100,
    zero_mass_threshold: float = 0.3,
    block_rows: int = ROW_BLOCK,
) -> AnyFrame:
    """Per-row MAP estimate over the sample axis → a `(N, …, 1)` frame.

    For each row: if a fraction ``>= zero_mass_threshold`` of the samples is ~0 the
    MAP is ``0.0``; otherwise it is the centre of the densest histogram bin. The
    work runs in row-blocks of ``block_rows`` to bound peak memory (register C-22).

    Caveat (register C-32): the densest-bin tie-break is the **lowest bin index**
    (deterministic; register C-24). At low sample counts the histogram peak is
    usually a multi-way tie, and lowest-index = leftmost = smallest value — so for
    **right-skewed, zero-inflated** posteriors the mode is biased toward the left
    tail (zero). This is therefore **not a drop-in** for a production histogram-MAP
    on such distributions; a robust mode estimator is tracked separately (#89).
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    # Bin in the input dtype, exactly as the v0.2.0 per-row np.histogram did —
    # upcasting to float64 would shift the bin edges and pick a different mode.
    flat = np.ascontiguousarray(values).reshape(-1, s)

    result = np.empty(flat.shape[0], dtype=np.float32)
    for start in range(0, flat.shape[0], block_rows):
        block = flat[start : start + block_rows]
        centers = _batched_map(block, bins)
        mass_at_zero = np.mean(np.isclose(block, 0.0, atol=1e-8), axis=1)
        result[start : start + block_rows] = np.where(
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

    # The densest bin = the one with the most samples. Tie-break on the **integer
    # counts** (lowest-index wins), not on ``counts / width`` density: the bins are
    # uniform so density and counts agree on the winner — *except* on ties, where
    # the float64 bin widths differ by ~1 ulp across numpy versions and flip the
    # argmax (register C-24). Integer ``argmax`` is deterministic and identical on
    # every numpy build, so ``map_estimate`` is portable and reproducible.
    # NOTE (register C-32): lowest-index == leftmost == smallest value, so on the
    # frequent low-sample ties this biases the mode toward zero for right-skewed,
    # zero-inflated posteriors. Portable but not unbiased; redesign tracked in #89.
    densest = np.argmax(counts, axis=1)

    lo = np.take_along_axis(edges, densest[:, None], axis=1)[:, 0]
    hi = np.take_along_axis(edges, (densest + 1)[:, None], axis=1)[:, 0]
    return np.asarray((lo + hi) / 2.0, dtype=np.float32)
