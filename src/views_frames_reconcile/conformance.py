"""Conformance checks for the reconcile package (ADR-023).

A consumer can re-run these against its own frame factories to confirm the reconciler
behaves: grid (``pgm``) predictions sum, per draw, to their country (``cm``) totals
(except all-zero grid draws, which stay zero — the documented edge); zeros preserved;
values stay non-negative; the output is a same-shape ``pgm`` ``PredictionFrame`` at PGM
level; and the cm/pgm mapping is **injected, never fetched** (ADR-014/ADR-023).

Mirrors ``views_frames_summarize/conformance.py:assert_summarizer_contract``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame, SpatialLevel
from views_frames_reconcile.module import ReconciliationModule


def assert_reconcile_contract(
    cm_frame: PredictionFrame,
    pgm_frame: PredictionFrame,
    map_keys: NDArray[np.integer[Any]] | object,
    map_vals: NDArray[np.integer[Any]] | object,
) -> None:
    """Assert the reconciler obeys its contract on ``(cm_frame, pgm_frame, mapping)``.

    The mapping is **injected** (``map_keys``/``map_vals`` arrays) — never fetched
    (enforced by the signature + the import-DAG; honoured here by the sum-to-country
    law, which only holds if each cell is grouped under its injected country).

    Raises:
        AssertionError: a contract law is violated.
    """
    mk = np.asarray(map_keys)
    mv = np.asarray(map_vals)
    out = ReconciliationModule(mk, mv).reconcile(cm_frame, pgm_frame)

    # 1. Output type / shape / level / index: a same-shape pgm PredictionFrame at PGM.
    assert type(out) is type(pgm_frame), "reconcile must return the pgm frame type"
    assert out.values.shape == pgm_frame.values.shape, "reconcile must preserve (N, S)"
    assert out.index.level is SpatialLevel.PGM, "reconciled frame stays at PGM level"
    assert np.array_equal(out.index.time, pgm_frame.index.time), "time index preserved"
    assert np.array_equal(out.index.unit, pgm_frame.index.unit), "unit index preserved"

    # 2. Non-negativity.
    assert bool((out.values >= 0).all()), "reconciled forecasts must be non-negative"

    # 3. Zero-preservation: an input zero cell stays zero.
    assert bool((out.values[pgm_frame.values == 0] == 0).all()), "zeros preserved"

    # 4. Sum-to-country per draw: each (time, country) group's cells sum, per draw, to
    #    its country total — except all-zero input draws, which stay zero (the edge).
    cm_units = pgm_frame.index.cross_level_align_arrays(mk, mv, SpatialLevel.CM).unit
    pg_time = pgm_frame.index.time
    cm_pos = {
        (int(t), int(u)): j
        for j, (t, u) in enumerate(
            zip(cm_frame.index.time, cm_frame.index.unit, strict=True)
        )
    }
    for t, c in np.unique(np.stack([pg_time, cm_units], axis=1), axis=0):
        rows = (pg_time == t) & (cm_units == c)
        in_sum = pgm_frame.values[rows].sum(axis=0)  # (S,)
        out_sum = out.values[rows].sum(axis=0)  # (S,)
        # cm may be a point (sample_count == 1, broadcast inside reconcile) or aligned
        # draws — broadcast its per-(time, country) total to the draw axis either way.
        cm_total = cm_frame.values[cm_pos[(int(t), int(c))]]
        total = np.broadcast_to(cm_total, out_sum.shape)
        active = in_sum != 0
        np.testing.assert_allclose(
            out_sum[active], total[active], rtol=1e-4, atol=1e-3
        )
        assert bool((out_sum[~active] == 0).all()), "all-zero draws stay zero"
