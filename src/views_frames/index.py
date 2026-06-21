"""`SpatioTemporalIndex` — the genuinely-reused alignment primitive.

`{time, unit, level}` integer arrays plus **same-level** pure-numpy alignment
(intersect / align / reindex / searchsorted). Cross-level (cm↔pgm) alignment is
exposed as a protocol whose mapping is **injected by the consumer**, never
embedded or fetched here (ADR-014, register C-14).

STUB — implementation lands in Epic 2.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames.spatial_level import SpatialLevel


class SpatioTemporalIndex:
    """An immutable ``{time, unit, level}`` row index with same-level alignment.

    STUB — constructing one raises until Epic 2 implements it.
    """

    def __init__(
        self,
        time: NDArray[np.integer],
        unit: NDArray[np.integer],
        level: SpatialLevel,
    ) -> None:
        raise NotImplementedError(
            "views-frames is a stub skeleton (Epic 1); "
            "SpatioTemporalIndex lands in Epic 2"
        )
