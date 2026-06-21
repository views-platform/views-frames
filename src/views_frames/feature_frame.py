"""`FeatureFrame` — model inputs (X): ``y_features (N, F, S)`` float32.

A sibling frame (no shared base; ADR-011 Option C). Relocated from
views-datafactory. The sample axis is **always explicit** (ADR-012): legacy 2D
``(N, F)`` arrays are lifted to ``(N, F, 1)`` only through the explicit
:meth:`from_2d` shim. Carries ``feature_names`` and a typed metadata header
(ADR-013). ``from_grid`` is **not** here — it stays in views-datafactory.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from views_frames._typing import IntArray
from views_frames._validation import coerce_values, validate_values
from views_frames.index import SpatioTemporalIndex
from views_frames.io import npz
from views_frames.metadata import FrameMetadata
from views_frames.spatial_level import SpatialLevel


class FeatureFrame:
    """Immutable model-input frame: ``(N, F, S)`` float32 + index + feature names."""

    def __init__(
        self,
        y_features: object,
        index: SpatioTemporalIndex,
        feature_names: list[str],
        metadata: FrameMetadata | None = None,
    ) -> None:
        values = coerce_values(y_features)
        validate_values(values)
        if values.ndim != 3:
            raise ValueError(
                "FeatureFrame y_features must be 3D (N, F, S) with an explicit "
                f"trailing sample axis (ADR-012), got ndim={values.ndim}. "
                "Use FeatureFrame.from_2d to lift a legacy (N, F) array."
            )
        if values.shape[0] != index.n_rows:
            raise ValueError(
                f"y_features has {values.shape[0]} rows but index has {index.n_rows}"
            )
        if len(feature_names) != values.shape[1]:
            raise ValueError(
                f"feature_names length ({len(feature_names)}) must match the "
                f"feature axis ({values.shape[1]})"
            )
        self._values = values
        self._index = index
        self._feature_names = list(feature_names)
        self._metadata = metadata if metadata is not None else FrameMetadata()

    @classmethod
    def from_2d(
        cls,
        y_features_2d: object,
        index: SpatioTemporalIndex,
        feature_names: list[str],
        metadata: FrameMetadata | None = None,
    ) -> FeatureFrame:
        """Lift a legacy 2D ``(N, F)`` array to ``(N, F, 1)`` (deprecated shim)."""
        arr = coerce_values(y_features_2d)
        if arr.ndim != 2:
            raise ValueError(f"from_2d expects a 2D (N, F) array, got ndim={arr.ndim}")
        return cls(arr[:, :, np.newaxis], index, feature_names, metadata)

    # ---- core surface -------------------------------------------------------

    @property
    def values(self) -> NDArray[np.float32]:
        """The ``(N, F, S)`` float32 value array."""
        return self._values

    @property
    def index(self) -> SpatioTemporalIndex:
        """The spatiotemporal row index."""
        return self._index

    @property
    def feature_names(self) -> list[str]:
        """The feature/channel names (length ``F``)."""
        return list(self._feature_names)

    @property
    def metadata(self) -> FrameMetadata:
        """The typed provenance header."""
        return self._metadata

    @property
    def n_rows(self) -> int:
        """Number of rows ``N``."""
        return int(self._values.shape[0])

    @property
    def n_features(self) -> int:
        """Number of features ``F``."""
        return int(self._values.shape[1])

    @property
    def identifiers(self) -> dict[str, IntArray]:
        """The integer identifier arrays from the index."""
        return self._index.identifiers

    @property
    def sample_count(self) -> int:
        """Size of the trailing sample axis ``S``."""
        return int(self._values.shape[-1])

    @property
    def is_sample(self) -> bool:
        """True iff ``sample_count > 1``."""
        return self.sample_count > 1

    # ---- operations ---------------------------------------------------------

    def with_metadata(self, metadata: FrameMetadata) -> FeatureFrame:
        """Return a new frame with replaced metadata, **sharing** the values buffer."""
        new = FeatureFrame.__new__(FeatureFrame)
        new._values = self._values
        new._index = self._index
        new._feature_names = self._feature_names
        new._metadata = metadata
        return new

    def select(self, indexer: IntArray | NDArray[np.bool_]) -> FeatureFrame:
        """A new frame of the rows at integer positions **or** a boolean mask.

        Rows are selected by numpy fancy indexing — an integer array reorders or
        repeats, a boolean mask filters. ``feature_names`` and metadata are
        preserved; the selection **copies**. An empty selection yields an empty
        frame.
        """
        return FeatureFrame(
            self._values[indexer],
            self._index.select(indexer),
            self._feature_names,
            self._metadata,
        )

    def reindex(self, other: SpatioTemporalIndex) -> FeatureFrame:
        """Align this frame to ``other``'s rows, returning a new frame.

        Fails loud unless this frame's index is a **superset** of ``other``. The
        frame-level companion to the index's ``reindex``/``searchsorted``.
        """
        if not self._index.is_superset_of(other):
            raise ValueError(
                "reindex requires this frame's index to be a superset of `other`; "
                "some target rows are absent"
            )
        return self.select(self._index.searchsorted(other))

    # ---- persistence --------------------------------------------------------

    def save(self, directory: Path | str) -> None:
        """Serialize to ``directory`` (incl. ``feature_names`` + metadata header)."""
        npz.save(
            directory,
            values=self._values,
            time=self._index.time,
            unit=self._index.unit,
            level=self._index.level.value,
            metadata=self._metadata.to_dict(),
            feature_names=self._feature_names,
        )

    @classmethod
    def load(cls, directory: Path | str, mmap: bool = False) -> FeatureFrame:
        """Deserialize a frame from ``directory``; ``mmap`` propagates."""
        state = npz.load(directory, mmap=mmap)
        index = SpatioTemporalIndex(
            time=state["time"],
            unit=state["unit"],
            level=SpatialLevel(state["level"]),
        )
        feature_names = state["feature_names"]
        if feature_names is None:
            raise ValueError("saved FeatureFrame is missing feature_names")
        return cls(
            state["values"],
            index,
            feature_names,
            FrameMetadata.from_dict(state["metadata"]),
        )
