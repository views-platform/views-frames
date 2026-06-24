"""Per-row bimodality flag (ADR-019) — a `(N, …, 1)` array aligned to the index.

A genuinely two-peaked posterior — a zero atom plus a *distinct* positive bump, or two
well-separated positive bumps — has no well-defined "most likely single value" and no
well-defined shortest interval (the shortest 50% interval flips between the peaks under
tiny perturbations, at *any* grid density). `bimodality` flags those rows so a consumer
is never handed a single point / interval that silently hides a second mode.

The detector is a **deliberately conservative heuristic**, not a formal multimodality
test. Per row: a coarse, lightly-smoothed histogram; then a count of *separated*
density regions — runs of bins at least ``prominence`` of the row's peak, with
sub-``prominence`` valleys between them — keeping only regions that carry at least
``min_mass`` of the samples. A row is flagged iff ≥ 2 such regions survive. Quiet rows
(the zero short-circuit) are never flagged.

It is tuned (against the research battery) for **zero false positives** on the normal
regime — right-skewed, zero-inflated and active unimodal posteriors all read as
unimodal — at the cost of recall on *ambiguous*, overlapping mixtures. That trade is
intentional: today's models are effectively unimodal, so the flag's job is to catch a
future regime change that produces *clearly* separated modes, not to adjudicate every
heavy tail. A missed subtle bump is cheaper than crying wolf on every skewed cell.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize import config
from views_frames_summarize._common import AnyFrame, block_apply
from views_frames_summarize.tower import _zero_mask


def _coarse_counts(flat: NDArray[np.float32], bins: int) -> NDArray[np.intp]:
    """Per-row histogram counts ``(rows, bins)`` over each row's ``[min, max]``.

    A simple clipped linear bucket (not ``numpy.histogram``'s edge-exact path) —
    enough to locate density regions. All-equal rows fall into a single bin.
    """
    rows = flat.shape[0]
    first = flat.min(axis=1)
    last = flat.max(axis=1)
    span = np.where(first == last, np.float32(1.0), last - first)
    idx = (((flat - first[:, None]) / span[:, None]) * bins).astype(np.intp)
    np.clip(idx, 0, bins - 1, out=idx)
    offsets = idx + (np.arange(rows)[:, None] * bins)
    return np.bincount(offsets.ravel(), minlength=rows * bins).reshape(rows, bins)


def _bimodal_block(
    block: NDArray[np.float32],
    bins: int,
    prominence: float,
    min_mass: float,
    smooth: int,
) -> NDArray[np.float32]:
    """Flag (0/1) per row of a block: ≥ 2 separated regions each holding enough mass.

    ``smooth`` is the moving-average window width (the 3-tap normalization; config
    ``bimodality_smooth``). It tames sparse-histogram flicker.
    """
    rows = block.shape[0]
    counts = _coarse_counts(block, bins).astype(np.float64)

    # Light moving-average smoothing (window ``smooth``) over the bins. Normalise each
    # position by the number of *real* bins in its window — the two edge bins have one
    # fewer neighbour, so dividing them by the full window would deflate an edge peak
    # (e.g. the zero atom, which always lands in bin 0) and hide an atom+bump bimodal.
    pad = np.zeros((rows, 1))
    padded = np.concatenate([pad, counts, pad], axis=1)
    window_sum = padded[:, :-2] + padded[:, 1:-1] + padded[:, 2:]
    divisor = np.full(bins, smooth, dtype=np.float64)
    divisor[0] = divisor[-1] = smooth - 1  # edges contribute one fewer real bin
    smoothed = window_sum / divisor

    significant = smoothed >= prominence * smoothed.max(axis=1, keepdims=True)
    prev = np.concatenate(
        [np.zeros((rows, 1), dtype=bool), significant[:, :-1]], axis=1
    )
    starts = significant & ~prev
    # Label each maximal run of significant bins with a per-row region index (1-based).
    region = np.where(significant, np.cumsum(starts, axis=1), 0)

    total = counts.sum(axis=1)
    kept = np.zeros(rows, dtype=np.intp)
    for r in range(
        1, int(region.max()) + 1
    ):  # <= bins iterations, vectorized over rows
        mass = np.where(region == r, counts, 0.0).sum(axis=1)
        kept += (mass >= min_mass * total).astype(np.intp)

    flag = (kept >= 2).astype(np.float32)
    flag[_zero_mask(block)] = 0.0
    return flag


def bimodality(frame: AnyFrame) -> NDArray[np.float32]:
    """Per-row bimodality flag over the sample axis → ``(N, …, 1)`` of ``0.0``/``1.0``.

    Conservative heuristic (see module docstring): ≥ 2 separated density regions, each
    holding ≥ ``min_mass`` of the samples, after coarse binning + light smoothing.
    Aligned to ``frame.index``. Tunables (``bins``, ``prominence``, ``min_mass``,
    ``smooth``, row-block) come from ``config`` — no silent defaults (ADR-009).
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    bins = int(config.get("bimodality_bins"))
    prominence = float(config.get("bimodality_prominence"))
    min_mass = float(config.get("bimodality_min_mass"))
    smooth = int(config.get("bimodality_smooth"))
    block_rows = int(config.get("row_block"))
    flat = np.ascontiguousarray(values).reshape(-1, s)

    def _block(block: NDArray[np.float32]) -> NDArray[np.float32]:
        return _bimodal_block(block, bins, prominence, min_mass, smooth)

    out = block_apply(flat, block_rows, _block)
    return np.asarray(out, dtype=np.float32).reshape(lead)[..., np.newaxis]
