"""Conformance checks for the reconcile package (ADR-023).

A consumer can re-run these against its own frame factories to confirm the reconciler
behaves: grid (``pgm``) predictions sum, in **every** draw, to their country (``cm``)
totals (ADR-030: a draw whose grid was empty is filled from a donor draw of its group);
zero cells stay zero in draws that had grid mass, and a filled draw copies a donor's
pattern; values stay non-negative; the output is a same-shape ``pgm``
``PredictionFrame`` at PGM level; and the cm/pgm mapping is **injected, never fetched**
(ADR-014/ADR-023).

Until 3.0.0 the sum law exempted draws whose grid was all zeros and required them to
stay zero. That exemption is where the reconciler lost country mass (#283); it is gone.

Mirrors ``views_frames_summarize/conformance.py:assert_summarizer_contract``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame, SpatialLevel
from views_frames_reconcile.module import ReconciliationModule

__all__ = ["assert_reconcile_contract"]


def _require_assertions() -> None:
    """Fail loud if assertions are stripped (``python -O``/``-OO``).

    Mirrors ``views_frames.conformance._require_assertions`` (falsify audit 2026-07,
    F3): under optimized bytecode every ``assert`` silently passes — refuse to run.
    """
    if not __debug__:  # pragma: no cover — pytest always runs with assertions on
        raise RuntimeError(
            "the reconcile conformance suite requires assertions; run without "
            "python -O/-OO (PYTHONOPTIMIZE), otherwise every check silently passes"
        )


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
    _require_assertions()
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

    # 3 + 4, per (time, country) group.
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
        grid_in = np.asarray(pgm_frame.values[rows], dtype=np.float64)  # (n, S)
        grid_out = np.asarray(out.values[rows], dtype=np.float64)
        out_sum = grid_out.sum(axis=0)  # (S,)
        # cm may be a point (sample_count == 1, broadcast inside reconcile) or aligned
        # draws — broadcast its per-(time, country) total to the draw axis either way.
        cm_total = cm_frame.values[cm_pos[(int(t), int(c))]]
        total = np.broadcast_to(cm_total, out_sum.shape)

        # 4. Sum-to-country in every draw: a positive country value is placed in full,
        #    a zero one empties the grid. No draw is exempt (ADR-030).
        np.testing.assert_allclose(out_sum, total, rtol=1e-4, atol=1e-3)

        # 3a. Zero-preservation in draws that had grid mass: their zero cells stay zero.
        positive_in = np.where(grid_in > 0, grid_in, 0.0)
        had_mass = positive_in.sum(axis=0) > 0
        stays_zero = positive_in[:, had_mass] == 0
        assert bool((grid_out[:, had_mass][stays_zero] == 0).all()), "zeros preserved"

        # 3b. A filled draw (input grid empty, mass placed) is a scaled copy of a draw
        #     of the same group that had grid mass: same zero cells, same shares.
        filled = np.flatnonzero(~had_mass & (out_sum > 0))
        if filled.size:
            donors = positive_in[:, had_mass]
            assert donors.shape[1] > 0, "a draw was filled although no draw had mass"
            donor_shares = donors / donors.sum(axis=0)
            for s in filled:
                share = grid_out[:, s] / out_sum[s]
                close = np.isclose(donor_shares, share[:, None], rtol=1e-4, atol=1e-6)
                assert bool(close.all(axis=0).any()), (
                    "a filled draw must copy the pattern of a donor draw of its group"
                )
