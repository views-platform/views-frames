"""Synthetic benchmark battery (IMMUTABLE harness — do not edit from the loop).

A fixed, cached set of "cells" spanning the VIEWS conflict shape. TWO regimes:

  zero-mode-dominant — the most likely value is 0 (quiet cells, the majority):
    zi_lognormal, zi_gamma, heavy, bimodal   (zero spike + right-skewed body)
  active / non-zero-mode — the most likely value is a positive number (1..4)
  with a right-skewed tail (active regions):
    active_gamma, active_lognormal, active_weibull, low_zi_active, bimodal_active

Per cell we store the OBSERVED draws (n in {128, 1024}), a large sorted REFERENCE
sample (oracle for true mass / shortest width), and the TRUE MODE (the most likely
value — densest bin of the reference; 0 if the zero spike dominates). Params are
drawn ONCE per cell so observed, reference, and true_mode all match.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SEED = 20260623
N_CELLS = 108
N_OBS = (128, 1024)
N_REF = 20000
MODE_BINS = 200
FAMILIES = (
    "zi_lognormal", "zi_gamma", "heavy", "bimodal",            # zero-mode-dominant
    "active_gamma", "active_lognormal", "active_weibull",      # non-zero mode 1..4
    "low_zi_active", "bimodal_active",
)
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "battery.npz"


def _params(rng: np.random.Generator, fam: str) -> dict:
    tm = float(rng.uniform(1.0, 4.0))  # target non-zero mode where relevant
    if fam == "zi_lognormal":
        return {"p0": rng.uniform(0.2, 0.6), "mu": rng.uniform(-1, 1.5), "sigma": rng.uniform(0.4, 1.2)}
    if fam == "zi_gamma":
        return {"p0": rng.uniform(0.2, 0.6), "shape": rng.uniform(1.0, 3.0), "scale": rng.uniform(0.5, 2.0)}
    if fam == "heavy":
        return {"p0": rng.uniform(0.1, 0.4), "mu": rng.uniform(0, 1), "sigma": rng.uniform(1.2, 2.0)}
    if fam == "bimodal":
        return {"p0": rng.uniform(0.2, 0.5), "w": rng.uniform(0.4, 0.7), "mu2": rng.uniform(1.5, 3.0)}
    if fam == "active_gamma":
        k = rng.uniform(2.0, 6.0)
        return {"p0": 0.0, "shape": k, "scale": tm / (k - 1.0)}  # gamma mode = (k-1)*scale = tm
    if fam == "active_lognormal":
        sig = rng.uniform(0.4, 0.9)
        return {"p0": 0.0, "mu": np.log(tm) + sig * sig, "sigma": sig}  # lognormal mode = exp(mu-sig^2) = tm
    if fam == "active_weibull":
        c = rng.uniform(1.6, 3.0)
        return {"p0": 0.0, "c": c, "scale": tm / ((c - 1.0) / c) ** (1.0 / c)}  # weibull mode = tm
    if fam == "low_zi_active":
        k = rng.uniform(2.5, 6.0)
        return {"p0": rng.uniform(0.0, 0.15), "shape": k, "scale": tm / (k - 1.0)}
    if fam == "bimodal_active":
        k1, k2 = 3.0, 5.0
        return {"p0": 0.0, "w": rng.uniform(0.4, 0.6),
                "s1": rng.uniform(1.0, 2.0) / (k1 - 1), "s2": rng.uniform(4.0, 7.0) / (k2 - 1),
                "k1": k1, "k2": k2}
    raise ValueError(fam)


def _draw(rng: np.random.Generator, fam: str, p: dict, n: int) -> np.ndarray:
    if fam in ("zi_lognormal", "heavy", "active_lognormal"):
        x = rng.lognormal(p["mu"], p["sigma"], n)
    elif fam in ("zi_gamma", "active_gamma", "low_zi_active"):
        x = rng.gamma(p["shape"], p["scale"], n)
    elif fam == "active_weibull":
        x = p["scale"] * rng.weibull(p["c"], n)
    elif fam == "bimodal":
        a = rng.lognormal(0.0, 0.4, n)
        b = rng.lognormal(p["mu2"], 0.4, n)
        x = np.where(rng.random(n) < p["w"], a, b)
    elif fam == "bimodal_active":
        a = rng.gamma(p["k1"], p["s1"], n)
        b = rng.gamma(p["k2"], p["s2"], n)
        x = np.where(rng.random(n) < p["w"], a, b)
    else:
        raise ValueError(fam)
    if p.get("p0", 0.0) > 0:
        x = np.where(rng.random(n) < p["p0"], 0.0, x)
    return x.astype(np.float64)


def _hist_mode(ref: np.ndarray) -> float:
    """The most likely value: centre of the densest bin (0 if the zero spike wins)."""
    hi = float(ref.max())
    if hi <= 1e-9:
        return 0.0
    counts, edges = np.histogram(ref, bins=MODE_BINS, range=(0.0, hi))
    j = int(np.argmax(counts))
    return float((edges[j] + edges[j + 1]) * 0.5)


def build(cache: Path = CACHE, seed: int = SEED) -> Path:
    cache.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    observed, reference, modes, meta = [], [], [], []
    for c in range(N_CELLS):
        fam = FAMILIES[c % len(FAMILIES)]
        n = N_OBS[c % len(N_OBS)]
        cr = np.random.default_rng(rng.integers(1 << 62))
        p = _params(cr, fam)
        observed.append(_draw(cr, fam, p, n))
        ref = np.sort(_draw(cr, fam, p, N_REF))
        reference.append(ref)
        modes.append(_hist_mode(ref))
        meta.append((fam, n))
    np.savez(
        cache,
        observed=np.array(observed, dtype=object),
        reference=np.array(reference, dtype=object),
        modes=np.array(modes, dtype=float),
        meta=np.array(meta, dtype=object),
    )
    return cache


def load(cache: Path = CACHE):
    """Return (observed, reference, modes, meta); build the cache if absent."""
    if not cache.exists():
        build(cache)
    d = np.load(cache, allow_pickle=True)
    return list(d["observed"]), list(d["reference"]), list(d["modes"]), list(d["meta"])


if __name__ == "__main__":
    build()
    obs, ref, modes, meta = load()
    print(f"built {len(obs)} cells")
    for f in FAMILIES:
        mm = [modes[i] for i, m in enumerate(meta) if m[0] == f]
        print(f"  {f:16s} n={len(mm):2d}  true_mode range [{min(mm):.2f}, {max(mm):.2f}]")
