"""Published protocols — the abstract surface consumers type against.

Consumers depend on these `Protocol`s (DIP/ISP, ADR-009, README §5); a concrete
frame is an implementation detail. The surface is segregated so no consumer
depends on methods it does not use.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class SpatioTemporalIndexed(Protocol):
    """What a reconciler / aligner needs: the row identity surface."""

    @property
    def n_rows(self) -> int:
        """Number of rows (the first axis length)."""
        ...

    @property
    def identifiers(self) -> dict[str, NDArray[np.integer]]:
        """The integer identifier arrays, keyed by name (e.g. ``time``, ``unit``)."""
        ...


@runtime_checkable
class Sampled(Protocol):
    """What an ensemble / aggregator needs: the trailing sample axis (ADR-012)."""

    @property
    def sample_count(self) -> int:
        """Size of the trailing sample axis ``S`` (always ``>= 1``)."""
        ...

    @property
    def is_sample(self) -> bool:
        """True iff ``sample_count > 1``."""
        ...

    def collapse(self, method: str = "arithmetic_mean") -> Sampled:
        """Reduce the trailing sample axis, returning a new frame with ``S == 1``."""
        ...


@runtime_checkable
class Persistable(Protocol):
    """What I/O needs — and only I/O."""

    def save(self, directory: str) -> None:
        """Serialize this frame to ``directory``."""
        ...

    @classmethod
    def load(cls, directory: str, mmap: bool = False) -> Persistable:
        """Deserialize a frame from ``directory``; ``mmap`` propagates (C-07)."""
        ...


@runtime_checkable
class Frame(SpatioTemporalIndexed, Protocol):
    """The small composition the math layer needs: values + index + n_rows."""

    @property
    def values(self) -> NDArray[np.float32]:
        """The contiguous ``float32`` value array (first axis = rows)."""
        ...
