"""`PredictionFrame` — model outputs (ŷ samples): ``y_pred (N, S)`` float32.

A sibling frame (no shared base; ADR-011 Option C). Relocated from
views-pipeline-core and rewritten **numpy-only** — the original imports pandas
(``pd.isna``); here identifier validation is the integer-dtype check in
``_validation`` (register C-17). The sample axis is always explicit (`S >= 1`;
ADR-012).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from views_frames._validation import coerce_values, validate_values
from views_frames.index import SpatioTemporalIndex
from views_frames.io import npz
from views_frames.metadata import FrameMetadata
from views_frames.spatial_level import SpatialLevel

SUPPORTED_AGGREGATE_METHODS = ("arithmetic_mean",)


class PredictionFrame:
    """Immutable model-output frame: ``(N, S)`` float32 + a spatiotemporal index."""

    def __init__(
        self,
        y_pred: object,
        index: SpatioTemporalIndex,
        metadata: FrameMetadata | None = None,
    ) -> None:
        values = coerce_values(y_pred)
        validate_values(values)
        if values.ndim != 2:
            raise ValueError(
                f"PredictionFrame y_pred must be 2D (N, S), got ndim={values.ndim}"
            )
        if values.shape[0] != index.n_rows:
            raise ValueError(
                f"y_pred has {values.shape[0]} rows but index has {index.n_rows}"
            )
        self._values = values
        self._index = index
        self._metadata = metadata if metadata is not None else FrameMetadata()

    # ---- core surface -------------------------------------------------------

    @property
    def values(self) -> NDArray[np.float32]:
        """The ``(N, S)`` float32 value array."""
        return self._values

    @property
    def index(self) -> SpatioTemporalIndex:
        """The spatiotemporal row index."""
        return self._index

    @property
    def metadata(self) -> FrameMetadata:
        """The typed provenance header."""
        return self._metadata

    @property
    def n_rows(self) -> int:
        """Number of rows ``N``."""
        return int(self._values.shape[0])

    @property
    def identifiers(self) -> dict[str, NDArray[np.integer]]:
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

    def collapse(self, method: str = "arithmetic_mean") -> PredictionFrame:
        """Reduce the trailing sample axis, returning a new ``(N, 1)`` frame."""
        if method not in SUPPORTED_AGGREGATE_METHODS:
            raise ValueError(
                f"Unknown aggregate method '{method}'. "
                f"Supported: {sorted(SUPPORTED_AGGREGATE_METHODS)}"
            )
        collapsed = self._values.mean(axis=-1, keepdims=True)
        return PredictionFrame(collapsed, self._index, self._metadata)

    def with_metadata(self, metadata: FrameMetadata) -> PredictionFrame:
        """Return a new frame with replaced metadata, **sharing** the values buffer."""
        new = PredictionFrame.__new__(PredictionFrame)
        new._values = self._values
        new._index = self._index
        new._metadata = metadata
        return new

    # ---- persistence --------------------------------------------------------

    def save(self, directory: Path | str) -> None:
        """Serialize to ``directory`` (npy + npz + header)."""
        npz.save(
            directory,
            values=self._values,
            time=self._index.time,
            unit=self._index.unit,
            level=self._index.level.value,
            metadata=self._metadata.to_dict(),
        )

    @classmethod
    def load(cls, directory: Path | str, mmap: bool = False) -> PredictionFrame:
        """Deserialize a frame from ``directory``; ``mmap`` propagates."""
        state = npz.load(directory, mmap=mmap)
        index = SpatioTemporalIndex(
            time=state["time"],
            unit=state["unit"],
            level=SpatialLevel(state["level"]),
        )
        return cls(state["values"], index, FrameMetadata.from_dict(state["metadata"]))
