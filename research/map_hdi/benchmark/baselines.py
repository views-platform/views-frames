"""Incumbent baselines (IMMUTABLE harness — the bar the loop must beat).

These reproduce what the platform does today, so every experiment is reported
against them (Hyndman's rule: strong simple baselines from day one).

  histogram_map_independent_movetonest — the current behaviour:
      * point = centre of the densest 100-bin histogram cell (the C-32 estimator)
      * each HDI = independent shortest interval, THEN post-hoc "move the least
        distance to nest" (the C-33 patch)
"""

from __future__ import annotations

import numpy as np

HIGH_Q = 0.99


def _shortest(sorted_s: np.ndarray, alpha: float) -> tuple[float, float]:
    n = sorted_s.size
    k = int(np.floor(alpha * n))
    if k <= 0:
        i = n // 2
        return float(sorted_s[i]), float(sorted_s[i])
    widths = sorted_s[k:] - sorted_s[: n - k]
    i = int(np.argmin(widths))
    return float(sorted_s[i]), float(sorted_s[i + k])


def histogram_map_independent_movetonest(samples, masses):
    s = np.sort(np.asarray(samples, dtype=float))
    # point: histogram-MAP (lowest-index argmax tie-break — the C-32 behaviour)
    counts, edges = np.histogram(s, bins=100)
    j = int(np.argmax(counts))
    point = float((edges[j] + edges[j + 1]) / 2)
    # independent shortest intervals
    tower = [_shortest(s, a) for a in masses]
    # post-hoc move-to-nest: expand each wider interval to contain the previous
    for i in range(1, len(tower)):
        lo, hi = tower[i]
        plo, phi = tower[i - 1]
        tower[i] = (min(lo, plo), max(hi, phi))
    return {
        "tower": tower,
        "point": point,
        "low": float(s.min()),
        "high": float(np.quantile(s, HIGH_Q)),
    }


BASELINES = {
    "histogram_map_movetonest": histogram_map_independent_movetonest,
}
