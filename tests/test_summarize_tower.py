"""The constrained-nested HDI tower + tower-tip point + bimodality flag (ADR-019).

Categories per ADR-005:
  🟩 Green — the laws hold, vectorized == per-row reference, bundle == trio.
  🟫 Beige — realistic edges: S=1, tiny S, all-equal, tail pinning, FF axes.
  🟥 Red — adversarial: the zero boundary, map_estimate independence, NaN locality.
"""

from __future__ import annotations

import tracemalloc

import numpy as np
import pytest
from numpy.typing import NDArray

from views_frames import (
    FeatureFrame,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
    TargetFrame,
)
from views_frames_summarize import (
    TowerSummary,
    bimodality,
    hdi_tower,
    map_estimate,
    summarize_tower,
    tower_point,
)
from views_frames_summarize.tower import _CANONICAL_FLOORS


def _index(n):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=SpatialLevel.PGM,
    )


def _pf(rows):
    arr = np.array(rows, dtype=np.float32)
    return PredictionFrame(arr, _index(arr.shape[0]))


def _ff(values):
    arr = np.asarray(values, dtype=np.float32)
    return FeatureFrame(
        arr, _index(arr.shape[0]), [f"f{i}" for i in range(arr.shape[1])]
    )


# --- per-row scalar references (the golden the vectorized engine must match) --


def _ref_tower(row: NDArray[np.float32], floors) -> list[tuple[float, float]]:
    s = np.sort(row)
    n = s.size
    out: list[tuple[float, float]] = []
    inner: tuple[float, float] | None = None
    for m in floors:
        k = int(np.floor(m * n))
        if inner is None:
            if k <= 0:
                lo = hi = float(s[n // 2])
            else:
                w = s[k:] - s[: n - k]
                i = int(np.argmin(w))
                lo, hi = float(s[i]), float(s[i + k])
        elif k <= 0:
            lo, hi = inner
        elif k >= n - 1:
            lo, hi = float(s[0]), float(s[-1])
        else:
            a, b = s[: n - k], s[k:]
            ok = (a <= inner[0]) & (b >= inner[1])
            w = np.where(ok, b - a, np.inf)
            i = int(np.argmin(w))
            lo, hi = float(a[i]), float(b[i])
        out.append((lo, hi))
        inner = (lo, hi)
    return out


def _ref_tip(row: NDArray[np.float32]) -> float:
    s = np.sort(row)
    n = s.size
    if float(s.max()) <= 1.0:
        return 0.0
    k0 = int(np.floor(0.05 * n))
    if k0 <= 0:
        return float(s[n // 2])
    w = s[k0:] - s[: n - k0]
    i = int(np.argmin(w))
    return float((s[i + k0 // 2] + s[i + (k0 + 1) // 2]) * 0.5)


# =========================== 🟩 GREEN — happy path ===========================


def test_green_tower_golden_row():
    # samples [1,2,3,4,100]: for mass 0.5 (k=2) the shortest 3-window is (1,3);
    # wider floors must contain it. Hand-checkable nesting.
    pf = _pf([[1.0, 2.0, 3.0, 4.0, 100.0]])
    out = hdi_tower(pf, masses=(0.5, 0.9))
    assert out.shape == (1, 2, 2)
    assert np.array_equal(out[0, 0], [1.0, 3.0])  # 50% = shortest 3 of 5
    lo, hi = out[0, 1]
    assert lo <= 1.0 and hi >= 3.0  # 90% contains the 50%


def test_green_tip_recovers_unimodal_peak():
    rng = np.random.default_rng(0)
    samples = rng.normal(10.0, 0.5, 5000).astype(np.float32)
    pf = PredictionFrame(samples[np.newaxis, :], _index(1))
    out = tower_point(pf)
    assert isinstance(out, PredictionFrame)
    assert abs(float(out.values[0, 0]) - 10.0) < 0.3


@pytest.mark.parametrize("seed", [0, 1, 7, 13])
@pytest.mark.parametrize("shape", [(20, 64), (50, 257), (8, 3, 200)])
def test_green_vectorized_matches_scalar_reference(seed, shape):
    rng = np.random.default_rng(seed)
    values = rng.lognormal(0.5, 0.8, shape).astype(np.float32)
    values[rng.random(shape) < 0.15] = 0.0
    frame = (
        _ff(values) if len(shape) == 3 else PredictionFrame(values, _index(shape[0]))
    )
    masses = tuple(float(m) for m in _CANONICAL_FLOORS)  # request the whole grid

    tower = hdi_tower(frame, masses=masses)
    tip = tower_point(frame).values[..., 0]
    flat = values.reshape(-1, shape[-1])
    for r, row in enumerate(flat):
        ref = _ref_tower(row, masses)
        got = tower.reshape(-1, len(masses), 2)[r]
        if float(row.max()) <= 1.0:
            assert np.array_equal(got, np.zeros_like(got))
        else:
            assert np.array_equal(got, np.asarray(ref, dtype=np.float32))
        np.testing.assert_allclose(
            tip.reshape(-1)[r], _ref_tip(row), rtol=1e-5, atol=1e-6
        )


@pytest.mark.parametrize("seed", [0, 2, 5])
def test_green_laws_nesting_tip_reproducibility(seed):
    rng = np.random.default_rng(seed)
    pf = PredictionFrame(
        rng.lognormal(0.3, 1.0, (40, 300)).astype(np.float32), _index(40)
    )
    tower = hdi_tower(pf, masses=(0.5, 0.9, 0.99))
    # nesting: lowers non-increasing, uppers non-decreasing across the M axis
    assert np.all(np.diff(tower[..., 0], axis=-1) <= 1e-6)
    assert np.all(np.diff(tower[..., 1], axis=-1) >= -1e-6)
    # tip inside the narrowest requested floor
    tip = tower_point(pf).values[:, 0]
    assert np.all(tip >= tower[:, 0, 0] - 1e-6)
    assert np.all(tip <= tower[:, 0, 1] + 1e-6)
    # reproducibility: the 50% interval is invariant to the other requested masses
    just_50 = hdi_tower(pf, masses=(0.5,))
    assert np.array_equal(just_50[:, 0, :], tower[:, 0, :])
    weird = hdi_tower(pf, masses=(0.5, 0.123, 0.876))
    assert np.array_equal(weird[:, 0, :], tower[:, 0, :])


def test_green_bundle_equals_trio():
    rng = np.random.default_rng(3)
    v = rng.lognormal(0.4, 0.8, (12, 256)).astype(np.float32)
    v[0] = 0.0
    pf = PredictionFrame(v, _index(12))
    s = summarize_tower(pf, masses=(0.5, 0.9, 0.99))
    assert isinstance(s, TowerSummary)
    assert np.array_equal(s.point.values, tower_point(pf).values)
    assert np.array_equal(s.intervals, hdi_tower(pf, masses=(0.5, 0.9, 0.99)))
    assert np.array_equal(s.bimodal, bimodality(pf))
    assert np.array_equal(s.masses, np.array([0.5, 0.9, 0.99], dtype=np.float32))


def test_green_clear_bimodal_is_flagged():
    rng = np.random.default_rng(1)
    twopeak = np.concatenate([rng.normal(2.0, 0.4, 500), rng.normal(20.0, 1.0, 500)])
    atom_bump = np.concatenate([np.zeros(400), rng.normal(10.0, 1.0, 600)])
    pf = PredictionFrame(np.stack([twopeak, atom_bump]).astype(np.float32), _index(2))
    flag = bimodality(pf)
    assert flag.shape == (2, 1)
    assert flag[0, 0] == 1.0 and flag[1, 0] == 1.0


def test_green_skewed_unimodal_not_flagged():
    rng = np.random.default_rng(4)
    pf = PredictionFrame(rng.gamma(2.5, 1.5, (30, 1024)).astype(np.float32), _index(30))
    assert bimodality(pf).sum() == 0.0  # right-skewed unimodal must read as unimodal


# =========================== 🟫 BEIGE — realistic edges =======================


def test_beige_single_sample():
    pf = _pf([[5.0], [0.0]])  # S=1
    tower = hdi_tower(pf, masses=(0.5, 0.99))
    assert np.array_equal(tower[0], [[5.0, 5.0], [5.0, 5.0]])  # degenerate point
    assert np.array_equal(tower[1], [[0.0, 0.0], [0.0, 0.0]])  # quiet → 0
    assert np.array_equal(tower_point(pf).values[:, 0], [5.0, 0.0])
    assert bimodality(pf).sum() == 0.0


def test_beige_all_equal_row():
    pf = _pf([[7.0] * 50])
    tower = hdi_tower(pf, masses=(0.5, 0.9))
    assert np.allclose(tower[0], 7.0)
    assert abs(float(tower_point(pf).values[0, 0]) - 7.0) < 1e-6
    assert bimodality(pf)[0, 0] == 0.0


def test_beige_tiny_sample_k0_floor_is_median():
    # S=5: floor(0.05*5)=0 → narrowest floor degenerates to the median; floor(0.10*5)=0
    # → the next floor inherits it (exercises _shortest_containing's k<=0 branch).
    pf = _pf([[2.0, 4.0, 6.0, 8.0, 10.0]])
    assert abs(float(tower_point(pf).values[0, 0]) - 6.0) < 1e-6  # median
    tower = hdi_tower(pf, masses=(0.05, 0.10))
    assert np.array_equal(tower[0, 0], [6.0, 6.0])
    assert np.array_equal(tower[0, 1], [6.0, 6.0])


def test_beige_single_positive_among_zeros_not_bimodal():
    row = np.zeros(200, dtype=np.float32)
    row[0] = 9.0  # one positive draw, max > 1 so NOT zero-short-circuited
    pf = PredictionFrame(row[np.newaxis, :], _index(1))
    assert bimodality(pf)[0, 0] == 0.0  # a lone outlier is not a second mode


def test_beige_requested_tail_pins_to_fine_tail_not_095():
    # a uniform 5% grid would top out at 0.95; the fixed fine tail must keep 0.99.
    rng = np.random.default_rng(0)
    pf = PredictionFrame(rng.lognormal(0, 1, (5, 2000)).astype(np.float32), _index(5))
    s = summarize_tower(pf, masses=(0.99,))
    assert s.masses[0] == np.float32(0.99)
    # 0.99 is strictly wider than 0.95 — it did not silently pin down to 0.95.
    at_095 = hdi_tower(pf, masses=(0.95,))
    assert np.all(s.intervals[:, 0, 1] >= at_095[:, 0, 1] - 1e-6)


def test_beige_pinning_is_deterministic_on_ties():
    # 0.075 is equidistant from 0.05 and 0.10; argmin must pick the lower floor, always.
    pf = _pf([list(range(1, 41))])
    a = hdi_tower(pf, masses=(0.075,))
    b = hdi_tower(pf, masses=(0.05,))
    assert np.array_equal(a[:, 0, :], b[:, 0, :])


def test_beige_featureframe_axes_and_identifiers_preserved():
    rng = np.random.default_rng(2)
    ff = _ff(rng.lognormal(0, 1, (4, 3, 128)).astype(np.float32))
    assert hdi_tower(ff).shape == (4, 3, 3, 2)
    tip = tower_point(ff)
    assert isinstance(tip, FeatureFrame)
    assert tip.values.shape == (4, 3, 1)
    assert tip.feature_names == ff.feature_names
    assert np.array_equal(tip.identifiers["unit"], ff.identifiers["unit"])
    assert bimodality(ff).shape == (4, 3, 1)


def test_beige_targetframe_supported():
    tf = TargetFrame(np.array([[0.0], [5.0]], dtype=np.float32), _index(2))
    assert isinstance(tower_point(tf), TargetFrame)
    assert hdi_tower(tf).shape == (2, 3, 2)


# =========================== 🟥 RED — adversarial =============================


def test_red_zero_cutoff_boundary():
    # max exactly == 1.0 collapses; max just above does not. The boundary is a contract.
    at = _pf([[0.0, 1.0, 1.0, 1.0]])
    above = _pf([[0.0, 1.0, 1.0, 1.0 + 1e-3]])
    assert float(tower_point(at).values[0, 0]) == 0.0
    assert np.array_equal(hdi_tower(at, masses=(0.9,))[0, 0], [0.0, 0.0])
    assert float(tower_point(above).values[0, 0]) > 0.0


def test_red_tower_point_independent_of_frozen_map_estimate():
    # Right-skewed, low-sample rows: map_estimate's binned histogram mode and the
    # unbinned tower tip are computed differently and must be free to disagree (the
    # C-32 motivation). They may coincide on some rows; independence means they do
    # NOT coincide everywhere. The frozen map_estimate is exercised, never modified.
    rng = np.random.default_rng(11)
    rows = rng.gamma(2.0, 1.5, (20, 60)).astype(np.float32)
    pf = PredictionFrame(rows, _index(20))
    tips = tower_point(pf).values[:, 0]
    modes = map_estimate(pf).values[:, 0]
    assert np.any(tips != modes)  # independent estimators — free to disagree


@pytest.mark.parametrize("bad", [1.0, 1.5, 0.0, -0.2, (0.5, 2.0)])
def test_red_out_of_range_mass_fails_loud(bad):
    # A mass outside (0,1) must raise, not silently pin to the nearest floor (ADR-008).
    pf = _pf([[1.0, 2.0, 3.0, 4.0]])
    masses = bad if isinstance(bad, tuple) else (bad,)
    with pytest.raises(ValueError, match="open interval"):
        hdi_tower(pf, masses=masses)


def test_red_nan_row_stays_local_and_does_not_crash():
    # Frames do not ban NaN (out-of-contract input). A NaN in one row must not corrupt
    # or crash the others — failure stays localized.
    good = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=np.float32)
    bad = good.copy()
    bad[0] = np.nan
    pf = PredictionFrame(np.stack([good, bad]), _index(2))
    tower = hdi_tower(pf, masses=(0.5,))
    tip = tower_point(pf).values[:, 0]
    # the clean row is unaffected by its neighbour's NaN
    clean_ref = _ref_tower(good, (0.5,))[0]
    assert np.array_equal(tower[0, 0], np.asarray(clean_ref, dtype=np.float32))
    assert np.isfinite(tip[0])


# --- scale guard: memory must not scale with rows ----------------------------


@pytest.mark.parametrize(
    "fn, name",
    [
        (lambda pf: hdi_tower(pf, masses=(0.5, 0.9, 0.99)), "hdi_tower"),
        (lambda pf: bimodality(pf), "bimodality"),
        (lambda pf: tower_point(pf), "tower_point"),
    ],
)
def test_tower_memory_is_bounded_at_grid_scale(fn, name):
    n, s = 1_000_000, 32
    rng = np.random.default_rng(0)
    pf = PredictionFrame(rng.random((n, s), dtype=np.float32), _index(n))
    input_bytes = n * s * 4
    tracemalloc.start()
    tracemalloc.reset_peak()
    fn(pf)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < input_bytes, (
        f"{name} peak {peak / 1e6:.0f} MB scales with rows*S "
        f"(input {input_bytes / 1e6:.0f} MB) — blocking regressed"
    )
