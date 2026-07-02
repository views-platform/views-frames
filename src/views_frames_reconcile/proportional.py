"""Top-down proportional reconciliation (numpy port — phase 2, slice 1).

Makes PRIO-GRID-month (pgm) forecasts sum to their country-month (cm) total by
**top-down disaggregation using forecast proportions** (FPP3 terminology),
applied **per posterior draw**: within a draw, each grid cell keeps its relative
share and the cells are rescaled so they sum to that draw's country total. Zeros
stay zero; country totals are authoritative; the result is non-negative.

This is a *faithful, numpy-only* port of views-reporting's
``ForecastReconciler.reconcile_forecast`` (torch), migrated here because the
algorithm belongs in post-processing, not reporting (views-reporting issue #72).
One deliberate deviation (falsify audit 2026-07): the original's ``+ 1e-8``
denominator epsilon is replaced by an explicit all-zero-draw guard — bit-identical
on all realistic data (the epsilon was a float32 no-op for draw sums ≳ 0.1) but
exactly conserving for tiny nonzero sums, where the epsilon silently deflated the
scale factor. Negative country totals now fail loud instead of silently clamping.
It is intentionally the **same** method — a pragmatic per-draw approximation, not
principled joint probabilistic reconciliation. The upgrade to the latter is designed
in **ADR-024** (register **C-62**; the cross-repo lineage is views-postprocessing
C-37) and is deliberately **deferred**: per-draw pairing of independently-trained
grid and country draws has no shared draw identity, so the principled method waits on
a defined draw-identity/coupling contract and a consumer that needs calibrated joint
tails.

No torch, no pandas — numpy only.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def reconcile_proportional(
    grid: NDArray[np.floating[Any]] | object,
    country: NDArray[np.floating[Any]] | float | object,
) -> NDArray[np.float32]:
    """Rescale grid forecasts so each draw sums to its country total.

    Args:
        grid: Grid-level forecasts, float32-coercible. Either
            ``(num_samples, num_grid_cells)`` (probabilistic) or
            ``(num_grid_cells,)`` (point).
        country: Country-level total. Either ``(num_samples,)`` (probabilistic)
            or a scalar (point). Must align with ``grid``'s sample axis.

    Returns:
        Adjusted grid forecasts, float32, same shape as ``grid``. ``sum`` over
        grid cells equals ``country`` per sample; zero cells stay zero; values
        are clamped to be non-negative.

    Raises:
        ValueError: the grid and country sample counts disagree, or any country
            total is negative (cannot be conserved under the non-negativity clamp).
    """
    grid_arr = np.asarray(grid, dtype=np.float32)
    is_point = grid_arr.ndim == 1

    if is_point:
        grid_arr = grid_arr[np.newaxis, :]  # (1, N)
        country_arr = np.asarray([country], dtype=np.float32)
    else:
        country_arr = np.asarray(country, dtype=np.float32).reshape(-1)

    if grid_arr.shape[0] != country_arr.shape[0]:
        raise ValueError(
            f"Mismatch in sample count: grid has {grid_arr.shape[0]}, "
            f"country has {country_arr.shape[0]}"
        )
    if bool((country_arr < 0).any()):
        # A negative total cannot be conserved under the non-negativity clamp — the
        # output would silently sum to 0, not the total (falsify audit 2026-07, F8).
        raise ValueError(
            "country totals must be non-negative; got a negative total "
            f"(min={float(country_arr.min())}). A negative forecast is an upstream "
            "bug; reconciliation cannot conserve it under the non-negativity clamp."
        )

    # Preserve zeros: only strictly-positive cells carry probability mass.
    nonzero = np.where(grid_arr > 0, grid_arr, np.float32(0.0))

    # Per-draw proportional scaling to the (authoritative) country total. Guard the
    # all-zero draws explicitly (they carry no mass and stay zero — the documented
    # edge) instead of an additive epsilon in the denominator: `+ 1e-8` was a no-op
    # in float32 for sums ≳ 0.1 (machine eps exceeds it) but silently deflated the
    # scale factor for tiny nonzero sums — at a draw sum of 1e-8 a country total of
    # 100 reconciled to 50 with no error signal (falsify audit 2026-07, F1). The
    # exact division below is bit-identical to the epsilon form on all realistic
    # data (torch-oracle parity preserved) and conserves exactly for any nonzero sum.
    sum_nonzero = nonzero.sum(axis=1, keepdims=True)  # (S, 1)
    has_mass = sum_nonzero > 0
    safe_sum = np.where(has_mass, sum_nonzero, np.float32(1.0))
    scaling = np.where(
        has_mass, country_arr.reshape(-1, 1) / safe_sum, np.float32(0.0)
    )  # (S, 1)
    adjusted = np.clip(nonzero * scaling, 0.0, None).astype(np.float32)

    return np.asarray(adjusted[0] if is_point else adjusted, dtype=np.float32)
