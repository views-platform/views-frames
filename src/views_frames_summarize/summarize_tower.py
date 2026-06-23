"""The single-pass coherent posterior summary (ADR-019).

`summarize_tower` is the dashboard hot path: it sorts each row-block **once** and builds
the canonical tower **once**, deriving the tower-tip point, the pinned nested HDIs, and
the bimodality flag together. It returns exactly what the three composable functions
(`tower_point`, `hdi_tower`, `bimodality`) return — the bundle is purely an efficiency
collapse of the three, not a different computation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, rebuild
from views_frames_summarize.bimodality import _bimodal_block
from views_frames_summarize.tower import (
    _CANONICAL_FLOORS,
    _dense_tower,
    _ks,
    _pin,
    _tip,
    _zero_mask,
)


class TowerSummary(NamedTuple):
    """The coherent summary of a frame's posteriors over the sample axis.

    Attributes:
        point: ``(N, …, 1)`` frame — the tower-tip point estimate.
        intervals: ``(N, …, M, 2)`` array — nested HDIs at the pinned masses.
        bimodal: ``(N, …, 1)`` array — the per-row bimodality flag (0/1).
        masses: ``(M,)`` array — the canonical floors the requested masses pinned to.
    """

    point: AnyFrame
    intervals: NDArray[np.float32]
    bimodal: NDArray[np.float32]
    masses: NDArray[np.float32]


def summarize_tower(
    frame: AnyFrame,
    masses: Sequence[float] = (0.5, 0.9, 0.99),
    *,
    bins: int = 16,
    prominence: float = 0.40,
    min_mass: float = 0.15,
    block_rows: int = ROW_BLOCK,
) -> TowerSummary:
    """Point + nested HDIs + bimodality flag in one sort-once pass → `TowerSummary`."""
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    ks = _ks(s)
    pin = _pin(masses)
    k0 = int(ks[0])
    flat = np.ascontiguousarray(values).reshape(-1, s)
    rows = flat.shape[0]

    point_flat = np.empty(rows, dtype=np.float32)
    intervals_flat = np.empty((rows, pin.shape[0], 2), dtype=np.float32)
    bimodal_flat = np.empty(rows, dtype=np.float32)

    for start in range(0, rows, block_rows):
        block = flat[start : start + block_rows]
        srt = np.sort(block, axis=-1)
        zero = _zero_mask(block)

        sel = _dense_tower(srt, ks)[:, pin, :]
        sel[zero] = 0.0
        tip = np.where(zero, np.float32(0.0), _tip(srt, k0))

        stop = start + block.shape[0]
        point_flat[start:stop] = tip
        intervals_flat[start:stop] = sel
        bimodal_flat[start:stop] = _bimodal_block(block, bins, prominence, min_mass)

    point = rebuild(frame, point_flat.reshape(lead)[..., np.newaxis])
    intervals = intervals_flat.reshape(*lead, pin.shape[0], 2)
    bimodal = bimodal_flat.reshape(lead)[..., np.newaxis]
    pinned = _CANONICAL_FLOORS[pin].astype(np.float32)
    return TowerSummary(
        point=point, intervals=intervals, bimodal=bimodal, masses=pinned
    )
