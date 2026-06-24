"""The tower-tip point estimate (ADR-019) — a `(N, …, 1)` frame.

`tower_point` is the "most likely single value" we report to a consumer: the median of
the draws inside the **`tip_mass` floor** of the nested tower (config-driven, default
0.5 — the "shorth"). Zero-inflation is handled by that floor's density (a zero-majority
row reads 0); the optional, off-by-default magnitude cutoff applies too if set (C-45).

It is a *new* estimator, deliberately distinct from the frozen `map_estimate` (ADR-018):
`map_estimate` is a binned histogram mode with a zero-*mass*-fraction rule and a
lowest-index tie-break that is directionally biased on right-skewed, zero-inflated,
low-sample posteriors (register C-32). The tower tip is unbinned — it reads the median
of a mass-aware floor — so it carries no histogram tie-break **and** is robust to
minority duplicated draws (register C-44; a lonely outlier cannot define a 50%-mass
floor). On a genuinely multi-peaked row the tip is, like any point, ambiguous; pair it
with `bimodality` to detect that case rather than collapse it silently.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize import config
from views_frames_summarize._common import AnyFrame, block_apply, rebuild
from views_frames_summarize.tower import (
    _dense_tower,
    _ks,
    _median_in,
    _tip_floor_index,
    _zero_mask,
)


def tower_point(frame: AnyFrame) -> AnyFrame:
    """Per-row tower-tip point estimate over the sample axis → a `(N, …, 1)` frame.

    The median of the ``tip_mass`` floor's samples (``0`` when the zero atom dominates,
    by density); if the optional ``zero_cutoff`` is set, ``max <= cutoff`` rows are
    forced to ``0`` (off by default — C-45). Returns the same frame type as ``frame``.
    Tunables (``tip_mass``, grid, ``zero_cutoff``, row-block) come from ``config``.
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    ks = _ks(s)
    t = _tip_floor_index(s)
    block_rows = int(config.get("row_block"))
    flat = np.ascontiguousarray(values).reshape(-1, s)

    def _block(block: NDArray[np.float32]) -> NDArray[np.float32]:
        srt = np.sort(block, axis=-1)
        tower = _dense_tower(srt, ks)
        tip = _median_in(srt, tower[:, t, 0], tower[:, t, 1])
        return np.asarray(
            np.where(_zero_mask(block), np.float32(0.0), tip), dtype=np.float32
        )

    out = block_apply(flat, block_rows, _block)
    reduced = np.asarray(out, dtype=np.float32).reshape(lead)[..., np.newaxis]
    return rebuild(frame, reduced)
