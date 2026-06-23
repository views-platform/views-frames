"""The tower-tip point estimate (ADR-019) — a `(N, …, 1)` frame.

`tower_point` is the "most likely single value" we report to a consumer: the median of
the draws inside the **narrowest canonical floor** of the constrained-nested tower (the
tip), with the same raw-count zero short-circuit as the tower (`max(row) <= 1` → 0).

It is a *new* estimator, deliberately distinct from the frozen `map_estimate` (ADR-018):
`map_estimate` is a binned histogram mode with a zero-*mass*-fraction rule and a
lowest-index tie-break that is directionally biased on right-skewed, zero-inflated,
low-sample posteriors (register C-32). The tower tip is unbinned — it reads the median
of an actual shortest-interval window — so it carries no histogram tie-break. On a
genuinely multi-peaked row the tip is, like any single point, ambiguous; pair it with
`bimodality` to detect that case rather than collapse it silently.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, block_apply, rebuild
from views_frames_summarize.tower import _CANONICAL_FLOORS, _tip, _zero_mask


def tower_point(frame: AnyFrame, *, block_rows: int = ROW_BLOCK) -> AnyFrame:
    """Per-row tower-tip point estimate over the sample axis → a `(N, …, 1)` frame.

    The median of the narrowest canonical floor's samples; ``0.0`` for quiet rows
    (every draw ``<= 1``). Returns a frame of the same type as ``frame``.
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    k0 = int(np.floor(_CANONICAL_FLOORS[0] * s))
    flat = np.ascontiguousarray(values).reshape(-1, s)

    def _block(block: NDArray[np.float32]) -> NDArray[np.float32]:
        srt = np.sort(block, axis=-1)
        tip = _tip(srt, k0)
        return np.asarray(
            np.where(_zero_mask(block), np.float32(0.0), tip), dtype=np.float32
        )

    out = block_apply(flat, block_rows, _block)
    reduced = np.asarray(out, dtype=np.float32).reshape(lead)[..., np.newaxis]
    return rebuild(frame, reduced)
