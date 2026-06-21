"""`SpatioTemporalIndex` — the genuinely-reused alignment primitive.

`{time, unit, level}` integer arrays plus **same-level** pure-numpy alignment
(intersect / reindex / is_superset_of / argsort / searchsorted). Cross-level
(cm↔pgm) alignment is exposed via `cross_level_align`, whose mapping is
**injected by the consumer** and never embedded or fetched here (ADR-014,
register C-14).

The same-level join is the pure-numpy unwrap of the proven
`pd.Index.get_indexer` pattern in `views-faoapi/.../data/handlers.py`.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from views_frames._validation import validate_identifiers
from views_frames.spatial_level import SpatialLevel


class SpatioTemporalIndex:
    """An immutable ``{time, unit, level}`` row index with same-level alignment."""

    def __init__(
        self,
        time: NDArray[np.integer],
        unit: NDArray[np.integer],
        level: SpatialLevel,
    ) -> None:
        if not isinstance(level, SpatialLevel):
            raise TypeError(
                f"level must be a SpatialLevel, got {type(level).__name__}"
            )
        is_array = isinstance(time, np.ndarray) and time.ndim >= 1
        n = int(time.shape[0]) if is_array else -1
        validate_identifiers({"time": time, "unit": unit}, n_rows=n)
        # store as read-only views so the value object cannot be mutated in place
        self._time = np.ascontiguousarray(time)
        self._unit = np.ascontiguousarray(unit)
        self._time.setflags(write=False)
        self._unit.setflags(write=False)
        self._level = level

    # ---- core surface -------------------------------------------------------

    @property
    def time(self) -> NDArray[np.integer]:
        """The time identifier array (read-only)."""
        return self._time

    @property
    def unit(self) -> NDArray[np.integer]:
        """The unit identifier array (read-only)."""
        return self._unit

    @property
    def level(self) -> SpatialLevel:
        """The spatial level (cm/pgm) of these rows."""
        return self._level

    @property
    def n_rows(self) -> int:
        """Number of rows (the first axis length)."""
        return int(self._time.shape[0])

    @property
    def identifiers(self) -> dict[str, NDArray[np.integer]]:
        """The integer identifier arrays, keyed by name."""
        return {"time": self._time, "unit": self._unit}

    def __len__(self) -> int:
        return self.n_rows

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SpatioTemporalIndex):
            return NotImplemented
        return (
            self._level == other._level
            and np.array_equal(self._time, other._time)
            and np.array_equal(self._unit, other._unit)
        )

    def __hash__(self) -> int:  # value objects are immutable; hash by identity surface
        return hash((self._level, self._time.tobytes(), self._unit.tobytes()))

    # ---- internal key representation ---------------------------------------

    def _keys(self) -> NDArray[np.int64]:
        """A contiguous ``(N, 2)`` int64 ``(time, unit)`` key array."""
        return np.ascontiguousarray(
            np.stack([self._time.astype(np.int64), self._unit.astype(np.int64)], axis=1)
        )

    @staticmethod
    def _row_view(keys: NDArray[np.int64]) -> NDArray[np.void]:
        """View each ``(time, unit)`` row as a single void scalar for set ops."""
        return np.ascontiguousarray(keys).view(
            np.dtype((np.void, keys.dtype.itemsize * keys.shape[1]))
        ).reshape(-1)

    def _require_same_level(self, other: SpatioTemporalIndex) -> None:
        if self._level != other._level:
            raise ValueError(
                "same-level operation requires equal SpatialLevel; "
                f"got {self._level} and {other._level}. Use cross_level_align."
            )

    # ---- same-level alignment ----------------------------------------------

    def argsort(self) -> NDArray[np.intp]:
        """Positions that sort the rows by ``(time, unit)`` (time-major)."""
        return np.lexsort((self._unit, self._time))

    def searchsorted(self, other: SpatioTemporalIndex) -> NDArray[np.intp]:
        """For each row of ``other``, its position in ``self`` (-1 if absent).

        The pure-numpy analogue of ``pd.Index.get_indexer``: a same-level join.
        """
        self._require_same_level(other)
        self_rows = self._row_view(self._keys())
        other_rows = self._row_view(other._keys())
        order = np.argsort(self_rows, kind="stable")
        sorted_rows = self_rows[order]
        pos = np.searchsorted(sorted_rows, other_rows)
        pos = np.clip(pos, 0, len(sorted_rows) - 1)
        found = sorted_rows[pos] == other_rows
        result = np.where(found, order[pos], -1)
        return result.astype(np.intp)

    def reindex(self, other: SpatioTemporalIndex) -> NDArray[np.intp]:
        """Alias of :meth:`searchsorted` — positions to align ``self`` to ``other``."""
        return self.searchsorted(other)

    def is_superset_of(self, other: SpatioTemporalIndex) -> bool:
        """True iff every row of ``other`` is present in ``self`` (same level)."""
        self._require_same_level(other)
        self_rows = self._row_view(self._keys())
        other_rows = self._row_view(other._keys())
        return bool(np.isin(other_rows, self_rows).all())

    def intersect(self, other: SpatioTemporalIndex) -> SpatioTemporalIndex:
        """A new index of the rows present in **both** ``self`` and ``other``."""
        self._require_same_level(other)
        common = np.intersect1d(
            self._row_view(self._keys()), self._row_view(other._keys())
        )
        keys = common.view(np.int64).reshape(-1, 2)
        return SpatioTemporalIndex(
            time=keys[:, 0].copy(), unit=keys[:, 1].copy(), level=self._level
        )

    # ---- cross-level alignment (ADR-014) -----------------------------------

    def cross_level_align(
        self,
        mapping: Mapping[int, int],
        target_level: SpatialLevel,
    ) -> SpatioTemporalIndex:
        """Remap each row's ``unit`` to ``target_level`` using an injected mapping.

        The cross-level (cm↔pgm) join needs an external, time-varying
        ``unit -> target_unit`` mapping (e.g. ``priogrid_id -> country_id``). The
        leaf owns this **operation**; the **mapping is supplied by the caller** and
        is never embedded or fetched here (ADR-014). Time is preserved.

        Args:
            mapping: A ``{unit: target_unit}`` mapping injected by the consumer.
            target_level: The ``SpatialLevel`` of the produced index.

        Raises:
            ValueError: ``mapping`` is missing/empty, or a ``unit`` value has no
                entry in ``mapping`` (the leaf never guesses a mapping).
            TypeError: ``target_level`` is not a ``SpatialLevel``.
        """
        if not isinstance(target_level, SpatialLevel):
            got = type(target_level).__name__
            raise TypeError(f"target_level must be a SpatialLevel, got {got}")
        if mapping is None or len(mapping) == 0:
            raise ValueError(
                "cross_level_align requires an injected unit->target_unit mapping; "
                "the leaf never embeds or fetches it (ADR-014)."
            )
        try:
            mapped = np.array(
                [mapping[int(u)] for u in self._unit], dtype=self._unit.dtype
            )
        except KeyError as exc:
            raise ValueError(
                f"unit value {exc.args[0]} has no entry in the injected mapping"
            ) from exc
        return SpatioTemporalIndex(
            time=self._time.copy(), unit=mapped, level=target_level
        )
