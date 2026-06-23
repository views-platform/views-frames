"""One more pass: settle the POINT estimate against a NON-CIRCULAR oracle.

The battery's stored `true_mode` is a 200-bin histogram argmax (battery.py:88) — so
the incumbent histogram-MAP matches it partly by sharing its binning, not by being
right (the C-32 circularity). But the ACTIVE families are constructed so the
*analytic* mode = tm (gamma (k-1)*scale, lognormal exp(mu-sig^2), weibull;
battery.py:48-54). We reconstruct tm by replaying the battery's RNG, then score
each candidate point estimator by |point - analytic_mode| / IQR.

We test, on the active (non-zero-mode) cells where the definitions actually differ:
  hist100  — incumbent: densest of 100 bins (argmax)         [the C-32 estimator]
  tip_med  — median of the narrowest 5% floor                 [the tower tip]
  tip_mid  — midpoint of the narrowest 5% floor
  halfsamp — Robertson-Cryer recursive half-sample mode

A uniform raw-count zero short-circuit (max < 1 -> 0) is applied to ALL candidates
first, so the active families purely test the non-zero definition.

Run: uv run python research/map_hdi/point_pass.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from benchmark import battery  # noqa: E402

ACTIVE = ("active_gamma", "active_lognormal", "active_weibull", "low_zi_active")
ZERO_FAMS = ("zi_lognormal", "zi_gamma", "heavy", "bimodal")
DENSITY = 0.05


def analytic_mode(fam: str, p: dict) -> float:
    """The TRUE mode from the parameters (no histogram). 0 for zero-spike families."""
    if fam == "active_gamma" or fam == "low_zi_active":
        m = (p["shape"] - 1.0) * p["scale"]  # gamma mode
        return float(m) if p.get("p0", 0.0) < 0.5 else 0.0
    if fam == "active_lognormal":
        return float(np.exp(p["mu"] - p["sigma"] ** 2))
    if fam == "active_weibull":
        c = p["c"]
        return float(p["scale"] * ((c - 1.0) / c) ** (1.0 / c))
    return 0.0  # zero-mode families: the spike at 0 dominates


def reconstruct():
    """Replay battery.build's RNG to recover (fam, n, params, analytic_mode) per cell."""
    rng = np.random.default_rng(battery.SEED)
    out = []
    for c in range(battery.N_CELLS):
        fam = battery.FAMILIES[c % len(battery.FAMILIES)]
        n = battery.N_OBS[c % len(battery.N_OBS)]
        cr = np.random.default_rng(rng.integers(1 << 62))
        p = battery._params(cr, fam)
        out.append((fam, n, p, analytic_mode(fam, p)))
    return out


# ---- candidate point estimators (raw draws, not sorted) -------------------
def _zero(s: np.ndarray) -> bool:
    return float(s.max()) < 1.0


def _shortest(s: np.ndarray, k: int):
    k = max(1, min(k, s.size - 1))
    w = s[k:] - s[: s.size - k]
    i = int(np.argmin(w))
    return float(s[i]), float(s[i + k])


def hist100(s: np.ndarray) -> float:
    if _zero(s):
        return 0.0
    hi = float(s.max())
    counts, edges = np.histogram(s, bins=100, range=(0.0, hi))
    j = int(np.argmax(counts))
    return float((edges[j] + edges[j + 1]) * 0.5)


def tip_med(s: np.ndarray) -> float:
    if _zero(s):
        return 0.0
    ss = np.sort(s)
    lo, hi = _shortest(ss, int(np.floor(DENSITY * ss.size)))
    within = ss[(ss >= lo) & (ss <= hi)]
    return float(np.median(within)) if within.size else float(np.median(ss))


def tip_mid(s: np.ndarray) -> float:
    if _zero(s):
        return 0.0
    ss = np.sort(s)
    lo, hi = _shortest(ss, int(np.floor(DENSITY * ss.size)))
    return 0.5 * (lo + hi)


def halfsamp(s: np.ndarray) -> float:
    """Robertson-Cryer recursive half-sample mode."""
    if _zero(s):
        return 0.0
    x = np.sort(s)
    while x.size > 2:
        k = (x.size + 1) // 2  # ceil(n/2) samples in the window
        w = x[k - 1 :] - x[: x.size - k + 1]
        i = int(np.argmin(w))
        x = x[i : i + k]
    return float(np.mean(x))


CANDS = {"hist100": hist100, "tip_med": tip_med, "tip_mid": tip_mid, "halfsamp": halfsamp}


def main():
    obs, _ref, modes, meta = battery.load()
    cells = reconstruct()
    # sanity: families/n line up between the replay and the cached battery
    assert [(f, n) for f, n, _, _ in cells] == [(m[0], m[1]) for m in meta], "RNG replay drift"

    iqr = [float(np.subtract(*np.quantile(o, [0.75, 0.25]))) + 1e-9 for o in obs]

    print(f"point estimate vs ANALYTIC mode (non-circular). density={DENSITY:.0%}, "
          f"|point-mode|/IQR, lower=better\n")
    print("ACTIVE families (analytic mode in [1,4] — the discriminating test):")
    header = f"{'family':16s} {'n':>5s} " + " ".join(f"{c:>9s}" for c in CANDS)
    print(header)
    for fam in ACTIVE:
        for nsel in (128, 1024):
            idx = [i for i, m in enumerate(meta) if m[0] == fam and m[1] == nsel]
            if not idx:
                continue
            row = f"{fam:16s} {nsel:>5d} "
            for c, fn in CANDS.items():
                errs = [abs(fn(np.asarray(obs[i], float)) - cells[i][3]) / iqr[i] for i in idx]
                row += f"{np.mean(errs):>9.4f} "
            print(row)

    # also report the circular (histogram-oracle) error on the SAME active cells,
    # so we can see whether hist100's edge is real or just oracle-matching.
    print("\nsame cells, but scored vs the battery's HISTOGRAM oracle (the circular one):")
    print(header)
    for fam in ACTIVE:
        idx = [i for i, m in enumerate(meta) if m[0] == fam]
        row = f"{fam:16s} {'all':>5s} "
        for c, fn in CANDS.items():
            errs = [abs(fn(np.asarray(obs[i], float)) - modes[i]) / iqr[i] for i in idx]
            row += f"{np.mean(errs):>9.4f} "
        print(row)

    # zero-mode families: every candidate should return ~0 (the spike is the mode)
    print("\nZERO-mode families: fraction of cells where point==0 (want 1.00):")
    for fam in ZERO_FAMS:
        idx = [i for i, m in enumerate(meta) if m[0] == fam]
        row = f"{fam:16s} {'':>5s} "
        for c, fn in CANDS.items():
            frac = np.mean([1.0 if fn(np.asarray(obs[i], float)) == 0.0 else 0.0 for i in idx])
            row += f"{frac:>9.2f} "
        print(row)


if __name__ == "__main__":
    main()
