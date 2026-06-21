"""Conservation-correct cross-level aggregation of sample distributions (ADR-017).

Sum the per-cell sample arrays across the cells of each coarser unit **preserving the
sample index** (joint sampling), so the aggregated uncertainty is correct —
``HDI(sum) != sum(HDI)`` (the faoapi C-70 concern). The ``(time, unit) ->
target_unit`` mapping is **injected** by the caller (the same map the leaf's
``cross_level_align`` takes — time-varying, register C-20); no geography is
embedded here.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from views_frames import SpatialLevel, SpatioTemporalIndex
from views_frames_summarize._common import AnyFrame, rebuild


def aggregate_distributions(
    frame: AnyFrame,
    mapping: Mapping[tuple[int, int], int],
    target_level: SpatialLevel,
) -> AnyFrame:
    """Aggregate a frame's sample distributions up to ``target_level``.

    Rows are grouped by ``(time, target_unit)`` — where ``target_unit`` comes from the
    injected ``(time, unit) -> target_unit`` ``mapping`` via the leaf's
    ``cross_level_align`` — and the sample arrays are summed **element-wise across the
    constituent cells** (joint sampling). Time is preserved.

    Raises:
        ValueError: ``mapping`` is missing/empty, is not keyed by ``(time, unit)``
            pairs, or a row's ``(time, unit)`` has no entry (inherited from
            ``cross_level_align`` — the leaf never guesses a mapping).
    """
    remapped = frame.index.cross_level_align(mapping, target_level)
    keys = np.stack(
        [remapped.time.astype(np.int64), remapped.unit.astype(np.int64)], axis=1
    )
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    inverse = np.asarray(inverse).reshape(-1)

    agg = np.zeros((unique.shape[0], *frame.values.shape[1:]), dtype=np.float32)
    np.add.at(agg, inverse, frame.values)

    agg_index = SpatioTemporalIndex(
        time=np.asarray(unique[:, 0], dtype=np.int64),
        unit=np.asarray(unique[:, 1], dtype=np.int64),
        level=target_level,
    )
    return rebuild(frame, agg, agg_index)
