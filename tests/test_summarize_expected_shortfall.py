"""Tests for `expected_shortfall` — the worst-case tail mean (ADR-022).

ADR-005 tiers:
🟩 Green — known tail mean → exact; min ≤ ES ≤ max; shape.
🟫 Beige — (added in I2) S=1, ⌈t·S⌉ rounding, FF/TF parity.
🟥 Red  — fail-loud NaN / empty / out-of-range; (aggregate composition in I3).

This file starts with the I1 driving cases; the full matrix lands in I2/I3.
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import (
    FeatureFrame,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
    TargetFrame,
)
from views_frames_summarize import (
    aggregate_distributions,
    expected_shortfall,
    quantiles,
)


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
    names = [f"f{i}" for i in range(arr.shape[1])]
    return FeatureFrame(arr, _index(arr.shape[0]), names)


# 🟩 Green ---------------------------------------------------------------------


def test_known_tail_mean_is_exact():
    # draws [0,1,2,3]: ES(.25)=worst1=3; ES(.5)=mean(worst2)=2.5; ES(1)=mean all=1.5.
    pf = _pf([[0.0, 1.0, 2.0, 3.0]])
    out = expected_shortfall(pf, [0.25, 0.5, 1.0])
    assert np.allclose(out[0], [3.0, 2.5, 1.5])


def test_shape_and_bounds():
    pf = _pf([[0.0, 1.0, 2.0, 3.0], [5.0, 5.0, 5.0, 5.0]])
    out = expected_shortfall(pf, [0.5, 1.0])
    assert out.shape == (2, 2)  # (N, K)
    lo = pf.values.min(axis=-1, keepdims=True)
    hi = pf.values.max(axis=-1, keepdims=True)
    assert ((out >= lo - 1e-6) & (out <= hi + 1e-6)).all()


def test_full_tail_is_the_mean():
    pf = _pf([[1.0, 2.0, 9.0, 12.0]])
    assert np.isclose(expected_shortfall(pf, [1.0])[0, 0], pf.values[0].mean())


def test_non_decreasing_as_tail_deepens():
    # a deeper tail (smaller t) is a worse worst-case: ES is non-decreasing as t → 0.
    pf = _pf([[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]])
    sweep = expected_shortfall(pf, [1.0, 0.5, 0.2, 0.1])  # widening tails
    assert (np.diff(sweep, axis=-1) >= -1e-6).all()


def test_es_dominates_its_var_quantile():
    # ES(t) ≥ the (1 − t) quantile (the tail mean dominates its VaR).
    rng = np.random.RandomState(1)
    pf = _pf(rng.gamma(1.0, 30.0, (3, 500)))
    for t in (0.5, 0.1, 0.02):
        es = expected_shortfall(pf, [t])[:, 0]
        var = quantiles(pf, [1.0 - t])[:, 0]
        assert (es >= var - 1e-3).all()


# 🟫 Beige ---------------------------------------------------------------------


def test_single_sample_frame():
    pf = _pf([[5.0]])  # S=1
    assert expected_shortfall(pf, [0.5])[0, 0] == 5.0  # ⌈0.5·1⌉ = 1 → that one draw
    assert expected_shortfall(pf, [1.0])[0, 0] == 5.0


def test_small_tail_reapproaches_max():
    # the documented caveat: ⌈t·S⌉ = 1 makes ES == max (volatile). t=0.01, S=100 → k=1.
    pf = _pf([np.arange(100, dtype=np.float32)])
    assert expected_shortfall(pf, [0.01])[0, 0] == 99.0  # == max
    assert expected_shortfall(pf, [0.05])[0, 0] == np.arange(95, 100).mean()  # worst 5


def test_featureframe_parity():
    ff = _ff([[[0.0, 1.0, 2.0, 3.0], [10.0, 20.0, 30.0, 40.0]]])  # (1, 2, 4)
    out = expected_shortfall(ff, [0.5])
    assert out.shape == (1, 2, 1)
    assert np.allclose(out[0, :, 0], [2.5, 35.0])  # mean(worst 2) per feature row


def test_targetframe_parity():
    # TargetFrame is (N, 1) — a degenerate S=1 sample axis; ES == that draw.
    tf = TargetFrame(np.array([[3.0], [7.0]], dtype=np.float32), _index(2))
    out = expected_shortfall(tf, [0.5])
    assert out.shape == (2, 1)
    assert np.allclose(out[:, 0], [3.0, 7.0])


# 🟥 Red (fail-loud guards land in I1; the wider matrix is I2/I3) ---------------


def test_nan_draw_raises():
    pf = _pf([[0.0, np.nan, 2.0, 3.0]])
    with pytest.raises(ValueError, match="non-finite"):
        expected_shortfall(pf, [0.5])


@pytest.mark.parametrize("bad", [np.inf, -np.inf])
def test_inf_draw_raises(bad):
    # falsify audit 2026-06-25 (P5b): an ±inf draw sorts last and contaminates the tail
    # mean to ±inf — a degenerate, bug-masking "worst case". The guard is `np.isfinite`,
    # not `np.isnan`, so ±inf fails loud just like NaN. (The leaf permits inf draws;
    # this worst-case summary rejects them as undefined.)
    pf = _pf([[0.0, 1.0, bad, 3.0]])
    with pytest.raises(ValueError, match="non-finite"):
        expected_shortfall(pf, [0.5])


def test_empty_tails_raises():
    pf = _pf([[0.0, 1.0, 2.0, 3.0]])
    with pytest.raises(ValueError, match="at least one tail"):
        expected_shortfall(pf, [])


def test_out_of_range_tail_raises():
    pf = _pf([[0.0, 1.0, 2.0, 3.0]])
    with pytest.raises(ValueError, match=r"in \(0, 1\]"):
        expected_shortfall(pf, [0.0])  # a tail <= 0 contains no samples
    with pytest.raises(ValueError, match=r"in \(0, 1\]"):
        expected_shortfall(pf, [1.5])  # > 1 is not a fraction


def test_aggregate_composition_is_joint_worst_case():
    # Country worst-case (register C-55): aggregate the SAMPLES first, then reduce per
    # row. Two pgm cells → one country, same time; samples summed per draw (joint
    # sampling). The cross-cell dependence MATTERS — here the two big draws fall in
    # DIFFERENT samples (anti-aligned), so the country worst-case is NOT the sum of the
    # per-cell worst-cases.
    idx = SpatioTemporalIndex(
        np.array([1, 1], dtype=np.int64),
        np.array([10, 11], dtype=np.int32),
        SpatialLevel.PGM,
    )
    grid = PredictionFrame(
        np.array([[1.0, 2.0, 3.0, 100.0], [100.0, 3.0, 2.0, 1.0]], dtype=np.float32),
        idx,
    )
    country = aggregate_distributions(
        grid, {(1, 10): 100, (1, 11): 100}, SpatialLevel.CM
    )
    # summed per draw = [101, 5, 5, 101]; ES(0.5) = mean(worst 2) = mean(101,101) = 101
    assert country.values.shape == (1, 4)
    assert np.isclose(expected_shortfall(country, [0.5])[0, 0], 101.0)
    # the per-cell ES are each mean(3, 100) = 51.5 → naive sum 103.0 ≠ the joint 101.0.
    per_cell = expected_shortfall(grid, [0.5])
    assert np.allclose(per_cell[:, 0], [51.5, 51.5])
    assert not np.isclose(float(per_cell[:, 0].sum()), 101.0)  # 103 ≠ 101 (subadditive)
