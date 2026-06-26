"""Synthetic, ground-truth-carrying data generators for the showcase notebooks.

An **un-gated dev helper** — it lives in ``notebooks/`` (outside ``src/``, excluded
from the lint/coverage gate) and is imported by ``01_frames`` / ``02_summaries`` /
``03_reconciliation``. It is *not* part of the package and is never imported by
``src/``.

Design rules it obeys (the same conventions as the notebooks):

* **numpy only**, and frames are built through the **public** ``views_frames`` API;
  no ``views_*`` consumer, ``viewser``, or domain import (ADR-001, the import-DAG).
* **Self-contained** — the distribution-family parametrisations are *copied in* from
  ``research/map_hdi/benchmark/battery.py``, never imported, so the notebooks depend
  on nothing outside this repo.
* **Ground-truth-carrying** — every generator returns the data **and the known latent
  truth**: the true mean / mode / quantiles of each shape, and for the cm/pgm scenario
  the true country total. That is what lets ``02_summaries`` check interval *coverage*
  and point-estimate *recovery*, and ``03_reconciliation`` ask whether reconciliation
  moves the grid estimates *toward* the truth.
* **Reproducible & light** — fixed seeds, small sample sizes; everything here renders
  fast inside the notebooks' < 1 min *Run All* budget.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from views_frames import (
    FeatureFrame,
    FrameMetadata,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
    TargetFrame,
)

__all__ = [
    "Truth",
    "ZooFrames",
    "CmPgmScenario",
    "ZOO_SHAPES",
    "distribution_zoo",
    "zoo_frames",
    "cm_pgm_scenario",
    "frame_from_samples",
]

_REF_SIZE = 40_000  # oracle-sample size behind each Truth (tight MC error on the truth)
_BASE_MONTH = 500
_BASE_PRIOGRID = 1000
_BASE_COUNTRY = 70

# The six canonical shapes of the VIEWS estimand. Params are FIXED (not random) so
# the zoo is fully reproducible and each shape is a labelled teaching example.
ZOO_SHAPES: dict[str, tuple[str, dict[str, float]]] = {
    "zero_inflated": ("zi_gamma", {"p0": 0.55, "shape": 2.0, "scale": 1.5}),
    "right_skewed_gamma": ("gamma", {"shape": 2.5, "scale": 1.2}),
    "right_skewed_lognormal": ("lognormal", {"mu": 0.6, "sigma": 0.7}),
    "near_symmetric": ("gamma", {"shape": 30.0, "scale": 0.2}),
    "heavy_tailed": ("lognormal", {"mu": 0.5, "sigma": 1.5}),
    # two well-separated, tight (clipped-normal) bumps — a *genuinely* two-peaked
    # posterior the conservative `bimodality` detector should flag (vs a merely
    # skewed/heavy tail, which it should not).
    "bimodal": ("bimodal", {"w": 0.5, "mu1": 2.0, "s1": 0.7, "mu2": 10.0, "s2": 1.0}),
}


# ---- distribution families (copied from battery.py; the data-generating process) ----


def _sample(
    family: str, params: dict[str, float], n: int, rng: np.random.Generator
) -> NDArray[np.float64]:
    """Draw ``n`` samples from the named family (the DGP behind a shape)."""
    if family == "gamma":
        x = rng.gamma(params["shape"], params["scale"], n)
    elif family == "lognormal":
        x = rng.lognormal(params["mu"], params["sigma"], n)
    elif family == "zi_gamma":
        x = rng.gamma(params["shape"], params["scale"], n)
        x = np.where(rng.random(n) < params["p0"], 0.0, x)
    elif family == "bimodal":
        a = rng.normal(params["mu1"], params["s1"], n)
        b = rng.normal(params["mu2"], params["s2"], n)
        x = np.clip(np.where(rng.random(n) < params["w"], a, b), 0.0, None)
    else:  # pragma: no cover - guards a typo in ZOO_SHAPES
        raise ValueError(f"unknown family: {family}")
    return np.asarray(x, dtype=np.float64)


def _analytic_mode(family: str, params: dict[str, float]) -> float:
    """The **true** mode of the DGP, in closed form.

    The notebooks rely on this being the genuine density peak. A histogram mode over the
    reference sample is a binning artifact for heavy tails (it can land ~10x off) and
    never returns exactly 0 for a zero-inflated atom — both would mislabel the "known
    truth" the teaching tables compare estimators against.
    """
    if family == "gamma":
        k, theta = params["shape"], params["scale"]
        return (k - 1.0) * theta if k >= 1.0 else 0.0  # gamma mode (k-1)θ, else at 0
    if family == "lognormal":
        return float(np.exp(params["mu"] - params["sigma"] ** 2))  # lognormal mode
    if family == "zi_gamma":
        return 0.0  # the zero atom is the mode of a zero-inflated distribution
    if family == "bimodal":
        # the taller component peak (density ∝ weight / sigma) is the mode
        d1 = params["w"] / params["s1"]
        d2 = (1.0 - params["w"]) / params["s2"]
        return params["mu1"] if d1 >= d2 else params["mu2"]
    raise ValueError(f"unknown family: {family}")  # pragma: no cover


@dataclass(frozen=True)
class Truth:
    """The known latent truth behind a synthetic shape.

    ``reference`` is a large sorted oracle sample from the DGP; ``mean``/``mode`` and
    :meth:`quantile` are read off it (tight MC error). :meth:`draw` produces *fresh*
    actuals from the same DGP — used by ``02_summaries`` to test interval coverage.
    """

    name: str
    family: str
    params: dict[str, float]
    reference: NDArray[np.float64]
    mean: float
    mode: float

    def quantile(self, p: float | NDArray[np.float64]) -> NDArray[np.float64]:
        """True quantile(s) of the DGP at probability level(s) ``p``."""
        return np.quantile(self.reference, p)

    def draw(self, n: int, rng: np.random.Generator) -> NDArray[np.float64]:
        """``n`` fresh draws from the same DGP (held-out 'actuals')."""
        return _sample(self.family, self.params, n, rng)


def _make_truth(
    name: str, family: str, params: dict[str, float], rng: np.random.Generator
) -> Truth:
    ref = np.sort(_sample(family, params, _REF_SIZE, rng))
    mode = _analytic_mode(family, params)
    return Truth(name, family, dict(params), ref, float(ref.mean()), mode)


# ---- the distribution zoo ----------------------------------------------------


def distribution_zoo(
    *, n_samples: int = 1024, seed: int = 0
) -> dict[str, tuple[NDArray[np.float32], Truth]]:
    """``{shape_name: (samples (n_samples,), Truth)}`` for the six canonical shapes.

    Call with ``n_samples=32`` for the low-sample regime and ``n_samples=1024`` for
    the pooled regime (``02_summaries`` contrasts the two).
    """
    rng = np.random.default_rng(seed)
    out: dict[str, tuple[NDArray[np.float32], Truth]] = {}
    for name, (family, params) in ZOO_SHAPES.items():
        cell_rng = np.random.default_rng(rng.integers(1 << 62))
        truth = _make_truth(name, family, params, cell_rng)
        samples = _sample(family, params, n_samples, cell_rng).astype(np.float32)
        out[name] = (samples, truth)
    return out


def frame_from_samples(
    samples: NDArray[np.float64], *, level: SpatialLevel = SpatialLevel.PGM
) -> PredictionFrame:
    """Wrap a raw ``(R, S)`` array of posteriors as a ``PredictionFrame``.

    A convenience for the notebooks' coverage / recovery / Monte-Carlo replica loops,
    which build many one-shot frames from arrays of draws; it owns the synthetic index
    (one synthetic ``unit`` per row at ``_BASE_MONTH``) so those cells don't each
    re-hardcode it.
    """
    arr = np.asarray(samples, dtype=np.float32)
    r = arr.shape[0]
    index = SpatioTemporalIndex(
        time=np.full(r, _BASE_MONTH, dtype=np.int64),
        unit=np.arange(r, dtype=np.int64),
        level=level,
    )
    return PredictionFrame(arr, index)


@dataclass(frozen=True)
class ZooFrames:
    """The zoo as the three sibling frames (all on one shared index)."""

    names: list[str]
    truths: list[Truth]
    index: SpatioTemporalIndex
    prediction: PredictionFrame  # (N, S)  — one posterior per shape
    target: TargetFrame  # (N, 1)  — a held-out actual per shape
    features: FeatureFrame  # (N, F, S) — illustrative model inputs


def zoo_frames(
    *, n_samples: int = 1024, seed: int = 0, n_features: int = 2
) -> ZooFrames:
    """Build the distribution zoo as a ``PredictionFrame`` / ``TargetFrame`` /
    ``FeatureFrame`` trio sharing one ``SpatioTemporalIndex`` (one row per shape)."""
    zoo = distribution_zoo(n_samples=n_samples, seed=seed)
    names = list(zoo)
    truths = [zoo[k][1] for k in names]
    samples = np.stack([zoo[k][0] for k in names]).astype(np.float32)  # (N, S)
    n = len(names)

    time = np.full(n, _BASE_MONTH, dtype=np.int64)
    unit = np.arange(_BASE_PRIOGRID, _BASE_PRIOGRID + n, dtype=np.int64)
    index = SpatioTemporalIndex(time=time, unit=unit, level=SpatialLevel.PGM)
    meta = FrameMetadata(model="synthetic-zoo", run_type="notebook", seed=seed)

    prediction = PredictionFrame(samples, index, meta)

    arng = np.random.default_rng(seed + 1)
    actuals = np.array([[float(t.draw(1, arng)[0])] for t in truths], dtype=np.float32)
    target = TargetFrame(actuals, index, meta)

    frng = np.random.default_rng(seed + 2)
    base = samples.mean(axis=1).reshape(n, 1, 1)
    feats = (base + frng.normal(0.0, 1.0, size=(n, n_features, n_samples))).astype(
        np.float32
    )
    feat_names = [f"feature_{i}" for i in range(n_features)]
    features = FeatureFrame(feats, index, feat_names, meta)

    return ZooFrames(names, truths, index, prediction, target, features)


# ---- the cm/pgm reconciliation scenario --------------------------------------


@dataclass(frozen=True)
class CmPgmScenario:
    """A grid (pgm) ↔ country (cm) scenario with an injected mapping + known totals.

    Everything ``03_reconciliation`` needs: a pgm ``PredictionFrame`` of grid
    forecasts, a cm ``PredictionFrame`` of country totals, the injected ``(time,
    priogrid) -> country`` mapping in both ``dict`` and array form, the lattice
    coordinates for the toy map view, and the **true** per-``(time, country)`` total
    (the sum of the cells' true means) to check does-reconciliation-help against.
    """

    months: list[int]
    countries: list[int]
    lattice_shape: tuple[int, int]
    coords: dict[int, tuple[int, int]]  # priogrid_id -> (row, col)
    pgm_to_country: dict[int, int]  # priogrid_id -> country_id
    pgm_index: SpatioTemporalIndex
    cm_index: SpatioTemporalIndex
    pgm_prediction: PredictionFrame  # (n_months * G, S)
    cm_prediction: PredictionFrame  # (n_months * C, S)
    map_keys: NDArray[np.int64]  # (M, 2) (time, priogrid)
    map_vals: NDArray[np.int64]  # (M,) country
    mapping: dict[tuple[int, int], int]  # {(time, priogrid): country}
    country_total_truth: dict[tuple[int, int], float]  # (time, country) -> true sum
    cell_total_truth: dict[tuple[int, int], float]  # (time, priogrid) -> true cell mean


def cm_pgm_scenario(
    *,
    n_samples: int = 256,
    seed: int = 0,
    lattice: tuple[int, int] = (4, 4),
    n_months: int = 3,
    n_countries: int = 2,
) -> CmPgmScenario:
    """Build a small reproducible cm/pgm reconciliation scenario.

    The grid cells are laid on a ``lattice`` (so the notebook can draw a toy map), the
    countries split the columns, and each cell draws from a quiet-leaning family. The
    cm country forecast is the true total times per-draw lognormal noise — so the grid
    draws do **not** already sum to the country forecast (that is the job of
    reconciliation), and the *true* total is known for the does-it-help check.
    """
    nrows, ncols = lattice
    rng = np.random.default_rng(seed)

    priogrids: list[int] = []
    coords: dict[int, tuple[int, int]] = {}
    pgm_to_country: dict[int, int] = {}
    for r in range(nrows):
        for c in range(ncols):
            pg = _BASE_PRIOGRID + r * ncols + c
            priogrids.append(pg)
            coords[pg] = (r, c)
            pgm_to_country[pg] = _BASE_COUNTRY + (c * n_countries) // ncols
    countries = sorted(set(pgm_to_country.values()))
    months = [_BASE_MONTH + i for i in range(n_months)]
    month_factor = {m: 1.0 + 0.25 * i for i, m in enumerate(months)}

    # per-cell DGP (round-robin families, quiet-leaning) + its true (base) mean
    fam_cycle = [
        "zero_inflated",
        "right_skewed_gamma",
        "heavy_tailed",
        "zero_inflated",
        "near_symmetric",
        "right_skewed_lognormal",
    ]
    cell_family: dict[int, str] = {}
    cell_params: dict[int, dict[str, float]] = {}
    cell_base_mean: dict[int, float] = {}
    for k, pg in enumerate(priogrids):
        family, params = ZOO_SHAPES[fam_cycle[k % len(fam_cycle)]]
        cell_family[pg] = family
        cell_params[pg] = params
        cr = np.random.default_rng(rng.integers(1 << 62))
        cell_base_mean[pg] = float(_sample(family, params, _REF_SIZE, cr).mean())

    # true per-(time, cell) means and per-(time, country) totals
    cell_total_truth: dict[tuple[int, int], float] = {
        (m, pg): month_factor[m] * cell_base_mean[pg]
        for m in months
        for pg in priogrids
    }
    country_total_truth: dict[tuple[int, int], float] = {}
    for m in months:
        for country in countries:
            country_total_truth[(m, country)] = sum(
                cell_total_truth[(m, pg)]
                for pg in priogrids
                if pgm_to_country[pg] == country
            )

    # pgm grid forecasts (time-major rows)
    pg_time, pg_unit = [], []
    pg_vals: list[NDArray[np.float64]] = []
    for m in months:
        for pg in priogrids:
            cr = np.random.default_rng(rng.integers(1 << 62))
            pg_time.append(m)
            pg_unit.append(pg)
            draws = _sample(cell_family[pg], cell_params[pg], n_samples, cr)
            pg_vals.append(month_factor[m] * draws)
    pgm_index = SpatioTemporalIndex(
        time=np.array(pg_time, dtype=np.int64),
        unit=np.array(pg_unit, dtype=np.int64),
        level=SpatialLevel.PGM,
    )
    pgm_prediction = PredictionFrame(
        np.array(pg_vals, dtype=np.float32),
        pgm_index,
        FrameMetadata(model="synthetic-pgm", run_type="notebook", seed=seed),
    )

    # cm country forecasts: true total × per-draw lognormal noise
    cm_time, cm_unit = [], []
    cm_vals: list[NDArray[np.float64]] = []
    crng = np.random.default_rng(seed + 5)
    for m in months:
        for country in countries:
            tt = country_total_truth[(m, country)]
            cm_time.append(m)
            cm_unit.append(country)
            cm_vals.append(tt * np.exp(crng.normal(0.0, 0.12, n_samples)))
    cm_index = SpatioTemporalIndex(
        time=np.array(cm_time, dtype=np.int64),
        unit=np.array(cm_unit, dtype=np.int64),
        level=SpatialLevel.CM,
    )
    cm_prediction = PredictionFrame(
        np.array(cm_vals, dtype=np.float32),
        cm_index,
        FrameMetadata(model="synthetic-cm", run_type="notebook", seed=seed),
    )

    # injected mapping, both forms (dict for cross_level_align; arrays for the module)
    map_keys = np.array([[m, pg] for m in months for pg in priogrids], dtype=np.int64)
    map_vals = np.array(
        [pgm_to_country[pg] for _ in months for pg in priogrids], dtype=np.int64
    )
    mapping = {
        (int(m), int(pg)): int(pgm_to_country[pg]) for m in months for pg in priogrids
    }

    return CmPgmScenario(
        months=months,
        countries=countries,
        lattice_shape=lattice,
        coords=coords,
        pgm_to_country=pgm_to_country,
        pgm_index=pgm_index,
        cm_index=cm_index,
        pgm_prediction=pgm_prediction,
        cm_prediction=cm_prediction,
        map_keys=map_keys,
        map_vals=map_vals,
        mapping=mapping,
        country_total_truth=country_total_truth,
        cell_total_truth=cell_total_truth,
    )
