"""Synthetic benchmark battery (IMMUTABLE harness — do not edit from the loop).

A fixed, cached set of "cells", each a 1-D sample from a KNOWN family matching the
VIEWS conflict shape in ln(1+count) space: a spike at 0 (zero-inflation) plus a
right-skewed / heavy-tailed / sometimes bimodal positive body. Per cell we store:

  observed  — what the estimator sees (n in {128, 1024})
  reference — a large oracle sample (sorted) for true mass-in-interval and true
              shortest-interval width

Deterministic by seed. Params are drawn ONCE per cell, then both observed and
reference are drawn from those same params (so the oracle matches the data).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SEED = 20260623
N_CELLS = 60
N_OBS = (128, 1024)
N_REF = 20000
FAMILIES = ("zi_lognormal", "zi_gamma", "heavy", "bimodal")
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "battery.npz"


def _params(rng: np.random.Generator, family: str) -> dict:
    if family == "zi_lognormal":
        return {"p0": rng.uniform(0.0, 0.5), "mu": rng.uniform(-1, 2), "sigma": rng.uniform(0.4, 1.2)}
    if family == "zi_gamma":
        return {"p0": rng.uniform(0.0, 0.5), "shape": rng.uniform(1.0, 4.0), "scale": rng.uniform(0.5, 3.0)}
    if family == "heavy":
        return {"p0": rng.uniform(0.0, 0.3), "mu": rng.uniform(0, 1), "sigma": rng.uniform(1.2, 2.0)}
    if family == "bimodal":
        return {"p0": rng.uniform(0.0, 0.2), "w": rng.uniform(0.3, 0.7),
                "mu2": rng.uniform(1.5, 3.0)}
    raise ValueError(family)


def _draw(rng: np.random.Generator, family: str, p: dict, n: int) -> np.ndarray:
    if family in ("zi_lognormal", "heavy"):
        x = rng.lognormal(p["mu"], p["sigma"], n)
    elif family == "zi_gamma":
        x = rng.gamma(p["shape"], p["scale"], n)
    elif family == "bimodal":
        a = rng.lognormal(0.0, 0.4, n)
        b = rng.lognormal(p["mu2"], 0.4, n)
        x = np.where(rng.random(n) < p["w"], a, b)
    else:
        raise ValueError(family)
    x = np.where(rng.random(n) < p["p0"], 0.0, x)
    return x.astype(np.float64)


def build(cache: Path = CACHE, seed: int = SEED) -> Path:
    cache.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    observed, reference, meta = [], [], []
    for c in range(N_CELLS):
        fam = FAMILIES[c % len(FAMILIES)]
        n = N_OBS[c % len(N_OBS)]
        cr = np.random.default_rng(rng.integers(1 << 62))
        p = _params(cr, fam)
        observed.append(_draw(cr, fam, p, n))
        reference.append(np.sort(_draw(cr, fam, p, N_REF)))
        meta.append((fam, n))
    np.savez(
        cache,
        observed=np.array(observed, dtype=object),
        reference=np.array(reference, dtype=object),
        meta=np.array(meta, dtype=object),
    )
    return cache


def load(cache: Path = CACHE):
    """Return (observed_list, reference_list, meta_list); build the cache if absent."""
    if not cache.exists():
        build(cache)
    d = np.load(cache, allow_pickle=True)
    return list(d["observed"]), list(d["reference"]), list(d["meta"])


if __name__ == "__main__":
    path = build()
    obs, ref, meta = load()
    print(f"built {len(obs)} cells -> {path}")
    print("families:", {f: sum(1 for m in meta if m[0] == f) for f in FAMILIES})
