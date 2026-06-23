"""Visual audit — plot candidate tower estimators on real + synthetic cells.

For each cell (rows) and each estimator (cols) draw: the draws (hist + rug), the
3 nested HDIs (10/50/90 as stacked bars), and the point (dashed line). Lets a human
eyeball whether the tower + point look sensible — and SEE why the discarded routes
fail (e.g. KDE bridging a gap on a bimodal cell).

Run: uv run --with scipy --with pandas --with pyarrow --with matplotlib \
        python research/map_hdi/audit.py
Out: research/map_hdi/audit_plots/towers.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from benchmark import battery  # noqa: E402

import estimator as base_mod  # noqa: E402  (the winning baseline)

MASSES = (0.10, 0.50, 0.90)
OUT = HERE / "audit_plots"
REAL = Path("../views-faoapi/appwrite_cache/unfao_bucket/forecast_dataset_20260310_114703.parquet")


# --- the two most informative discarded routes, inline, for comparison -------
def kde_levelset(samples, masses=MASSES):
    from scipy.stats import gaussian_kde

    s = np.sort(np.asarray(samples, float))
    lo, hi = float(s.min()), float(s.max())
    if hi - lo < 1e-9:
        return {"tower": [(lo, lo)] * len(masses), "point": lo, "low": lo, "high": hi}
    grid = np.linspace(lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo), 512)
    try:
        dens = gaussian_kde(s)(grid)
    except Exception:
        return {"tower": [(lo, hi)] * len(masses), "point": float(np.median(s)), "low": lo, "high": hi}
    order = np.argsort(dens)[::-1]
    cum = np.cumsum(dens[order]) * (grid[1] - grid[0])
    tower = []
    for a in masses:
        incl = grid[order[: min(int(np.searchsorted(cum, a) + 1), order.size)]]
        tower.append((float(incl.min()), float(incl.max())))
    return {"tower": tower, "point": float(np.median(s)), "low": lo, "high": float(np.quantile(s, 0.99))}


ESTIMATORS = {
    "baseline\n(constrained-nested)": base_mod.summarize,
    "KDE level-sets\n(discarded)": kde_levelset,
}


def plot_panel(ax, draws, res, title):
    ax.hist(draws, bins=40, density=True, color="0.85", edgecolor="none")
    ymax = ax.get_ylim()[1] or 1.0
    ax.plot(draws, np.full_like(draws, -0.04 * ymax), "|", color="k", ms=6, mew=0.5)
    colors = ["#1f77b4", "#2ca02c", "#9467bd"]
    for mi, (lo, hi) in enumerate(res["tower"]):
        y = ymax * (0.55 + 0.14 * mi)
        ax.hlines(y, lo, hi, color=colors[mi], lw=5, alpha=0.75)
        ax.text(hi, y, f" {int(MASSES[mi] * 100)}%", va="center", fontsize=6, color=colors[mi])
    ax.axvline(res["point"], color="crimson", lw=1.6, ls="--")
    ax.set_title(title, fontsize=8)
    ax.set_yticks([])


def collect_cells():
    cells = []  # (label, draws)
    obs, _ref, meta = battery.load()
    for fam in ("zi_lognormal", "bimodal", "heavy"):
        i = next(k for k, m in enumerate(meta) if m[0] == fam)
        cells.append((f"synthetic: {fam}\n(n={meta[i][1]})", np.asarray(obs[i], float)))
    if REAL.exists():
        import pandas as pd

        df = pd.read_parquet(REAL, columns=["pred_ln_sb_best"])
        mat = np.stack(df["pred_ln_sb_best"].to_numpy()[:50000])
        nz = (~np.isclose(mat, 0.0, atol=1e-8)).mean(axis=1)
        active = np.where((nz > 0.25) & (nz < 0.95))[0]
        for j in active[:: max(1, active.size // 3)][:3]:
            cells.append((f"REAL active cell\n(nz={nz[j]:.2f}, n=32)", mat[j].astype(float)))
    return cells


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cells = collect_cells()
    ncol = len(ESTIMATORS)
    fig, axes = plt.subplots(len(cells), ncol, figsize=(4.2 * ncol, 2.4 * len(cells)), squeeze=False)
    for r, (label, draws) in enumerate(cells):
        for c, (name, fn) in enumerate(ESTIMATORS.items()):
            res = fn(draws, MASSES)
            plot_panel(axes[r][c], draws, res, name if r == 0 else "")
        axes[r][0].set_ylabel(label, fontsize=7, rotation=0, ha="right", va="center", labelpad=40)
    fig.suptitle("Tower audit — 3 nested HDIs (blue=10% green=50% purple=90%) + point (red --)", fontsize=10)
    fig.tight_layout(rect=(0.04, 0, 1, 0.97))
    path = OUT / "towers.png"
    fig.savefig(path, dpi=120)
    print("wrote", path, "| cells:", len(cells))


if __name__ == "__main__":
    main()
