"""The constrained-nested HDI tower + tower-tip point + bimodality flag (ADR-019).

Built **outside-in** (widest floor first, each narrower floor contained in its parent);
the tip is the median of the configurable ``tip_mass`` floor. Robust to minority
duplicated draws (register C-44).

Categories per ADR-005:
  🟩 Green — the laws hold, vectorized == per-row reference, bundle == trio.
  🟫 Beige — realistic edges: S=1, tiny S, all-equal, tail pinning, FF/TF axes.
  🟥 Red — adversarial: the truth table A–L, real faoapi cells, duplicate sweeps,
            NaN/inf locality, multimodality, the zero boundary, map_estimate parity.
"""

from __future__ import annotations

import contextlib
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
    config,
    hdi_tower,
    map_estimate,
    summarize_tower,
    tower_point,
)

_FLOORS = config.canonical_floors()
_TIP_MASS = float(config.get("tip_mass"))


@contextlib.contextmanager
def _cutoff(value):
    """Temporarily set the optional magnitude ``zero_cutoff`` (restored after)."""
    prev = config.TOWER_CONFIG["zero_cutoff"]
    config.TOWER_CONFIG["zero_cutoff"] = value
    try:
        yield
    finally:
        config.TOWER_CONFIG["zero_cutoff"] = prev


def _ref_zeroed(row) -> bool:
    """Mirror of `_zero_mask`: the optional magnitude cutoff (off by default = None)."""
    cut = config.get("zero_cutoff")
    return cut is not None and float(np.asarray(row).max()) <= cut


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


def _row(draws):
    return PredictionFrame(np.asarray(draws, dtype=np.float32)[None, :], _index(1))


def _tp(draws):
    return float(tower_point(_row(draws)).values.reshape(-1)[0])


# --- per-row scalar references (the golden the vectorized engine must match) --
# Mirror tower.py exactly: outside-in, leftmost tie-break, a k<=0 floor is the middle
# *sample* (a real draw), the tip is the *averaged* median of the tip_mass floor.


def _ref_seed(s, k):
    n = s.size
    if k <= 0:
        return float(s[n // 2]), float(s[n // 2])
    if k >= n - 1:
        return float(s[0]), float(s[-1])
    w = s[k:] - s[: n - k]
    i = int(np.argmin(w))
    return float(s[i]), float(s[i + k])


def _ref_span(s, lo, hi):
    inside = (s >= lo) & (s <= hi)
    return int(np.argmax(inside)), int(inside.sum())


def _ref_mid_sample_in(s, lo, hi):
    first, cnt = _ref_span(s, lo, hi)
    return float(s[first + (cnt - 1) // 2])


def _ref_median_in(s, lo, hi):
    first, cnt = _ref_span(s, lo, hi)
    return float((s[first + (cnt - 1) // 2] + s[first + cnt // 2]) * 0.5)


def _ref_contained_in(s, k, plo, phi):
    n = s.size
    if k <= 0:
        v = _ref_mid_sample_in(s, plo, phi)
        return v, v
    starts, ends = s[: n - k], s[k:]
    ok = (starts >= plo) & (ends <= phi)
    w = np.where(ok, ends - starts, np.inf)
    i = int(np.argmin(w))
    return float(starts[i]), float(ends[i])


def _ref_tower(row: NDArray[np.float32], floors) -> list[tuple[float, float]]:
    s = np.sort(row)
    n = s.size
    f = len(floors)
    out: list[tuple[float, float]] = [(0.0, 0.0)] * f
    plo: float | None = None
    phi: float | None = None
    for j in range(f - 1, -1, -1):  # widest → narrowest
        k = int(np.floor(floors[j] * n))
        if plo is None or phi is None:
            lo, hi = _ref_seed(s, k)
        else:
            lo, hi = _ref_contained_in(s, k, plo, phi)
        out[j] = (lo, hi)
        plo, phi = lo, hi
    return out


def _ref_hdi(row: NDArray[np.float32], masses) -> list[tuple[float, float]]:
    """Mirror of ``hdi_tower``: full outside-in tower, pin each mass; opt-in zero."""
    if _ref_zeroed(row):
        return [(0.0, 0.0)] * len(masses)
    full = _ref_tower(row, _FLOORS)
    return [full[int(np.argmin(np.abs(_FLOORS - m)))] for m in masses]


def _ref_tip(row: NDArray[np.float32]) -> float:
    if _ref_zeroed(row):
        return 0.0
    s = np.sort(row)
    tlo, thi = _ref_hdi(row, (_TIP_MASS,))[0]
    return _ref_median_in(s, tlo, thi)


# =========================== 🟩 GREEN — happy path ===========================


def test_green_outside_in_golden_row():
    # samples [1,2,3,4,100]: the 50% floor (shortest 3 of 5, contained in the wider
    # floors) excludes the 100 outlier; the band matches the reference and nests.
    pf = _pf([[1.0, 2.0, 3.0, 4.0, 100.0]])
    out = hdi_tower(pf, masses=(0.5, 0.9))
    assert out.shape == (1, 2, 2)
    ref = _ref_hdi(np.array([1.0, 2.0, 3.0, 4.0, 100.0], np.float32), (0.5, 0.9))
    assert np.array_equal(out[0], np.asarray(ref, dtype=np.float32))
    assert out[0, 0, 1] < 100.0  # the 50% band sheds the outlier
    assert out[0, 1, 0] <= out[0, 0, 0] and out[0, 1, 1] >= out[0, 0, 1]  # nesting


def test_green_tip_recovers_unimodal_peak():
    rng = np.random.default_rng(0)
    samples = rng.normal(10.0, 0.5, 5000).astype(np.float32)
    out = tower_point(_row(samples))
    assert isinstance(out, PredictionFrame)
    assert abs(float(out.values[0, 0]) - 10.0) < 0.3


@pytest.mark.parametrize("seed", [0, 1, 7, 13])
@pytest.mark.parametrize("shape", [(20, 64), (50, 257), (8, 3, 200)])
def test_green_vectorized_matches_scalar_reference(seed, shape):
    rng = np.random.default_rng(seed)
    values = rng.lognormal(0.5, 0.8, shape).astype(np.float32)
    values[rng.random(shape) < 0.15] = 0.0  # zero-inflate, like the real domain
    frame = (
        _ff(values) if len(shape) == 3 else PredictionFrame(values, _index(shape[0]))
    )
    masses = tuple(float(m) for m in _FLOORS)  # request the whole grid

    tower = hdi_tower(frame, masses=masses).reshape(-1, len(masses), 2)
    tip = tower_point(frame).values[..., 0].reshape(-1)
    flat = values.reshape(-1, shape[-1])
    for r, row in enumerate(flat):
        assert np.array_equal(
            tower[r], np.asarray(_ref_hdi(row, masses), dtype=np.float32)
        )
        np.testing.assert_allclose(tip[r], _ref_tip(row), rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize("seed", [0, 2, 5])
def test_green_laws_nesting_and_reproducibility(seed):
    rng = np.random.default_rng(seed)
    pf = PredictionFrame(
        rng.lognormal(0.3, 1.0, (40, 300)).astype(np.float32), _index(40)
    )
    tower = hdi_tower(pf, masses=(0.5, 0.9, 0.99))
    # nesting: lowers non-increasing, uppers non-decreasing across the M axis
    assert np.all(np.diff(tower[..., 0], axis=-1) <= 1e-6)
    assert np.all(np.diff(tower[..., 1], axis=-1) >= -1e-6)
    # reproducibility: the 50% interval is invariant to the other requested masses
    assert np.array_equal(hdi_tower(pf, masses=(0.5,))[:, 0, :], tower[:, 0, :])
    weird = hdi_tower(pf, masses=(0.5, 0.123, 0.876))
    assert np.array_equal(weird[:, 0, :], tower[:, 0, :])


@pytest.mark.parametrize("seed", [0, 2, 5])
def test_green_law_tip_in_tip_mass_floor(seed):
    # The restated law (ADR-019): the tip lies inside the configured tip_mass floor.
    rng = np.random.default_rng(seed)
    v = rng.lognormal(0.3, 1.0, (40, 300)).astype(np.float32)
    v[rng.random(v.shape) < 0.2] = 0.0
    pf = PredictionFrame(v, _index(40))
    tip = tower_point(pf).values[:, 0]
    floor = hdi_tower(pf, masses=(_TIP_MASS,))
    assert np.all(tip >= floor[:, 0, 0] - 1e-6)
    assert np.all(tip <= floor[:, 0, 1] + 1e-6)


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
    assert np.array_equal(tower[1], [[0.0, 0.0], [0.0, 0.0]])  # all-zero row → 0
    assert np.array_equal(tower_point(pf).values[:, 0], [5.0, 0.0])
    assert bimodality(pf).sum() == 0.0


def test_beige_all_equal_row():
    pf = _pf([[7.0] * 50])
    tower = hdi_tower(pf, masses=(0.5, 0.9))
    assert np.allclose(tower[0], 7.0)
    assert abs(_tp([7.0] * 50) - 7.0) < 1e-6
    assert bimodality(pf)[0, 0] == 0.0


def test_beige_tiny_sample_tip_is_tip_mass_shorth():
    # S=5, tip_mass=0.5 → the 50% floor is the shortest 3 of [2,4,6,8,10] = (2,4,6),
    # whose median is 4.0 (NOT the global median 6.0 — the tip is the shorth, not the
    # row median). Narrow floors (k<=0) collapse to a real sample and stay nested.
    pf = _pf([[2.0, 4.0, 6.0, 8.0, 10.0]])
    assert abs(_tp([2.0, 4.0, 6.0, 8.0, 10.0]) - 4.0) < 1e-6
    tower = hdi_tower(pf, masses=(0.05, 0.5))
    assert tower[0, 0, 0] >= tower[0, 1, 0] - 1e-6  # 5% nested in 50%
    assert tower[0, 0, 1] <= tower[0, 1, 1] + 1e-6


def test_beige_single_positive_among_zeros_not_bimodal():
    row = np.zeros(200, dtype=np.float32)
    row[0] = 9.0  # one positive draw, max > 1 so NOT zero-short-circuited
    assert bimodality(_row(row))[0, 0] == 0.0  # a lone outlier is not a second mode


def test_beige_high_mass_tail_pins_exactly():
    rng = np.random.default_rng(0)
    pf = PredictionFrame(rng.lognormal(0, 1, (5, 2000)).astype(np.float32), _index(5))
    assert summarize_tower(pf, masses=(0.95,)).masses[0] == np.float32(0.95)
    assert summarize_tower(pf, masses=(0.99,)).masses[0] == np.float32(0.99)
    at_099 = hdi_tower(pf, masses=(0.99,))
    at_095 = hdi_tower(pf, masses=(0.95,))
    assert np.all(at_099[:, 0, 1] >= at_095[:, 0, 1] - 1e-6)


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


def test_beige_duplicate_body_value_is_unimodal():
    # 100 exact copies of 3.0 + a smooth tail: a *majority* duplicate is the real mode,
    # not an outlier — the tip is 3.0 and the row reads unimodal.
    rng = np.random.default_rng(0)
    row = np.concatenate([np.full(100, 3.0), rng.normal(3.0, 0.3, 28)]).astype(
        np.float32
    )
    assert abs(_tp(row) - 3.0) < 0.3
    assert bimodality(_row(row))[0, 0] == 0.0


# =========================== 🟥 RED — adversarial =============================

# The bug report truth table (register C-44): a minority duplicated value must not
# hijack the tip or the bands. S=32 rows; "correct mode" is visually unambiguous.

_TRUTH_TABLE = [
    ("A_two_zeros_thirty_twos", [0.0, 0.0] + [2.0] * 30, 2.0),
    ("E_three_zeros_29_threes", [0.0, 0.0, 0.0] + [3.0] * 29, 3.0),
    ("F_thirty_twos_two_fives", [2.0] * 30 + [5.0, 5.0], 2.0),
    ("H_thirty_twos_two_ones", [2.0] * 30 + [1.0, 1.0], 2.0),
    ("J_thirty_twos_two_zeros", [2.0] * 30 + [0.0, 0.0], 2.0),
]


@pytest.mark.parametrize(
    "name,draws,expected", _TRUTH_TABLE, ids=[t[0] for t in _TRUTH_TABLE]
)
def test_red_minority_duplicate_does_not_capture_the_tip(name, draws, expected):
    assert _tp(draws) == expected


def test_red_minority_zero_spike_does_not_drag_the_intervals():
    # Two zeros among thirty 2.0s: the old inside-out build dragged every band to [0,2];
    # outside-in keeps the body bands on [2,2] (only the >94% band must reach a zero).
    a = _row([0.0, 0.0] + [2.0] * 30)
    lo, hi = hdi_tower(a, masses=(0.5,))[0, 0]
    assert (float(lo), float(hi)) == (2.0, 2.0)
    assert float(hdi_tower(a, masses=(0.9,))[0, 0, 1]) == 2.0


def test_red_lone_duplicate_pair_in_distinct_body_does_not_win():
    # Case L: thirty DISTINCT body values in [0.1,1.9] + a lone 3.0 pair. The pair is
    # the unique zero-width interval — a naive tie-break (the old _select_window) chose
    # it. Outside-in sheds it: the tip is the body (~1.0), never 3.0.
    draws = list(np.linspace(0.1, 1.9, 30)) + [3.0, 3.0]
    tp = _tp(draws)
    assert 0.1 <= tp <= 1.9 and tp != 3.0
    # The tip and the central 50%/80% bands sit on the body, shedding the outlier. The
    # wide ≥90% coverage bands legitimately reach the 6%-mass tail at 3.0 (nesting is
    # preserved) — the old failure was the *tip* and the *tight* band collapsing.
    band = hdi_tower(_row(draws), masses=(0.5, 0.8))
    assert float(band[0, 0, 1]) < 3.0 and float(band[0, 1, 1]) < 3.0


def test_red_majority_duplicate_is_the_mode():
    # The guard against over-correction: when the spike is the genuine MAJORITY, it IS
    # the mode and must be returned.
    assert _tp([0.0] * 25 + [5.0] * 7) == 0.0  # 25/32 zeros → 0
    assert _tp([4.0] * 20 + list(np.linspace(0.1, 1.0, 12))) == 4.0  # 20/32 fours → 4


@pytest.mark.parametrize("k", [0, 1, 2, 3, 5, 8])
def test_red_duplicate_count_sweep(k):
    # k zeros + (32-k) twos, k below the tip-floor majority: the old bug fired at k=2;
    # outside-in returns the body 2.0 for every minority count.
    assert _tp([0.0] * k + [2.0] * (32 - k)) == 2.0


@pytest.mark.parametrize("val", [0.0, 0.01, 1000.0, 1e6, -5.0])
def test_red_minority_duplicate_at_value_extremes(val):
    # Two duplicates of an extreme value among a clear body at 2.0: the body wins.
    draws = [2.0] * 30 + [val, val]
    assert _tp(draws) == 2.0


def test_red_minority_high_outlier_in_widest_band_only():
    # A huge minority duplicate is shed from the body bands but the *widest* band (99%,
    # which must hold ~all samples) still contains it — nesting is honest re: the tail.
    draws = [2.0] * 30 + [1e6, 1e6]
    assert _tp(draws) == 2.0
    assert float(hdi_tower(_row(draws), masses=(0.5,))[0, 0, 1]) == 2.0
    assert float(hdi_tower(_row(draws), masses=(0.99,))[0, 0, 1]) == 1e6


# Real FAO forecast cells (pred_ln_sb_best, 32 draws) that collapsed to 0 under the bug.

_REAL_416 = [
    0,
    0,
    0.15,
    0.21,
    0.27,
    0.31,
    0.35,
    0.36,
    0.54,
    0.64,
    0.71,
    1.15,
    1.24,
    1.32,
    1.38,
    1.49,
    1.64,
    1.65,
    1.83,
    1.88,
    1.94,
    2.61,
    2.63,
    2.65,
    2.67,
    2.85,
    2.92,
    3.65,
    4.05,
    4.51,
    5.91,
    0,
]
_REAL_425 = [
    0,
    0,
    0.07,
    0.12,
    0.28,
    0.3,
    0.34,
    0.37,
    0.39,
    0.4,
    0.41,
    0.59,
    0.61,
    0.76,
    0.81,
    1.27,
    1.53,
    1.78,
    2.12,
    2.22,
    2.37,
    2.47,
    3.35,
    3.39,
    3.79,
    3.97,
    3.98,
    4.2,
    4.36,
    4.4,
    4.85,
    4.9,
]


@pytest.mark.parametrize("draws", [_REAL_416, _REAL_425], ids=["m416", "m425"])
def test_red_real_faoapi_cells_no_longer_collapse(draws):
    # These have only 2-3 exact zeros; under the bug tower_point == 0.0 (signal loss).
    # Now the tip is the robust body shorth: nonzero, finite, == the scalar reference.
    tp = _tp(draws)
    assert tp > 0.0
    assert np.isfinite(tp)
    np.testing.assert_allclose(tp, _ref_tip(np.asarray(draws, np.float32)), rtol=1e-5)


def test_red_multimodal_tip_lands_in_a_cluster_not_a_gap():
    # Three separated clusters: the tip must be inside one of them, never in a gap, and
    # the row is flagged bimodal.
    rng = np.random.default_rng(7)
    draws = np.concatenate(
        [
            rng.normal(1.0, 0.1, 350),
            rng.normal(10.0, 0.1, 350),
            rng.normal(20.0, 0.1, 350),
        ]
    ).astype(np.float32)
    tp = _tp(draws)
    assert min(abs(tp - c) for c in (1.0, 10.0, 20.0)) < 0.5  # in a cluster
    assert bimodality(_row(draws))[0, 0] == 1.0


def test_red_optin_zero_cutoff_boundary():
    # The magnitude cutoff is OFF by default (C-45); it must NOT zero a sub-1 row.
    at = _pf([[0.0, 1.0, 1.0, 1.0]])
    assert float(tower_point(at).values[0, 0]) > 0.0  # default off → density tip, not 0
    # Opt-in: with zero_cutoff set, max == cutoff collapses, just above does not.
    with _cutoff(1.0):
        above = _pf([[0.0, 1.0, 1.0, 1.0 + 1e-3]])
        assert float(tower_point(at).values[0, 0]) == 0.0
        assert np.array_equal(hdi_tower(at, masses=(0.9,))[0, 0], [0.0, 0.0])
        assert float(tower_point(above).values[0, 0]) > 0.0


def test_red_default_does_not_magnitude_zero_subunit_distributions():
    # The heart of C-45: by default, sub-1 distributions are NOT zeroed.
    rng = np.random.default_rng(0)
    assert abs(_tp([0.7] * 32) - 0.7) < 1e-6  # tight unanimous sub-1 mode
    assert _tp(rng.beta(5, 2, 32).tolist()) > 0.3  # probability target, not all-zero
    assert abs(_tp(rng.normal(0.5, 0.05, 64).tolist()) - 0.5) < 0.1  # narrow normal < 1


def test_red_zero_inflation_still_zero_by_density_with_cutoff_off():
    # Zero-inflation is handled by the tip_mass-floor density, not magnitude: a
    # zero-majority row reads 0 even with the magnitude cutoff off.
    assert _tp([0.0] * 20 + [5.0] * 12) == 0.0  # 62.5% exact zeros → 0
    assert _tp([0.0] * 13 + [5.0] * 19) == 5.0  # body majority → body mode


def test_red_optin_cutoff_zeroes_all_four_functions():
    # When a count consumer opts in, the magnitude rule re-applies to point, bands, and
    # suppresses bimodality — across all four functions.
    f = _row([0.7] * 32)
    with _cutoff(1.0):
        assert float(tower_point(f).values[0, 0]) == 0.0
        assert np.array_equal(hdi_tower(f, masses=(0.9,))[0, 0], [0.0, 0.0])
        assert float(summarize_tower(f).point.values[0, 0]) == 0.0
        assert float(bimodality(f)[0, 0]) == 0.0
    assert abs(float(tower_point(f).values[0, 0]) - 0.7) < 1e-6  # restored: off again


def test_red_zero_cutoff_is_runtime_live():
    # Editing the config takes effect without re-import (import-snapshot wart fixed).
    assert _tp([2.0] * 32) == 2.0  # default off
    with _cutoff(3.0):
        assert _tp([2.0] * 32) == 0.0  # live: 2.0 <= 3.0 → zeroed
    assert _tp([2.0] * 32) == 2.0  # restored


def test_red_tower_point_independent_of_frozen_map_estimate():
    # The unbinned tower tip and the binned frozen map_estimate are computed differently
    # and must be free to disagree (the C-32 motivation). map_estimate is untouched.
    rng = np.random.default_rng(11)
    pf = PredictionFrame(rng.gamma(2.0, 1.5, (20, 60)).astype(np.float32), _index(20))
    assert np.any(tower_point(pf).values[:, 0] != map_estimate(pf).values[:, 0])


@pytest.mark.parametrize("bad", [1.0, 1.5, 0.0, -0.2, (0.5, 2.0)])
def test_red_out_of_range_mass_fails_loud(bad):
    pf = _pf([[1.0, 2.0, 3.0, 4.0]])
    masses = bad if isinstance(bad, tuple) else (bad,)
    with pytest.raises(ValueError, match="open interval"):
        hdi_tower(pf, masses=masses)


def test_red_empty_masses_fails_loud():
    with pytest.raises(ValueError, match="open interval"):
        hdi_tower(_pf([[1.0, 2.0, 3.0, 4.0]]), masses=())


def test_red_nan_row_stays_local_and_does_not_crash():
    # Frames do not ban NaN (out-of-contract input). A NaN in one row must not corrupt
    # or crash the others — failure stays localized.
    good = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=np.float32)
    bad = good.copy()
    bad[0] = np.nan
    pf = PredictionFrame(np.stack([good, bad]), _index(2))
    tower = hdi_tower(pf, masses=(0.5,))
    tip = tower_point(pf).values[:, 0]
    clean_ref = _ref_hdi(good, (0.5,))[0]
    assert np.array_equal(tower[0, 0], np.asarray(clean_ref, dtype=np.float32))
    assert np.isfinite(tip[0])


def test_red_inf_row_stays_local_and_does_not_crash():
    good = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=np.float32)
    bad = good.copy()
    bad[-1] = np.inf
    pf = PredictionFrame(np.stack([good, bad]), _index(2))
    tower = hdi_tower(pf, masses=(0.5,))
    clean_ref = _ref_hdi(good, (0.5,))[0]
    assert np.array_equal(tower[0, 0], np.asarray(clean_ref, dtype=np.float32))
    assert np.isfinite(tower_point(pf).values[0, 0])


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
    # Threshold = input size, a "does not scale with n" proxy. A blocking regression
    # allocates the whole grid (hundreds of MB+), far above the threshold. tracemalloc
    # environment-sensitive: monitored as register C-38, not a fix.
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


# ============ I2 — distribution-agnostic (register C-45, off-by-default) ==========


@pytest.mark.parametrize(
    "name,draws_fn",
    [
        ("beta[0,1]", lambda r: r.beta(5, 2, 256)),
        ("uniform[0,1]", lambda r: r.uniform(0, 1, 256)),
        ("narrow-normal<1", lambda r: r.normal(0.5, 0.1, 256)),
        ("normal", lambda r: r.normal(50.0, 5.0, 256)),
        ("lognormal", lambda r: r.lognormal(0.0, 1.0, 256)),
        ("low-intensity-count", lambda r: r.gamma(2.0, 0.1, 256)),
    ],
)
def test_green_default_summary_is_distribution_agnostic(name, draws_fn):
    # By default (no magnitude cutoff) the tip sits in-range and bands are not all 0,
    # for every distribution shape — counts, continuous, normal, and [0,1] (C-45).
    draws = np.asarray(draws_fn(np.random.default_rng(0)), dtype=np.float32)
    pf = _row(draws)
    tip = float(tower_point(pf).values[0, 0])
    assert float(draws.min()) - 1e-3 <= tip <= float(draws.max()) + 1e-3
    assert not np.allclose(hdi_tower(pf, masses=(0.5, 0.9))[0], 0.0)


def test_green_probability_target_not_globally_zeroed():
    # A [0,1] (beta) field must not collapse to all-zeros — the C-45 headline failure.
    rng = np.random.default_rng(1)
    pf = PredictionFrame(rng.beta(5, 2, (50, 256)).astype(np.float32), _index(50))
    assert (tower_point(pf).values[:, 0] > 0).all()


@pytest.mark.parametrize("k", [0.1, 10.0, 1000.0])
def test_green_default_is_scale_consistent(k):
    # No magnitude rule by default → scaling all draws never flips a cell 0<->nonzero.
    base = [0.2, 0.3, 0.4, 0.5, 0.6] * 6 + [0.4, 0.4]
    assert _tp(base) > 0 and _tp([x * k for x in base]) > 0


def test_green_vectorized_matches_scalar_with_cutoff_on_and_off():
    # The vectorized engine equals the per-row reference whether the cutoff is off
    # (None) or on (1.0) — the reference mirrors `_zero_mask` live.
    rng = np.random.default_rng(7)
    values = rng.lognormal(0.3, 0.8, (20, 64)).astype(np.float32)
    values[rng.random(values.shape) < 0.2] = 0.0
    pf = PredictionFrame(values, _index(20))
    masses = tuple(float(m) for m in _FLOORS)
    for cut in (None, 1.0):
        with _cutoff(cut):
            tower = hdi_tower(pf, masses=masses).reshape(-1, len(masses), 2)
            tip = tower_point(pf).values[:, 0]
            for r, row in enumerate(values):
                assert np.array_equal(
                    tower[r], np.asarray(_ref_hdi(row, masses), dtype=np.float32)
                )
                np.testing.assert_allclose(tip[r], _ref_tip(row), rtol=1e-5, atol=1e-6)


def test_green_frame_parity_default_no_zeroing():
    # FeatureFrame and TargetFrame [0,1] data are not zeroed by default either.
    rng = np.random.default_rng(3)
    ff = _ff(rng.beta(5, 2, (4, 3, 128)).astype(np.float32))
    assert (tower_point(ff).values[..., 0] > 0).all()
    tf = TargetFrame(np.array([[0.7], [0.3]], dtype=np.float32), _index(2))
    assert (tower_point(tf).values[:, 0] > 0).all()


def test_green_optin_cutoff_reproduces_legacy_magnitude_behaviour():
    # Regression parity: with zero_cutoff=1.0 the 1.2.0 magnitude rule returns exactly.
    with _cutoff(1.0):
        assert _tp([0.7] * 32) == 0.0
        assert _tp(list(np.random.default_rng(0).beta(5, 2, 32))) == 0.0
        assert _tp([2.0] * 32) == 2.0  # max > cutoff → unaffected
