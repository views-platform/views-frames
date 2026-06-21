"""`SpatialLevel` — the cm/pgm identifier vocabulary (ADR-015).

Labels only: `entity_column` + **time-first** `index_names`. This object never
carries the cross-level mapping (ADR-014), unit values, ranges, or the grid
backbone. stdlib only (no numpy, no domain data).

Relocated from `views-pipeline-core/.../domain/spatial.py` with the two known
defects *fixed, not ported* (ADR-015, register C-18): the index tuple is
time-first ``(month_id, entity)`` (was entity-first, C-65), and the priogrid
entity name is consistent (`priogrid_id` everywhere).
"""

from __future__ import annotations

from enum import Enum


class SpatialLevel(Enum):
    """Spatial level of a frame's rows: country-month or PRIO-GRID-month.

    Carries the level's identifier vocabulary and nothing else.
    """

    CM = "cm"
    PGM = "pgm"

    @property
    def entity_column(self) -> str:
        """The unit identifier column name for this level."""
        return _ENTITY_COLUMN[self]

    @property
    def index_names(self) -> tuple[str, str]:
        """The ``(time, entity)`` index column names — **time-first** (ADR-015)."""
        return ("month_id", self.entity_column)


_ENTITY_COLUMN: dict[SpatialLevel, str] = {
    SpatialLevel.CM: "country_id",
    SpatialLevel.PGM: "priogrid_id",
}
