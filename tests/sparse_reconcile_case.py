"""Realistic sparse reconciliation cases (#285).

The reconcile suites used to build grids with a few random zeros, so a country whose
grid is empty in a draw while the country forecast is positive happened only by
accident, and a 2.9–7.3% loss of country mass went unnoticed on the first production
run (#283). This module builds the case on purpose, at the sparsity a conflict forecast
actually has (94–96% of grid cells are zero).

Every `(time, country)` group gets:

- a sparse grid: each cell-draw is positive with probability ``1 - zero_share``;
- some **empty draws**: every cell zero while the country value is positive (the case a
  donor must fill), at the share ``empty_draw_share`` plus whatever sparsity produces;
- some **zero-country draws**: country value 0, so the grid must come out empty;
- at least one **donor**: a draw with grid mass, unless the country is listed in
  ``no_donor``, in which case every draw of that country is empty.

numpy + views-frames only. Not a test file; imported by the reconcile tests.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame, SpatialLevel
from views_frames_reconcile.frames import prediction_frame_from_arrays


class SparseCase(NamedTuple):
    """A reconciliation input plus the bookkeeping the tests need to check it."""

    cm: PredictionFrame
    pgm: PredictionFrame
    map_keys: NDArray[np.int64]  # (M, 2) (time, priogrid_gid)
    map_vals: NDArray[np.int64]  # (M,) country id
    group: NDArray[np.int64]  # (N_pg,) group index of each grid row
    group_cm_row: NDArray[np.int64]  # (G,) the cm row each group reconciles to


def sparse_case(
    seed: int,
    *,
    countries: int = 4,
    cells: int = 20,
    months: int = 2,
    samples: int = 64,
    zero_share: float = 0.95,
    empty_draw_share: float = 0.15,
    zero_country_share: float = 0.1,
    no_donor: tuple[int, ...] = (),
    cm_samples: int | None = None,
) -> SparseCase:
    """Build a sparse reconciliation case.

    Country ids are ``1..countries``; country ``c`` owns grid ids
    ``c * 1000 + 0..cells-1``. Months start at 500. ``cm_samples=1`` gives a point
    country (broadcast inside reconcile); ``samples=1`` gives a single-draw grid.
    """
    rng = np.random.default_rng(seed)
    n_cm = samples if cm_samples is None else cm_samples
    cm_t, cm_u, cm_v = [], [], []
    pg_t, pg_u, pg_v, group = [], [], [], []
    for gi, (t, c) in enumerate(
        (500 + m, c) for m in range(months) for c in range(1, countries + 1)
    ):
        country = rng.gamma(1.5, 40.0, size=n_cm).astype(np.float32) + np.float32(1.0)
        country[rng.random(n_cm) < zero_country_share] = 0.0

        grid = rng.gamma(0.6, 5.0, size=(cells, samples))
        grid[rng.random((cells, samples)) < zero_share] = 0.0
        grid[:, rng.random(samples) < empty_draw_share] = 0.0
        if c in no_donor:
            grid[:] = 0.0
        elif not (grid.sum(axis=0) > 0).any():
            grid[rng.integers(cells), rng.integers(samples)] = 1.0

        cm_t.append(t)
        cm_u.append(c)
        cm_v.append(country)
        for k in range(cells):
            pg_t.append(t)
            pg_u.append(c * 1000 + k)
            pg_v.append(grid[k].astype(np.float32))
            group.append(gi)

    pg_time = np.array(pg_t, dtype=np.int64)
    pg_unit = np.array(pg_u, dtype=np.int64)
    return SparseCase(
        cm=prediction_frame_from_arrays(
            np.array(cm_t), np.array(cm_u), np.array(cm_v), level=SpatialLevel.CM
        ),
        pgm=prediction_frame_from_arrays(
            pg_time, pg_unit, np.array(pg_v), level=SpatialLevel.PGM
        ),
        map_keys=np.stack([pg_time, pg_unit], axis=1),
        map_vals=pg_unit // 1000,
        group=np.array(group, dtype=np.int64),
        group_cm_row=np.arange(len(cm_t), dtype=np.int64),
    )


def group_sums(case: SparseCase, values: NDArray[np.floating]) -> NDArray[np.float64]:
    """Sum grid ``values`` ``(N_pg, S)`` per group → ``(G, S)``."""
    out = np.zeros((case.group_cm_row.size, values.shape[1]), dtype=np.float64)
    np.add.at(out, case.group, np.asarray(values, dtype=np.float64))
    return out


def country_totals(case: SparseCase, n_samples: int) -> NDArray[np.float64]:
    """The country value each group must reach, broadcast to ``(G, n_samples)``."""
    cm = np.asarray(case.cm.values, dtype=np.float64)[case.group_cm_row]
    return np.broadcast_to(cm, (cm.shape[0], n_samples))
