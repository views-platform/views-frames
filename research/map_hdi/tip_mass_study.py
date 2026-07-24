"""Tip-mass study: which UPPER floor of the nested tower should define the MAP?

Question (Simon, 2026-07-24): the tip must be the median of a NARROW upper floor of
the constrained-nested tower — top 5% preferred, 10/15/20/25 acceptable, "absolutely
not higher than 25%". Because the tower is nested (C-44 outside-in), the narrow floor
is contained in its parents, so the tip is bounded — the open questions are purely
empirical:

  (1) Monte-Carlo stability: how much does tip(m) wobble across independent draws of
      the same posterior, at realistic sample counts (S = 32 / 100 / 1024)?
  (2) Accuracy: bias/RMSE of tip(m) against the known true mode, per shape.
  (3) Duplicate robustness (the C-44 concern, properly scoped to the nested tower):
      does a minority duplicate stack INSIDE the body attract a narrow floor more
      than a wide one? (An outside attractor is shed by nesting for every m — check.)

Method: R independent replicate rows per (shape, S); one `tower_point` call per
tip_mass m (config live-read, restored after) gives R tips vectorized. m ∈
{0.05, 0.10, 0.15, 0.20, 0.25} + 0.50 as the status-quo reference.

Run:  uv run python research/map_hdi/tip_mass_study.py
"""

from __future__ import annotations

import numpy as np

import views_frames as vf
import views_frames_summarize as vfs
from views_frames_summarize import config

R = 1000  # replicates per cell
MASSES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.50]
SAMPLE_COUNTS = [32, 100, 1024]
RNG = np.random.default_rng(20260724)


def _frame(mat: np.ndarray) -> vf.PredictionFrame:
    n = mat.shape[0]
    idx = vf.SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=vf.SpatialLevel.PGM,
    )
    return vf.PredictionFrame(np.asarray(mat, np.float32), idx)


def tips_for_mass(mat: np.ndarray, m: float) -> np.ndarray:
    """R tips (one per row) with tip_mass=m; config restored afterwards."""
    old = config.TOWER_CONFIG["tip_mass"]
    try:
        config.TOWER_CONFIG["tip_mass"] = m
        return vfs.tower_point(_frame(mat)).values.reshape(-1).astype(np.float64)
    finally:
        config.TOWER_CONFIG["tip_mass"] = old


# --- shapes with known true modes -------------------------------------------------
def shapes(s: int) -> dict[str, tuple[np.ndarray, float]]:
    out = {}
    out["lognormal (skewed)"] = (
        RNG.lognormal(0.5, 0.55, size=(R, s)),
        float(np.exp(0.5 - 0.55**2)),  # 1.218
    )
    out["gamma k=2 θ=5"] = (RNG.gamma(2.0, 5.0, size=(R, s)), 5.0)
    out["normal (symmetric)"] = (RNG.normal(6.0, 1.2, size=(R, s)), 6.0)
    zi = RNG.lognormal(0.7, 0.5, size=(R, s))
    mask = RNG.random(size=(R, s)) < 0.45
    out["zero-inflated 45%"] = (np.where(mask, 0.0, zi), 0.0)
    return out


def main() -> None:
    k_note = {s: {m: int(np.floor(m * s)) for m in MASSES} for s in SAMPLE_COUNTS}
    print("draws inside the tip floor  k = floor(m*S):")
    for s in SAMPLE_COUNTS:
        print(f"  S={s:5d}: " + "  ".join(f"m={m:.2f}→k={k_note[s][m]:4d}"
                                          for m in MASSES))
    print()

    # ---- (1)+(2) stability & accuracy ---------------------------------------------
    print("=" * 88)
    print("STABILITY & ACCURACY   (per cell: bias = mean(tip)−mode,  SD across "
          f"{R} replicates,  RMSE)")
    print("=" * 88)
    for s in SAMPLE_COUNTS:
        for name, (mat, mode) in shapes(s).items():
            line = f"S={s:5d}  {name:22s} mode={mode:6.3f} | "
            cells = []
            for m in MASSES:
                t = tips_for_mass(mat, m)
                bias = t.mean() - mode
                sd = t.std()
                rmse = np.sqrt(((t - mode) ** 2).mean())
                cells.append(f"m={m:.2f}: {bias:+.3f}/{sd:.3f}/{rmse:.3f}")
            print(line)
            for c in cells:
                print(" " * 12 + c)
        print("-" * 88)

    # ---- (3) duplicate robustness (C-44, nested-tower scoped) ----------------------
    print("=" * 88)
    print("DUPLICATE ROBUSTNESS — minority duplicate stack (15% of draws at one "
          "value); median |tip_dup − tip_clean| across replicates")
    print("attractor INSIDE the body (at the clean q80) vs OUTSIDE (beyond q99.9×1.5)")
    print("=" * 88)
    for s in [32, 100, 1024]:
        base = RNG.lognormal(0.5, 0.55, size=(R, s))
        n_dup = max(1, int(0.15 * s))
        q80 = np.quantile(base, 0.80, axis=1, keepdims=True)
        far = np.quantile(base, 0.999, axis=1, keepdims=True) * 1.5
        for label, attractor in [("inside(q80)", q80), ("outside(far)", far)]:
            dup = base.copy()
            dup[:, :n_dup] = attractor  # replace a minority block with the stack
            line = f"S={s:5d}  {label:13s} | "
            cells = []
            for m in MASSES:
                t_clean = tips_for_mass(base, m)
                t_dup = tips_for_mass(dup, m)
                disp = float(np.median(np.abs(t_dup - t_clean)))
                snapped = float(np.mean(np.abs(t_dup - attractor.ravel()) < 1e-6))
                cells.append(f"m={m:.2f}: disp={disp:6.3f} snap={snapped:4.0%}")
            print(line)
            for c in cells:
                print(" " * 12 + c)
        print("-" * 88)


if __name__ == "__main__":
    main()
