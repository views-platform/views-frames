"""`FeatureFrame` — model inputs (X): ``y_features (N, F, S)`` float32.

A sibling frame (no shared base; ADR-011 Option C). Carries `feature_names` and a
typed `metadata` header (ADR-013). The trailing sample axis is always explicit
(`S >= 1`; ADR-012). STUB — implementation lands in Epic 2.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames.index import SpatioTemporalIndex


class FeatureFrame:
    """Immutable model-input frame: ``(N, F, S)`` float32 + identifiers. STUB."""

    def __init__(
        self,
        y_features: NDArray[np.float32],
        index: SpatioTemporalIndex,
        feature_names: list[str],
    ) -> None:
        raise NotImplementedError(
            "views-frames is a stub skeleton (Epic 1); FeatureFrame lands in Epic 2"
        )
