"""Visual audit #2 — is the HDI path-dependent, and what fixes it?

Left column: the 50% HDI computed under different tower configs (does it move when
you change the OTHER masses?). Right column: the dense constrained-nested fan
(floors every 5%) + the point (median of the smallest floor) — the canonical tower.

Run: uv run --with pandas --with pyarrow --with matplotlib \
        python research/map_hdi/audit_tower.py
Out: research/map_hdi/audit_plots/tower_pathdep.png
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

OUT = HERE / "audit_plots"


def _shortest(s, k):
    if k <= 0:
        i = s.size // 2
        return float(s[i]), float(s[i])
    w = s[k:] - s[: s.size - k]
    i = int(np.argmin(w))
    return float(s[i]), float(s[i + k])


def _shortest_containing(s, k, lo, hi):
    n = s.size
    if k >= n - 1:
        return float(s[0]), float(s[-1])
    a, b = s[: n - k], s[k:]
    ok = (a <= lo) & (b >= hi)
    if not ok.any():
        return float(min(s[0], lo)), float(max(s[-1], hi))
    w = np.where(ok, b - a, np.inf)
    i = int(np.argmin(w))
    return float(a[i]), float(b[i])


def tower(s, masses):
    s = np.sort(np.asarray(s, float))
    n = s.size
    out, inner = [], None
    for m in masses:
        k = int(np.floor(m * n))
        lo, hi = _shortest(s, k) if inner is None else _shortest_containing(s, k, inner[0], inner[1])
        out.append((lo, hi))
        inner = (lo, hi)
    return out


# configs to test "the 50% HDI" under — varying masses below AND above it
CONFIGS = {
    "[50] alone": [0.50],
    "[50, 95]": [0.50, 0.95],
    "[50, 60, 95]": [0.50, 0.60, 0.95],
    "[10, 50]": [0.10, 0.50],
    "[10, 50, 95]": [0.10, 0.50, 0.95],
    "dense 5..95": list(np.round(np.arange(0.05, 1.0, 0.05), 2)),
}
DENSE = list(np.round(np.arange(0.05, 1.0, 0.05), 2))


def pick_cells():
    obs, _ref, _modes, meta = battery.load()
    out = []
    for fam in ("zi_lognormal", "bimodal", "active_gamma", "active_lognormal"):
        i = next(k for k, m in enumerate(meta) if m[0] == fam and m[1] == 1024)
        out.append((fam, np.asarray(obs[i], float)))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cells = pick_cells()
    fig, axes = plt.subplots(len(cells), 2, figsize=(13, 2.7 * len(cells)), squeeze=False)
    for r, (fam, draws) in enumerate(cells):
        s = np.sort(draws)
        # LEFT: the 50% HDI under each config
        axL = axes[r][0]
        for yi, (name, masses) in enumerate(CONFIGS.items()):
            t = tower(s, masses)
            j = masses.index(0.50) if 0.50 in masses else int(np.argmin(np.abs(np.array(masses) - 0.50)))
            lo, hi = t[j]
            axL.hlines(yi, lo, hi, lw=6, color="#1f77b4", alpha=0.75)
            axL.plot([lo, hi], [yi, yi], "|", color="k", ms=8, mew=1)
            axL.text(hi, yi, f"  [{lo:.2g}, {hi:.2g}]", va="center", fontsize=7)
        axL.set_yticks(range(len(CONFIGS)))
        axL.set_yticklabels(list(CONFIGS.keys()), fontsize=7)
        axL.set_title(f"{fam}: the 50% HDI under different towers", fontsize=8)
        axL.invert_yaxis()

        # RIGHT: dense fan + point
        axR = axes[r][1]
        axR.hist(s, bins=40, density=True, color="0.85")
        ymax = axR.get_ylim()[1] or 1.0
        t = tower(s, DENSE)
        for mi, (lo, hi) in enumerate(t):
            axR.hlines(ymax * (0.15 + 0.04 * mi), lo, hi, lw=2.5,
                       color=plt.cm.viridis(mi / len(t)), alpha=0.8)
        p_lo, p_hi = t[0]
        within = s[(s >= p_lo) & (s <= p_hi)]
        point = float(np.median(within)) if within.size else float(np.median(s))
        axR.axvline(point, color="crimson", lw=1.6, ls="--")
        axR.set_title(f"{fam}: dense fan (5..95%) + point={point:.2g}", fontsize=8)
        axR.set_yticks([])
    fig.suptitle("Is the 50% HDI path-dependent? (left) — and the canonical dense tower (right)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT / "tower_pathdep.png", dpi=120)
    print("wrote", OUT / "tower_pathdep.png")


if __name__ == "__main__":
    main()
