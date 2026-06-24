"""How compute-heavy is a dense, vectorized, constrained-nested tower?

Builds the tower across MANY cells at once (vectorized over the sample axis, like
views_frames.hdi already is), at several grid densities, and times it. Answers:
does the dense tower scale to the full PGM grid per month?

Run: uv run python research/map_hdi/timing.py
"""

from __future__ import annotations

import time

import numpy as np


def vec_shortest(s: np.ndarray, k: int):
    n = s.shape[1]
    if k <= 0:
        v = s[:, n // 2]
        return v.copy(), v.copy()
    w = s[:, k:] - s[:, : n - k]
    i = np.argmin(w, axis=1)
    lo = np.take_along_axis(s, i[:, None], 1)[:, 0]
    hi = np.take_along_axis(s, (i + k)[:, None], 1)[:, 0]
    return lo, hi


def vec_shortest_containing(s: np.ndarray, k: int, plo, phi):
    n = s.shape[1]
    if k >= n - 1:
        return s[:, 0].copy(), s[:, -1].copy()
    starts, ends = s[:, : n - k], s[:, k:]
    ok = (starts <= plo[:, None]) & (ends >= phi[:, None])
    w = np.where(ok, ends - starts, np.inf)
    i = np.argmin(w, axis=1)
    lo = np.take_along_axis(starts, i[:, None], 1)[:, 0]
    hi = np.take_along_axis(ends, i[:, None], 1)[:, 0]
    bad = ~np.isfinite(w.min(axis=1))
    lo = np.where(bad, np.minimum(s[:, 0], plo), lo)
    hi = np.where(bad, np.maximum(s[:, -1], phi), hi)
    return lo, hi


def dense_tower(s_sorted: np.ndarray, masses) -> np.ndarray:
    n = s_sorted.shape[1]
    out = np.empty((s_sorted.shape[0], len(masses), 2))
    plo = phi = None
    for j, m in enumerate(masses):
        k = int(np.floor(m * n))
        lo, hi = vec_shortest(s_sorted, k) if plo is None else vec_shortest_containing(s_sorted, k, plo, phi)
        out[:, j, 0], out[:, j, 1] = lo, hi
        plo, phi = lo, hi
    return out


def main():
    rng = np.random.default_rng(0)
    C, n = 50_000, 1024  # cells per block, pooled draws per cell
    # zero-inflated lognormal-ish, the realistic shape
    x = rng.lognormal(0.5, 1.0, (C, n))
    x[rng.random((C, n)) < 0.4] = 0.0
    s = np.sort(x, axis=1)

    full_grid_cells = 471_960 * 3  # PGM cells x 3 targets, one month
    print(f"block: {C:,} cells x {n} draws | extrapolating to {full_grid_cells:,} cell-summaries\n")
    print(f"{'density':>9} {'floors':>7} {'block_s':>9} {'full_grid_s':>12}")
    for d, label in [(0.05, "5%"), (0.02, "2%"), (0.01, "1%"), (0.005, "0.5%")]:
        masses = np.round(np.arange(d, 1.0, d), 4)
        t0 = time.perf_counter()
        dense_tower(s, masses)
        dt = time.perf_counter() - t0
        print(f"{label:>9} {len(masses):>7} {dt:>9.2f} {dt * full_grid_cells / C:>12.1f}")


if __name__ == "__main__":
    main()
