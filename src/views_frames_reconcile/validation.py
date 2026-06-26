"""Fail-loud validation for reconciliation inputs (epic #31, story #35).

Ports views-reporting `ReconciliationModule.__init__`'s guards to frames-native
checks, run before any work. SRP: small, independently testable helpers — not
buried in the orchestrator. The original's intents map as:

  - dataset type checks            -> spatial-level guard (cm@CM, pgm@PGM)
  - same time steps + exact overlap -> identical set of time values
  - (per-draw scaling needs it)     -> equal `sample_count`
  - valid countries                 -> every (time, country) the grid maps to has
                                       a country forecast in the cm frame

The original's "different time units" (e.g. month_id vs year_id) check is
subsumed by the level guard; per-target intersection is handled by the
orchestrator, since frames here are single-target.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame, SpatialLevel


def validate_reconciliation_inputs(
    cm_frame: PredictionFrame,
    pgm_frame: PredictionFrame,
    map_keys: NDArray[np.integer] | object,
    map_vals: NDArray[np.integer] | object,
) -> None:
    """Raise ``ValueError`` if the reconciliation inputs are inconsistent.

    Checks spatial levels, sample-count alignment, identical time coverage, and
    that every country the grid maps to has a forecast in ``cm_frame``.
    """
    if cm_frame.index.level is not SpatialLevel.CM:
        raise ValueError(
            f"country frame must be at SpatialLevel.CM, got {cm_frame.index.level}"
        )
    if pgm_frame.index.level is not SpatialLevel.PGM:
        raise ValueError(
            f"grid frame must be at SpatialLevel.PGM, got {pgm_frame.index.level}"
        )
    if cm_frame.sample_count != pgm_frame.sample_count:
        raise ValueError(
            f"sample-count mismatch: cm has {cm_frame.sample_count}, "
            f"pgm has {pgm_frame.sample_count}"
        )

    cm_times = {int(t) for t in np.unique(cm_frame.index.time)}
    pg_times = {int(t) for t in np.unique(pgm_frame.index.time)}
    if cm_times != pg_times:
        raise ValueError(
            "cm and pgm cover different time steps: "
            f"cm-only={sorted(cm_times - pg_times)}, "
            f"pgm-only={sorted(pg_times - cm_times)}"
        )

    # Valid countries: every (time, country) the grid maps to must have a forecast.
    cm_units = pgm_frame.index.cross_level_align_arrays(
        np.asarray(map_keys), np.asarray(map_vals), SpatialLevel.CM
    ).unit
    needed = {
        (int(t), int(c))
        for t, c in zip(pgm_frame.index.time, cm_units, strict=True)
    }
    have = {
        (int(t), int(c))
        for t, c in zip(cm_frame.index.time, cm_frame.index.unit, strict=True)
    }
    missing = needed - have
    if missing:
        raise ValueError(
            f"{len(missing)} grid group(s) have no country forecast in cm_frame, "
            f"e.g. {sorted(missing)[:5]}"
        )
