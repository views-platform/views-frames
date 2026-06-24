"""Threshold exceedance probabilities over the sample axis (ADR-021).

`exceedance(frame, thresholds)` returns the per-row empirical **survival fraction**
`P(Y > c)` for each threshold — an index-aligned array `(N, …, K)`, the same shape/role
family as `quantiles`. `exceedance_reducer(c)` is a `collapse`-compatible factory for
the single-threshold `(N, …, 1)` **frame** path.

Distribution-agnostic (a counting reducer — no histogram, no config, no unimodality
assumption), so it is robust where the tower is weakest (register C-34); the flagship
is `P(Y > 0)` = probability of any activity (onset). Thresholds are **required**
per-call, in the frame's own units (an *input*, like `quantiles`' ``qs`` — never a
tunable or a default). **Strict `>`** (register D-08). Fails loud on any NaN draw
(register C-50) and on empty thresholds; the joint-sample requirement for aggregate
exceedance is the consumer's (C-49).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, block_apply
from views_frames_summarize.collapse import Reducer


def _exceed(
    values: NDArray[np.float32], thresholds: NDArray[np.float64]
) -> NDArray[np.float32]:
    """Fraction of the trailing (sample) axis **strictly** greater than each threshold.

    ``values`` is ``(…, S)`` and ``thresholds`` is ``(K,)``; returns ``(…, K)``.

    Fails loud on NaN: ``NaN > c`` is silently ``False``, so a naive count would deflate
    ``P(Y > c)`` — worst on the ``P(Y > 0)`` onset flagship (register C-50).
    """
    if bool(np.isnan(values).any()):
        raise ValueError(
            "exceedance is undefined on NaN draws; strip or impute upstream "
            "(NaN > c is silently False and would deflate P(Y > c); register C-50)"
        )
    # (…, S) vs (K,) → (…, K, S) by broadcasting; strict ">"; mean over the sample axis.
    above = values[..., np.newaxis, :] > thresholds[:, np.newaxis]
    return np.asarray(above.mean(axis=-1), dtype=np.float32)


def exceedance(
    frame: AnyFrame,
    thresholds: Sequence[float],
    *,
    block_rows: int = ROW_BLOCK,
) -> NDArray[np.float32]:
    """Per-row exceedance probability `P(Y > c)` over the sample axis → `(N, …, K)`.

    For each of the ``K`` caller-supplied ``thresholds`` (required, in the frame's own
    units), the empirical fraction of draws **strictly** greater than it. An
    index-aligned numpy array (the caller holds the index), vectorized in row-blocks of
    ``block_rows`` so peak memory is bounded by one block's working set (register C-25).

    Raises:
        ValueError: ``thresholds`` is empty (no default), or any draw is NaN (C-50).
    """
    thr = np.asarray(thresholds, dtype=np.float64)
    if thr.size == 0:
        raise ValueError(
            "exceedance requires at least one threshold; there is no default "
            "(thresholds are an input in the frame's units, not a tunable — ADR-021)."
        )

    def _block(vals: NDArray[np.float32]) -> NDArray[np.float32]:
        return _exceed(vals, thr)

    out = block_apply(frame.values, block_rows, _block)
    return np.asarray(out, dtype=np.float32)


def exceedance_reducer(threshold: float) -> Reducer:
    """A `collapse`-compatible reducer for single-threshold exceedance.

    ``collapse(frame, exceedance_reducer(c))`` returns `P(Y > c)` as a `(N, …, 1)`
    frame, sharing `exceedance`'s strict-`>` and fail-loud-NaN policy (so a consumer
    never re-implements ``np.mean(values > c)`` and drifts on the convention).
    """
    thr = np.asarray([threshold], dtype=np.float64)

    def _reducer(values: NDArray[np.float32], axis: int = -1) -> NDArray[np.float32]:
        # `collapse` calls reducer(values, axis=-1) and appends the trailing axis
        # itself, so drop the singleton K axis (collapse re-adds the sample-axis slot).
        return _exceed(values, thr)[..., 0]

    return _reducer
