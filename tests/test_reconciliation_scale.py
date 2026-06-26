"""C-38 regression guard: reconciliation grouping scales (not O(groups x N)).

Reconciles a frame with **many** (time, country) groups and asserts it stays
correct and fast. The primary guard is correctness-at-scale — the group-by-sort
`argsort`/`bounds` logic (`grouping.py`) must hold conservation across thousands
of groups; the time budget is a loose smoke. The real global-volume verification
is the S7 dry-run (register C-38). Offline; numpy + views-frames only.
"""

import time

import numpy as np

from views_frames import SpatialLevel
from views_frames_reconcile import ReconciliationModule
from views_frames_reconcile.frames import prediction_frame_from_arrays


def _many_group_frames(n_countries=2000, cells_per=8, month=528, samples=20):
    """A single-month frame with `n_countries` groups of `cells_per` grid cells."""
    rng = np.random.default_rng(0)
    times, grids, gcountry, cm_units = [], [], [], []
    g = 1000
    for c in range(1, n_countries + 1):
        for _ in range(cells_per):
            times.append(month)
            grids.append(g)
            gcountry.append(c)
            g += 1
        cm_units.append(c)
    times = np.asarray(times)
    grids = np.asarray(grids)
    gcountry = np.asarray(gcountry)

    pg = rng.gamma(2.0, 5.0, (len(grids), samples)).astype(np.float32)
    pg[rng.random(pg.shape) < 0.3] = 0.0  # sparsity -> some all-zero groups
    cm_vals = rng.gamma(3.0, 20.0, (n_countries, samples)).astype(np.float32)

    pgm = prediction_frame_from_arrays(times, grids, pg, level=SpatialLevel.PGM)
    cm = prediction_frame_from_arrays(
        np.full(n_countries, month), np.asarray(cm_units), cm_vals, level=SpatialLevel.CM
    )
    map_keys = np.stack([times, grids], axis=1)
    return cm, pgm, map_keys, gcountry, month


class TestScale:
    def test_many_groups_correct_and_fast(self):
        cm, pgm, map_keys, gcountry, month = _many_group_frames()
        rm = ReconciliationModule(map_keys, gcountry)

        t0 = time.perf_counter()
        out = rm.reconcile(cm, pgm)
        elapsed = time.perf_counter() - t0

        assert out.values.shape == pgm.values.shape
        # Loose smoke: a reintroduced O(groups x N) grouping would balloon this.
        assert elapsed < 10.0, f"reconcile unexpectedly slow ({elapsed:.1f}s)"

        # Correctness across many groups: conservation holds per draw, except
        # all-zero-input draws (which stay zero) — checked on a spread of countries.
        cmv = {int(u): cm.values[i] for i, u in enumerate(cm.index.unit)}
        for c in (1, 137, 1000, 2000):
            sel = np.nonzero(gcountry == c)[0]
            inp_allzero = (pgm.values[sel] == 0).all(axis=0)
            grid_sum = out.values[sel].sum(axis=0)
            active = ~inp_allzero
            np.testing.assert_allclose(
                grid_sum[active], cmv[c][active], rtol=1e-3, atol=1e-2
            )
            assert (grid_sum[inp_allzero] == 0).all()
