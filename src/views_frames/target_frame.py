"""`TargetFrame` — observed actuals (ground truth): ``y_true (N, 1)`` float32.

A sibling frame (no shared base; ADR-011 Option C). Structurally a
`PredictionFrame` with ``S == 1`` (the trailing sample axis is explicit;
ADR-012). Makes the evaluation boundary array-native. STUB — implementation
lands in Epic 2.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames.index import SpatioTemporalIndex


class TargetFrame:
    """Immutable observed-actuals frame: ``(N, 1)`` float32 + identifiers. STUB."""

    def __init__(
        self,
        y_true: NDArray[np.float32],
        index: SpatioTemporalIndex,
    ) -> None:
        raise NotImplementedError(
            "views-frames is a stub skeleton (Epic 1); TargetFrame lands in Epic 2"
        )
