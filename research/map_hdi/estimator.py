"""THE SANDBOX — the autoresearch loop edits ONLY this file.

`summarize(samples, masses)` turns one cell's pooled posterior draws into the
dashboard summary. Contract (do not change the keys/shape):

    {"tower": [(lo, hi), ...],   # one per mass, ascending, NESTED by construction
     "point": float,            # median of draws inside the narrowest HDI
     "low":   float,            # ~0
     "high":  float}            # ~0.99 quantile

Current route: constrained nested shortest-intervals (Route 1 in program.md).
Nesting is guaranteed because each wider interval is the shortest one that
*contains the previous*. Deterministic — no RNG here.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

MASSES = (0.10, 0.50, 0.90)
HIGH_Q = 0.99


def _shortest(sorted_s: np.ndarray, k: int) -> tuple[int, int]:
    """Indices (i, i+k) of the shortest window holding k+1 points."""
    if k <= 0:
        i = sorted_s.size // 2
        return i, i
    widths = sorted_s[k:] - sorted_s[: sorted_s.size - k]
    i = int(np.argmin(widths))
    return i, i + k


def _shortest_containing(sorted_s: np.ndarray, k: int, lo: float, hi: float) -> tuple[float, float]:
    """Shortest window of k+1 points that contains [lo, hi]."""
    n = sorted_s.size
    if k >= n - 1:
        return float(sorted_s[0]), float(sorted_s[-1])
    starts = sorted_s[: n - k]
    ends = sorted_s[k:]
    ok = (starts <= lo) & (ends >= hi)
    if not ok.any():
        # no k+1-window brackets the inner interval; widen minimally to cover it
        return float(min(sorted_s[0], lo)), float(max(sorted_s[-1], hi))
    widths = np.where(ok, ends - starts, np.inf)
    i = int(np.argmin(widths))
    return float(starts[i]), float(ends[i])


def summarize(samples, masses: Sequence[float] = MASSES) -> dict:
    s = np.sort(np.asarray(samples, dtype=float))
    n = s.size
    tower: list[tuple[float, float]] = []
    inner: tuple[float, float] | None = None
    for a in masses:  # ascending => each contains the previous => nested
        k = int(np.floor(a * n))
        if inner is None:
            i, j = _shortest(s, k)
            lo, hi = float(s[i]), float(s[j])
        else:
            lo, hi = _shortest_containing(s, k, inner[0], inner[1])
        tower.append((lo, hi))
        inner = (lo, hi)

    lo0, hi0 = tower[0]
    within = s[(s >= lo0) & (s <= hi0)]
    point = float(np.median(within)) if within.size else float(np.median(s))
    return {"tower": tower, "point": point, "low": float(s.min()), "high": float(np.quantile(s, HIGH_Q))}
