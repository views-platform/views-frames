"""Donor fill: give an empty grid draw a pattern before it is scaled (ADR-030).

Scaling is multiplication, so ``reconcile_proportional`` cannot place a positive
country value on a draw whose grid cells are all zero. Before 3.0.0 that draw stayed
zero and the country's mass was lost (2.9–7.3% on the first production run, #283).

This pass runs **before** the unchanged scaling. Within each ``(time, country)`` group,
a draw that **needs filling** (country value > 0, no grid cell > 0) receives a copy of
the grid values of a **donor**: a draw of the same group that has grid mass, chosen
uniformly at random. The scaling then rescales it to the draw's own country value, so
the filled draw has exactly the donor's zero cells and proportions.

The random choice is reproducible: each group draws from
``numpy.random.default_rng([seed, time, country])``, so the result does not depend on
how a caller chunks its calls or on group order.

``proportional`` and ``grouping`` are not touched (CIC §11). The group-by-sort below
repeats ``grouping``'s on purpose (ADR-030 §Decision 6).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame, SpatialLevel


def fill_empty_draws(
    grid: NDArray[np.floating[Any]],
    country: NDArray[np.floating[Any]],
    rng: np.random.Generator,
) -> tuple[NDArray[np.floating[Any]], int]:
    """Fill the draws of one group whose grid is empty but whose country is positive.

    Args:
        grid: ``(S, n_cells)`` grid values of one ``(time, country)`` group.
        country: ``(S,)`` the country value of each draw.
        rng: the group's generator.

    Returns:
        ``(grid, n_filled)``. ``grid`` is the input object itself when nothing needed
        filling, otherwise a new array; the input is never modified.

    Raises:
        ValueError: a draw needs filling but no draw of the group has grid mass, so
            there is no pattern to borrow (ADR-030 §Decision 5).
    """
    has_mass = (grid > 0).any(axis=1)  # (S,)
    needs_fill = (country > 0) & ~has_mass
    n_filled = int(needs_fill.sum())
    if n_filled == 0:
        return grid, 0
    donors = np.flatnonzero(has_mass)
    if donors.size == 0:
        raise ValueError(
            f"cannot place the country value of {n_filled} of {grid.shape[0]} "
            "draw(s): the grid is zero in every cell of every draw, so there is no "
            "donor pattern to borrow. The country forecast has fatalities where the "
            "grid forecast has none at all (ADR-030)."
        )
    filled = np.array(grid, copy=True)
    filled[needs_fill] = grid[rng.choice(donors, size=n_filled)]
    return filled, n_filled


def fill_empty_grid_draws(
    pgm_frame: PredictionFrame,
    cm_frame: PredictionFrame,
    map_keys: NDArray[np.integer[Any]],
    map_vals: NDArray[np.integer[Any]],
    seed: int,
) -> tuple[PredictionFrame, int]:
    """Apply :func:`fill_empty_draws` to every ``(time, country)`` group of a pgm frame.

    ``cm_frame`` must already carry the grid's draw count (a point country is broadcast
    before this is called), and every grid group must have a country row
    (``validate_reconciliation_inputs`` guarantees both).

    Returns:
        ``(frame, n_filled)``: ``pgm_frame`` itself when nothing needed filling,
        otherwise a new frame with the same index and metadata; and the number of draws
        filled.

    Raises:
        ValueError: a ``(time, country)`` group needs filling and has no donor. Raised
            before any output is returned; the message names the time and country.
    """
    cm_units = pgm_frame.index.cross_level_align_arrays(
        map_keys, map_vals, SpatialLevel.CM
    ).unit
    pg_time = pgm_frame.index.time
    cm_vals = cm_frame.values
    cm_pos = {
        (int(t), int(u)): j
        for j, (t, u) in enumerate(
            zip(cm_frame.index.time, cm_frame.index.unit, strict=True)
        )
    }

    pg_vals = pgm_frame.values
    groups, inverse, counts = np.unique(
        np.stack([pg_time, cm_units], axis=1),
        axis=0,
        return_inverse=True,
        return_counts=True,
    )
    order = np.argsort(np.asarray(inverse).reshape(-1), kind="stable")
    bounds = np.concatenate(([0], np.cumsum(counts)))

    out: NDArray[Any] | None = None
    n_filled = 0
    for gi in range(groups.shape[0]):
        t, c = int(groups[gi, 0]), int(groups[gi, 1])
        rows = order[bounds[gi] : bounds[gi + 1]]
        grid = pg_vals[rows].T  # (S, n_cells)
        try:
            filled, n = fill_empty_draws(
                grid, cm_vals[cm_pos[(t, c)]], np.random.default_rng([seed, t, c])
            )
        except ValueError as err:
            raise ValueError(f"time {t}, country {c}: {err}") from err
        if n:
            if out is None:
                out = np.array(pg_vals, copy=True)
            out[rows] = filled.T
            n_filled += n

    if out is None:
        return pgm_frame, 0
    return PredictionFrame(out, pgm_frame.index, pgm_frame.metadata), n_filled
