"""Top-down proportional reconciliation (numpy port — phase 2, slice 1).

Makes PRIO-GRID-month (pgm) forecasts sum to their country-month (cm) total by
**top-down disaggregation using forecast proportions** (FPP3 terminology),
applied **per posterior draw**: within a draw, each grid cell keeps its relative
share and the cells are rescaled so they sum to that draw's country total. Zeros
stay zero; country totals are authoritative; the result is non-negative.

This is a *faithful, numpy-only* port of views-reporting's
``ForecastReconciler.reconcile_forecast`` (torch), migrated here because the
algorithm belongs in post-processing, not reporting (views-reporting issue #72).
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

_EPS = np.float32(1e-8)


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
        ValueError: the grid and country sample counts disagree.
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

    # Preserve zeros: only strictly-positive cells carry probability mass.
    nonzero = np.where(grid_arr > 0, grid_arr, np.float32(0.0))

    # Per-draw proportional scaling to the (authoritative) country total.
    sum_nonzero = nonzero.sum(axis=1, keepdims=True)  # (S, 1)
    scaling = country_arr.reshape(-1, 1) / (sum_nonzero + _EPS)  # (S, 1)
    adjusted = np.clip(nonzero * scaling, 0.0, None).astype(np.float32)

    return np.asarray(adjusted[0] if is_point else adjusted, dtype=np.float32)
