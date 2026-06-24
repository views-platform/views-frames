"""Worst-case scenario summary over the sample axis (ADR-022).

`expected_shortfall(frame, tails)` returns the per-row **mean of the worst `⌈t·S⌉`
draws** for each upper-tail fraction `t` — the tail mean / CVaR, a coherent worst-case
risk measure and the companion to `exceedance`. An index-aligned array `(N, …, K)`, the
same shape/role family as `quantiles`.

`max` is deliberately **not** offered — it is the highest-variance, non-reproducible
summary this replaces. Tails are **required** per-call, in `(0, 1]` (e.g. `0.01` = "the
worst 1%") — the consumer's policy, never a default or config. Fails loud on any
non-finite draw — NaN or ±inf (numpy sorts them *last*, so a naive top-`k` mean silently
selects them — register C-56), on empty `tails`, and on any `t` outside `(0, 1]`.

Written explicitly in its own module — it does **not** share a "tail reducer"
abstraction with `quantiles`/`exceedance` (the duplication is shallow and the concerns
change independently — WET before DRY). It reuses only the stable `_common` primitives.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, block_apply


def _expected_shortfall(
    values: NDArray[np.float32], tails: NDArray[np.float64]
) -> NDArray[np.float32]:
    """Mean of the worst ``⌈t·S⌉`` draws of the trailing (sample) axis, per tail.

    ``values`` is ``(…, S)``, ``tails`` is ``(K,)`` in ``(0, 1]``; returns ``(…, K)``.

    Fails loud on any **non-finite** draw (NaN or ±inf): numpy sorts NaN *last*, so a
    top-`k` mean would silently select the NaNs — a NaN/garbage worst-case; and an ±inf
    draw (always an upstream bug) sorts last and contaminates the tail mean to ±inf — a
    degenerate "worst case". A draw must be a usable finite number (register C-56).
    """
    if not bool(np.isfinite(values).all()):
        raise ValueError(
            "expected_shortfall is undefined on non-finite draws (NaN or ±inf); strip "
            "or impute upstream (numpy sorts NaN/+inf last, so the worst-k mean would "
            "silently select them — a NaN/inf worst-case; register C-56)"
        )
    s = values.shape[-1]
    srt = np.sort(values, axis=-1)  # ascending: the worst (largest) draws are last
    out = np.empty((*values.shape[:-1], tails.shape[0]), dtype=np.float32)
    for i in range(tails.shape[0]):
        k = int(np.ceil(float(tails[i]) * s))  # number of worst draws to average (≥ 1)
        out[..., i] = srt[..., s - k :].mean(axis=-1)
    return out


def expected_shortfall(
    frame: AnyFrame,
    tails: Sequence[float],
    *,
    block_rows: int = ROW_BLOCK,
) -> NDArray[np.float32]:
    """Per-row worst-case **expected shortfall** over the sample axis → `(N, …, K)`.

    For each upper-tail fraction ``t`` in ``tails`` (required, in ``(0, 1]``), the mean
    of the worst ``⌈t·S⌉`` draws — the average of the worst-case scenarios. An
    index-aligned numpy array (the caller holds the index), block-applied in row-blocks.

    Raises:
        ValueError: ``tails`` is empty (no default), any ``t ∉ (0, 1]`` (a tail with no
            samples), or any draw is non-finite — NaN or ±inf (register C-56).
    """
    thr = np.asarray(tails, dtype=np.float64)
    if thr.size == 0:
        raise ValueError(
            "expected_shortfall requires at least one tail level; there is no default "
            "(the tail fraction is an input in (0, 1], not a tunable — ADR-022)."
        )
    if bool(((thr <= 0.0) | (thr > 1.0)).any()):
        raise ValueError(
            f"expected_shortfall tails must be in (0, 1]; got {thr.tolist()} "
            "(a tail <= 0 contains no samples; > 1 is not a fraction)."
        )

    def _block(vals: NDArray[np.float32]) -> NDArray[np.float32]:
        return _expected_shortfall(vals, thr)

    out = block_apply(frame.values, block_rows, _block)
    return np.asarray(out, dtype=np.float32)
