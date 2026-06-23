"""Density-sensitivity study (clean): does the tower floor at a given mass depend
on tower density?

Compares floors at masses present on EVERY grid (10/30/50/70/90%) — no pinning, no
interpolation, so the only thing that varies is how far below each floor its nesting
constraint sits (m - density). MAP = median of the 10% floor. Each density compared
to a very-dense reference, per cell, normalised by the cell's IQR.

Run: uv run python research/map_hdi/density_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from benchmark import battery  # noqa: E402

EVAL_MASSES = (0.10, 0.30, 0.50, 0.70, 0.90)  # exact floors on all grids below
REF_D = 0.0025
TEST_D = (0.10, 0.05, 0.02, 0.01, 0.005)
ZERO_CUTOFF = 1.0


def _shortest(s, k):
    k = max(1, min(k, s.size - 1))  # a floor must hold >= 2 draws (resolution = 1/n)
    w = s[k:] - s[: s.size - k]
    i = int(np.argmin(w))
    return float(s[i]), float(s[i + k])


def _shortest_containing(s, k, lo, hi):
    n = s.size
    k = max(1, k)
    if k >= n - 1:
        return float(s[0]), float(s[-1])
    a, b = s[: n - k], s[k:]
    ok = (a <= lo) & (b >= hi)
    if not ok.any():
        return float(min(s[0], lo)), float(max(s[-1], hi))
    w = np.where(ok, b - a, np.inf)
    i = int(np.argmin(w))
    return float(a[i]), float(b[i])


def grid_tower(s, masses):
    n = s.size
    out, inner = [], None
    for m in masses:
        k = int(np.floor(m * n))
        lo, hi = _shortest(s, k) if inner is None else _shortest_containing(s, k, inner[0], inner[1])
        out.append((lo, hi))
        inner = (lo, hi)
    return out


def floors_and_map(s, density):
    s = np.sort(np.asarray(s, float))
    if s.max() < ZERO_CUTOFF:
        return {m: (0.0, 0.0) for m in EVAL_MASSES}, 0.0
    gmasses = np.round(np.arange(density, 1.0 + 1e-9, density), 6)
    gtower = grid_tower(s, gmasses)
    floors = {}
    for m in EVAL_MASSES:
        j = int(np.argmin(np.abs(gmasses - m)))
        floors[m] = gtower[j]
    lo, hi = floors[0.10]
    within = s[(s >= lo) & (s <= hi)]
    point = float(np.median(within)) if within.size else float(np.median(s))
    return floors, point


def main():
    obs, _ref, _modes, meta = battery.load()
    # production regime only (n=1024): density 0.5% is above the 1/n resolution floor
    cells = [np.asarray(o, float) for o, m in zip(obs, meta) if m[1] == 1024]
    iqr = [float(np.subtract(*np.quantile(s, [0.75, 0.25]))) + 1e-9 for s in cells]
    ref = [floors_and_map(s, REF_D) for s in cells]

    print(f"reference {REF_D*100:.2f}% ({int(round(1/REF_D))-1} floors); floors at "
          f"{[f'{int(m*100)}%' for m in EVAL_MASSES]}; MAP=median(10% floor)\n")
    print(f"{'density':>8} {'floors':>7} {'HDI Δ mean':>11} {'HDI Δ max':>10} {'MAP Δ mean':>11} {'MAP Δ max':>10}")
    for d in TEST_D:
        hd, md = [], []
        for ci, s in enumerate(cells):
            fl, pt = floors_and_map(s, d)
            rfl, rpt = ref[ci]
            sc = iqr[ci]
            for m in EVAL_MASSES:
                (lo, hi), (rlo, rhi) = fl[m], rfl[m]
                hd.append((abs(lo - rlo) + abs(hi - rhi)) / sc)
            md.append(abs(pt - rpt) / sc)
        print(f"{d*100:>7.1f}% {int(round(1/d))-1:>7} {np.mean(hd):>11.4f} {np.max(hd):>10.4f} "
              f"{np.mean(md):>11.4f} {np.max(md):>10.4f}")


if __name__ == "__main__":
    main()
