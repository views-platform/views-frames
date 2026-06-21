"""I6: the vectorized summarizers must (a) match the per-row reference exactly and
(b) hold memory bounded at grid scale — the #181 report-stage regime (register C-22).

The reference functions below are the v0.2.0 ``np.apply_along_axis`` implementations;
the production code must be numerically identical to them while not looping in Python.
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
)
from views_frames_summarize import hdi, map_estimate


def _index(n):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=SpatialLevel.PGM,
    )


# --- reference (v0.2.0 per-row) implementations ------------------------------


def _ref_map(values: NDArray[np.float32], bins: int, zmt: float) -> NDArray[np.float32]:
    def m1d(s: NDArray[np.float32]) -> float:
        if float(np.mean(np.isclose(s, 0.0, atol=1e-8))) >= zmt:
            return 0.0
        # integer-counts argmax (lowest-index tie-break), matching production's
        # portable tie-break — not np.histogram(density=True)'s width-based one.
        counts, edges = np.histogram(s, bins=bins)
        centers = (edges[:-1] + edges[1:]) / 2.0
        return float(centers[int(np.argmax(counts))])

    return np.asarray(
        np.apply_along_axis(m1d, -1, values), dtype=np.float32
    )


def _ref_hdi(values: NDArray[np.float32], mass: float) -> NDArray[np.float32]:
    def h1d(s: NDArray[np.float32]) -> NDArray[np.float32]:
        srt = np.sort(s)
        n = int(srt.shape[0])
        k = int(np.floor(mass * n))
        if k < 1:
            return np.array([srt[0], srt[0]], dtype=np.float32)
        widths = srt[k:] - srt[: n - k]
        i = int(np.argmin(widths))
        return np.array([srt[i], srt[i + k]], dtype=np.float32)

    return np.asarray(np.apply_along_axis(h1d, -1, values), dtype=np.float32)


# --- exact-equivalence (vectorized == per-row reference) ---------------------


@pytest.mark.parametrize("seed", [0, 1, 2, 7, 13])
@pytest.mark.parametrize("shape", [(50, 64), (200, 31), (16, 8, 40)])
def test_map_estimate_matches_per_row_reference(seed, shape):
    rng = np.random.default_rng(seed)
    # mix in exact zeros so the zero-mass rule and degenerate-ish rows are exercised
    values = rng.normal(3.0, 2.0, shape).astype(np.float32)
    values[rng.random(shape) < 0.2] = 0.0
    pf = PredictionFrame(values, _index(shape[0])) if len(shape) == 2 else (
        FeatureFrame(values, _index(shape[0]), [f"f{i}" for i in range(shape[1])])
    )
    got = map_estimate(pf, bins=37)
    ref = _ref_map(values, bins=37, zmt=0.3)
    # map_estimate selects the same densest bin as the per-row np.histogram
    # reference, and the bin centre matches to float32 precision. Bit-exact
    # equality is NOT portable across the supported numpy range — on the numpy
    # 1.26 floor the vectorized and scalar `linspace` paths differ by ~1 ulp
    # (register C-24). Assert to float32 tolerance: a genuine bin divergence
    # would differ by ~a bin width and still fail here.
    np.testing.assert_allclose(got.values[..., 0], ref, rtol=1e-5, atol=1e-6)


def test_map_estimate_degenerate_rows_match_reference():
    # all-equal rows: numpy.histogram widens the range to (v-0.5, v+0.5).
    values = np.array([[5.0] * 10, [0.0] * 10, [-2.0] * 10], dtype=np.float32)
    pf = PredictionFrame(values, _index(3))
    got = map_estimate(pf, bins=100)
    ref = _ref_map(values, bins=100, zmt=0.3)
    np.testing.assert_allclose(got.values[..., 0], ref, rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize("seed", [0, 3, 9])
@pytest.mark.parametrize("mass", [0.5, 0.9, 0.95])
@pytest.mark.parametrize("shape", [(40, 50), (12, 6, 33)])
def test_hdi_matches_per_row_reference(seed, mass, shape):
    rng = np.random.default_rng(seed)
    values = rng.normal(0.0, 5.0, shape).astype(np.float32)
    pf = PredictionFrame(values, _index(shape[0])) if len(shape) == 2 else (
        FeatureFrame(values, _index(shape[0]), [f"f{i}" for i in range(shape[1])])
    )
    got = hdi(pf, mass=mass)
    ref = _ref_hdi(values, mass=mass)
    assert np.array_equal(got, ref)


# --- scale guard: memory must not scale with rows x bins ----------------------


def test_map_estimate_memory_is_bounded_at_grid_scale():
    # A whole-grid (rows x bins) counts matrix is the #181 OOM. The blocked
    # implementation caps peak memory regardless of row count; assert peak stays
    # well under what a whole-grid counts matrix alone would cost.
    n, s, bins = 1_000_000, 20, 200
    rng = np.random.default_rng(0)
    pf = PredictionFrame(rng.random((n, s), dtype=np.float32), _index(n))

    whole_grid_counts_bytes = n * bins * 8  # the allocation we refuse to make
    tracemalloc.start()
    tracemalloc.reset_peak()
    out = map_estimate(pf, bins=bins)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    assert out.values.shape == (n, 1)
    assert peak < whole_grid_counts_bytes / 2, (
        f"peak {peak / 1e6:.0f} MB ~ scales with rows*bins "
        f"({whole_grid_counts_bytes / 1e6:.0f} MB) — blocking regressed"
    )
