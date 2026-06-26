"""Array → `PredictionFrame` adapters for reconciliation (epic #31, story #33).

Reconciliation works on views-frames `PredictionFrame`s at two spatial levels:
country (`cm`) and PRIO-GRID (`pgm`). Both are built the same way from
`(time, unit, values)` arrays — only the `SpatialLevel` and the unit identifier
(`country_id` vs `priogrid_gid`) differ. Predictions here carry a real posterior
sample axis, so values are `(N, S)` with `S >= 1`.

This is the reconciliation package's **own** I/O: it differs from the unfao
delivery adapters (`unfao/frames.py`), which wrap pandas *scalar* columns as
`(N, 1)` point frames — so per CRP they are not forced together. numpy +
views-frames only; no torch, no pandas.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from views_frames import (
    FrameMetadata,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
)


def prediction_frame_from_arrays(
    time: NDArray[np.integer[Any]] | object,
    unit: NDArray[np.integer[Any]] | object,
    values: NDArray[np.floating[Any]] | object,
    *,
    level: SpatialLevel,
    metadata: FrameMetadata | None = None,
) -> PredictionFrame:
    """Build a `PredictionFrame` from `(time, unit, values)` at ``level``.

    Args:
        time: 1-D integer array, length ``N`` (``month_id``).
        unit: 1-D integer array, length ``N`` — ``country_id`` for
            ``SpatialLevel.CM``, ``priogrid_gid`` for ``SpatialLevel.PGM``.
        values: ``(N, S)`` float32-coercible array of posterior samples.
        level: the frame's spatial level.

    Returns:
        A `PredictionFrame` of shape ``(N, S)`` at ``level``. The values buffer
        is reused without copy when already float32 (views-frames C-07); the
        input arrays are never mutated.

    Raises:
        ValueError: ``values`` is not 2-D, or ``time``/``unit`` are not 1-D of
            length ``N``.
    """
    time_arr = np.asarray(time, dtype=np.int64)
    unit_arr = np.asarray(unit, dtype=np.int64)
    vals = np.asarray(values, dtype=np.float32)

    if vals.ndim != 2:
        raise ValueError(f"values must be 2-D (N, S); got ndim={vals.ndim}")
    if time_arr.shape != (vals.shape[0],) or unit_arr.shape != (vals.shape[0],):
        raise ValueError(
            f"time {time_arr.shape} and unit {unit_arr.shape} must both be 1-D "
            f"of length N={vals.shape[0]}"
        )

    index = SpatioTemporalIndex(time=time_arr, unit=unit_arr, level=level)
    return PredictionFrame(vals, index, metadata)
