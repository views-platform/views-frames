"""`TargetFrame` — observed actuals (ground truth): ``y_true (N, 1)`` float32.

A sibling frame (no shared base; ADR-011 Option C). Structurally a
`PredictionFrame` with ``S == 1`` (the trailing sample axis is explicit; ADR-012).
Makes the evaluation boundary array-native. ``is_sample`` is always ``False``.
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


class TargetFrame:
    """Immutable observed-actuals frame: ``(N, 1)`` float32 + a spatiotemporal index."""

    def __init__(
        self,
        y_true: object,
        index: SpatioTemporalIndex,
        metadata: FrameMetadata | None = None,
    ) -> None:
        values = coerce_values(y_true)
        validate_values(values)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError(
                "TargetFrame y_true must have shape (N, 1) with an explicit "
                f"trailing axis (ADR-012), got shape {values.shape}"
            )
        if values.shape[0] != index.n_rows:
            raise ValueError(
                f"y_true has {values.shape[0]} rows but index has {index.n_rows}"
            )
        self._values = values
        self._index = index
        self._metadata = metadata if metadata is not None else FrameMetadata()

    # ---- core surface -------------------------------------------------------

    @property
    def values(self) -> NDArray[np.float32]:
        """The ``(N, 1)`` float32 value array."""
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
    def identifiers(self) -> dict[str, IntArray]:
        """The integer identifier arrays from the index."""
        return self._index.identifiers

    @property
    def sample_count(self) -> int:
        """Always ``1`` for a target frame."""
        return 1

    @property
    def is_sample(self) -> bool:
        """Always ``False`` — a target carries a single realized value."""
        return False

    def with_metadata(self, metadata: FrameMetadata) -> TargetFrame:
        """Return a new frame with replaced metadata, **sharing** the values buffer."""
        new = TargetFrame.__new__(TargetFrame)
        new._values = self._values
        new._index = self._index
        new._metadata = metadata
        return new

    def select(self, indexer: IntArray | NDArray[np.bool_]) -> TargetFrame:
        """A new frame of the rows at integer positions **or** a boolean mask.

        Rows are selected by numpy fancy indexing — an integer array reorders or
        repeats, a boolean mask filters. Metadata is preserved; the selection
        **copies**. An empty selection yields an empty frame.
        """
        return TargetFrame(
            self._values[indexer], self._index.select(indexer), self._metadata
        )

    def reindex(self, other: SpatioTemporalIndex) -> TargetFrame:
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
    def load(cls, directory: Path | str, mmap: bool = False) -> TargetFrame:
        """Deserialize a frame from ``directory``; ``mmap`` propagates."""
        state = npz.load(directory, mmap=mmap)
        index = SpatioTemporalIndex(
            time=state["time"],
            unit=state["unit"],
            level=SpatialLevel(state["level"]),
        )
        return cls(state["values"], index, FrameMetadata.from_dict(state["metadata"]))
