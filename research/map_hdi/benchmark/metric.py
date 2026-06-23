"""Tower-quality metric (IMMUTABLE harness — do not edit from the loop).

Measures whether an HDI tower is a *good summary* of a distribution we know the
truth of (via the reference oracle). NOT forecast evaluation — no real outcomes,
no CRPS. Components (all lower = better):

  nesting     hard gate: the tower must be nested (narrower ⊂ wider) for every cell
  mass_err    |true mass inside the α-HDI − α|, averaged over the tower
  excess_w    how much wider the α-HDI is than the TRUE shortest α-interval
  instab      how much the tower moves under a bootstrap resample of the draws

The aggregate scalar is feasibility-first: any nesting violation => 1e6 + count.
"""

from __future__ import annotations

import numpy as np

# component weights (reported separately too — a scalar hides choices).
# point_err is the HEADLINE deliverable (the "most likely value" we tell FAO).
W_POINT, W_MASS, W_SHARP, W_STAB = 1.0, 1.0, 0.5, 0.5


def point_error(point: float, true_mode: float, ref_sorted: np.ndarray) -> float:
    scale = float(np.subtract(*np.quantile(ref_sorted, [0.75, 0.25]))) + 1e-9
    return abs(point - true_mode) / scale


def _mass_in(ref_sorted: np.ndarray, lo: float, hi: float) -> float:
    lo_i = np.searchsorted(ref_sorted, lo, side="left")
    hi_i = np.searchsorted(ref_sorted, hi, side="right")
    return (hi_i - lo_i) / ref_sorted.size


def _true_shortest_width(ref_sorted: np.ndarray, alpha: float) -> float:
    m = ref_sorted.size
    k = int(np.floor(alpha * m))
    if k <= 0:
        return 0.0
    widths = ref_sorted[k:] - ref_sorted[: m - k]
    return float(widths.min())


def is_nested(tower: list[tuple[float, float]], eps: float = 1e-9) -> bool:
    return all(
        tower[i][0] <= tower[i - 1][0] + eps and tower[i][1] >= tower[i - 1][1] - eps
        for i in range(1, len(tower))
    )


def cell_components(tower, ref_sorted, masses) -> tuple[bool, float, float]:
    """Return (nested, mean_mass_err, mean_excess_width) for one cell's tower.

    Excess width is normalised by the distribution's IQR (a robust scale), NOT by
    the true shortest width — which is ~0 for zero-inflated cells (the atom at 0)
    and would divide by ~0.
    """
    nested = is_nested(tower)
    scale = float(np.subtract(*np.quantile(ref_sorted, [0.75, 0.25]))) + 1e-9
    mass_err = 0.0
    excess_w = 0.0
    for (lo, hi), a in zip(tower, masses):
        mass_err += abs(_mass_in(ref_sorted, lo, hi) - a)
        w_star = _true_shortest_width(ref_sorted, a)
        excess_w += max(0.0, (hi - lo) - w_star) / scale
    k = len(masses)
    return nested, mass_err / k, excess_w / k


def aggregate(per_cell: list[dict]) -> tuple[float, dict]:
    """Combine per-cell records into the scalar score + a components dict.

    Each record: {nested: bool, mass_err: float, excess_w: float, instab: float}.
    """
    viol = sum(0 if r["nested"] else 1 for r in per_cell)
    comp = {
        "point_err": float(np.mean([r["point_err"] for r in per_cell])),
        "mass_err": float(np.mean([r["mass_err"] for r in per_cell])),
        "excess_w": float(np.mean([r["excess_w"] for r in per_cell])),
        "instab": float(np.mean([r["instab"] for r in per_cell])),
        "nesting_viol": viol,
    }
    if viol:
        return 1e6 + viol, comp
    score = (
        W_POINT * comp["point_err"]
        + W_MASS * comp["mass_err"]
        + W_SHARP * comp["excess_w"]
        + W_STAB * comp["instab"]
    )
    return float(score), comp
