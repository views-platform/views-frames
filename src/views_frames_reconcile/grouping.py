"""Reconcile a pgm `PredictionFrame` to cm country totals (epic #31, story #34).

The heart of the migration: for each `(time, country)`, scale that country's grid
cells so their per-draw sum matches the country forecast, using the parity-proven
leaf `reconcile_proportional` (PR #30). Grid rows are labelled by country with
views-frames `cross_level_align` — the sanctioned cm↔pgm primitive, which fails
loud if any grid row lacks a country (mirrors the original's "valid countries"
guard). De-mutated: returns a **new** pgm frame (C-184); the input is untouched.

numpy + views-frames only. The loop is over `(time, country)` groups (a small
number), not over rows; each group call is fully vectorised over cells × samples.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame, SpatialLevel

from views_frames_reconcile.proportional import reconcile_proportional


def reconcile_pgm_to_cm(
    pgm_frame: PredictionFrame,
    cm_frame: PredictionFrame,
    map_keys: NDArray[np.integer] | object,
    map_vals: NDArray[np.integer] | object,
) -> PredictionFrame:
    """Return a new pgm `PredictionFrame` reconciled to ``cm_frame``'s totals.

    Args:
        pgm_frame: grid forecasts at PGM level, values ``(N_pg, S)``.
        cm_frame: country forecasts at CM level, values ``(N_cm, S)``.
        map_keys: ``(M, 2)`` int ``(time, priogrid_gid)`` covering every pgm row.
        map_vals: ``(M,)`` int ``country_id`` for each key (injected; geography is
            never embedded here — views-frames ADR-014).

    Returns:
        A new pgm `PredictionFrame` (same index/metadata as ``pgm_frame``) whose
        cells sum, per draw, to the country forecast — except all-zero country
        draws, which stay zero (the leaf's documented edge case).

    Raises:
        ValueError: a grid row has no country mapping (raised by
            ``cross_level_align``), or a ``(time, country)`` group has no matching
            country forecast in ``cm_frame``.
    """
    # 1. Label every grid row with its country (cm-level units); fails loud if a
    #    row's (time, priogrid) is absent from the injected mapping.
    cm_units = pgm_frame.index.cross_level_align_arrays(
        np.asarray(map_keys), np.asarray(map_vals), SpatialLevel.CM
    ).unit  # (N_pg,)
    pg_time = pgm_frame.index.time

    # 2. (time, country) -> row position in the country frame.
    cm_time, cm_unit, cm_vals = cm_frame.index.time, cm_frame.index.unit, cm_frame.values
    cm_pos = {(int(cm_time[j]), int(cm_unit[j])): j for j in range(cm_frame.n_rows)}

    # 3. Group grid rows by (time, country) and reconcile each group with the leaf.
    #    Group-by-sort: a single argsort lays the rows out contiguously per group
    #    (O(N log N), one index array) — no per-group full-array scan — so it
    #    scales to the full grid (register C-38). Group iteration order is
    #    irrelevant: each group writes only its own rows.
    pg_vals = pgm_frame.values
    out = np.empty_like(pg_vals)
    group_key = np.stack([pg_time, cm_units], axis=1)  # (N_pg, 2)
    unique_groups, inverse, counts = np.unique(
        group_key, axis=0, return_inverse=True, return_counts=True
    )
    inverse = np.asarray(inverse).reshape(-1)
    order = np.argsort(inverse, kind="stable")  # rows grouped contiguously by group
    bounds = np.concatenate(([0], np.cumsum(counts)))  # group gi -> order[bounds[gi]:bounds[gi+1]]

    for gi in range(unique_groups.shape[0]):
        t, c = int(unique_groups[gi, 0]), int(unique_groups[gi, 1])
        if (t, c) not in cm_pos:
            raise ValueError(
                f"grid group (time={t}, country={c}) has no country forecast in cm_frame"
            )
        rows = order[bounds[gi]:bounds[gi + 1]]
        country_total = cm_vals[cm_pos[(t, c)]]  # (S,)
        # leaf convention: grid is (samples, cells); our frame slice is (cells, samples)
        scaled = reconcile_proportional(pg_vals[rows].T, country_total)  # (S, n_cells)
        out[rows] = scaled.T  # back to (n_cells, S)

    return PredictionFrame(out, pgm_frame.index, pgm_frame.metadata)
