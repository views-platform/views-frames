"""views-frames — the VIEWS platform data-contract layer (numpy only).

Immutable array+identifier value objects at the root of the platform dependency
DAG. Explicit re-exports only (no ``import *``) so the public API is statically
analyzable (README §6).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from views_frames.feature_frame import FeatureFrame
from views_frames.index import SpatioTemporalIndex
from views_frames.metadata import FrameMetadata
from views_frames.prediction_frame import PredictionFrame
from views_frames.protocols import (
    Frame,
    Persistable,
    Sampled,
    SpatioTemporalIndexed,
)
from views_frames.spatial_level import SpatialLevel
from views_frames.target_frame import TargetFrame

__all__ = [
    "FeatureFrame",
    "Frame",
    "FrameMetadata",
    "Persistable",
    "PredictionFrame",
    "Sampled",
    "SpatialLevel",
    "SpatioTemporalIndex",
    "SpatioTemporalIndexed",
    "TargetFrame",
]

try:
    __version__ = version("views-frames")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
