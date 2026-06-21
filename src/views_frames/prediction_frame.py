"""`PredictionFrame` — model outputs (ŷ samples): ``y_pred (N, S)`` float32.

A sibling frame (no shared base; ADR-011 Option C). Relocated from
views-pipeline-core; its identifier validation is rewritten **numpy-only** (the
original imports pandas — this is *not* a verbatim move; ADR-012, register C-17).
The trailing sample axis is always explicit (`S >= 1`; ADR-012). STUB —
implementation lands in Epic 2.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames.index import SpatioTemporalIndex


class PredictionFrame:
    """Immutable model-output frame: ``(N, S)`` float32 + identifiers. STUB."""

    def __init__(
        self,
        y_pred: NDArray[np.float32],
        index: SpatioTemporalIndex,
    ) -> None:
        raise NotImplementedError(
            "views-frames is a stub skeleton (Epic 1); PredictionFrame lands in Epic 2"
        )
