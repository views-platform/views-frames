"""THE SANDBOX — the autoresearch loop edits ONLY this file.

`summarize(samples, masses)` -> {"tower": [(lo,hi),...] nested, "point", "low", "high"}.

Tower: inside-out constrained nested shortest-intervals (solved in v1). Point: the
SAMPLE histogram-MAP with the same binning the oracle uses to define the true mode
(200 bins over [0,max]) — a diagnostic for whether matching the mode's binning wins.
Deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

MASSES = (0.10, 0.50, 0.90)
HIGH_Q = 0.99
MODE_BINS = 200


def _shortest(s: np.ndarray, k: int) -> tuple[float, float]:
    if k <= 0:
        i = s.size // 2
        return float(s[i]), float(s[i])
    widths = s[k:] - s[: s.size - k]
    i = int(np.argmin(widths))
    return float(s[i]), float(s[i + k])


def _shortest_containing(s: np.ndarray, k: int, lo: float, hi: float) -> tuple[float, float]:
    n = s.size
    if k >= n - 1:
        return float(s[0]), float(s[-1])
    starts = s[: n - k]
    ends = s[k:]
    ok = (starts <= lo) & (ends >= hi)
    if not ok.any():
        return float(min(s[0], lo)), float(max(s[-1], hi))
    widths = np.where(ok, ends - starts, np.inf)
    i = int(np.argmin(widths))
    return float(starts[i]), float(ends[i])


def _hist_mode(s: np.ndarray) -> float:
    hi = float(s.max())
    if hi <= 1e-9:
        return 0.0
    counts, edges = np.histogram(s, bins=MODE_BINS, range=(0.0, hi))
    j = int(np.argmax(counts))
    return float((edges[j] + edges[j + 1]) * 0.5)


def summarize(samples, masses: Sequence[float] = MASSES) -> dict:
    s = np.sort(np.asarray(samples, dtype=float))
    n = s.size
    tower: list[tuple[float, float]] = []
    inner: tuple[float, float] | None = None
    for a in masses:
        k = int(np.floor(a * n))
        lo, hi = _shortest(s, k) if inner is None else _shortest_containing(s, k, inner[0], inner[1])
        tower.append((lo, hi))
        inner = (lo, hi)

    point = _hist_mode(s)
    return {"tower": tower, "point": point, "low": float(s.min()), "high": float(np.quantile(s, HIGH_Q))}
