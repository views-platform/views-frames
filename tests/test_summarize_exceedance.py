"""Tests for `exceedance` / `exceedance_reducer` (ADR-021).

ADR-005 tiers:
🟩 Green — known fraction → exact P; in [0,1]; shape; reducer ≡ array.
🟫 Beige — (added in I2) S=1, below-min/above-max, FF/TF parity, integer-count.
🟥 Red  — (added in I2/I3) strict-> tie, NaN/empty raise, ±inf, aggregate composition.

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
    collapse,
    exceedance,
    exceedance_reducer,
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


def test_known_fraction_is_exact():
    # row draws [0,1,2,3]: P(>0)=3/4, P(>1)=2/4, P(>3)=0/4.
    pf = _pf([[0.0, 1.0, 2.0, 3.0]])
    out = exceedance(pf, [0.0, 1.0, 3.0])
    assert np.allclose(out[0], [0.75, 0.5, 0.0])


def test_shape_and_range():
    pf = _pf([[0.0, 1.0, 2.0, 3.0], [5.0, 5.0, 5.0, 5.0]])
    out = exceedance(pf, [1.0, 4.0])
    assert out.shape == (2, 2)  # (N, K)
    assert ((out >= 0.0) & (out <= 1.0)).all()


def test_reducer_matches_array_for_single_threshold():
    # collapse(frame, exceedance_reducer(c)) is the (N,…,1) frame form of P(Y>c).
    pf = _pf([[0.0, 1.0, 2.0, 3.0], [2.0, 2.0, 9.0, 9.0]])
    frame = collapse(pf, exceedance_reducer(1.0))
    assert type(frame) is PredictionFrame
    assert frame.values.shape == (2, 1)
    assert np.allclose(frame.values[:, 0], exceedance(pf, [1.0])[:, 0])


def test_non_increasing_in_threshold():
    # the survival function is monotone non-increasing in the threshold.
    pf = _pf([[0.0, 1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0, 9.0]])
    sweep = exceedance(pf, [-1.0, 0.5, 2.5, 4.5, 10.0])
    assert (np.diff(sweep, axis=-1) <= 1e-7).all()


def test_onset_is_distribution_agnostic_on_zero_inflated_cell():
    # P(Y>0) = "any activity" = the nonzero-draw fraction, independent of the
    # (multimodal) shape of the positive part — robust where the tower is weak (C-34).
    draws = [0.0] * 6 + [3.0, 3.0, 50.0, 1000.0]  # 6 zeros + 4 positive
    assert np.isclose(exceedance(_pf([draws]), [0.0])[0, 0], 0.4)


# 🟫 Beige ---------------------------------------------------------------------


def test_single_sample_frame():
    pf = _pf([[5.0]])  # S=1
    assert exceedance(pf, [4.0])[0, 0] == 1.0  # 5 > 4
    assert exceedance(pf, [5.0])[0, 0] == 0.0  # 5 > 5 is False (strict)


def test_threshold_below_min_and_above_max():
    pf = _pf([[2.0, 4.0, 6.0]])
    assert exceedance(pf, [1.0])[0, 0] == 1.0  # below all draws → 1
    assert exceedance(pf, [9.0])[0, 0] == 0.0  # above all draws → 0


def test_featureframe_parity():
    # (N, F, S): each feature row reduced independently → (N, F, K).
    ff = _ff([[[0.0, 1.0, 2.0, 3.0], [10.0, 10.0, 10.0, 10.0]]])  # (1, 2, 4)
    out = exceedance(ff, [1.0])
    assert out.shape == (1, 2, 1)
    assert np.allclose(out[0, :, 0], [0.5, 1.0])


def test_targetframe_parity():
    # TargetFrame is (N, 1) — a degenerate S=1 sample axis; exceedance is well-defined.
    tf = TargetFrame(np.array([[3.0], [0.0]], dtype=np.float32), _index(2))
    out = exceedance(tf, [1.0])
    assert out.shape == (2, 1)
    assert np.allclose(out[:, 0], [1.0, 0.0])  # 3 > 1, 0 > 1


def test_integer_count_inclusive_via_k_minus_one():
    # strict '>' only; a consumer wanting P(Y >= 25) on integer counts passes 24.
    pf = _pf([[10.0, 25.0, 25.0, 30.0]])  # two draws at exactly 25
    assert exceedance(pf, [25.0])[0, 0] == 0.25  # P(Y > 25): just {30}
    assert exceedance(pf, [24.0])[0, 0] == 0.75  # P(Y >= 25): {25, 25, 30}


# 🟥 Red -----------------------------------------------------------------------


def test_strict_greater_excludes_a_tie_at_a_draw():
    pf = _pf([[1.0, 2.0, 3.0, 4.0]])
    # threshold exactly == the draw 2.0 → only {3, 4} exceed → 0.5 (the 2.0 excluded).
    assert exceedance(pf, [2.0])[0, 0] == 0.5


def test_infinite_thresholds():
    pf = _pf([[1.0, 2.0, 3.0]])
    assert exceedance(pf, [-np.inf])[0, 0] == 1.0  # P(> -inf) = 1
    assert exceedance(pf, [np.inf])[0, 0] == 0.0  # P(> +inf) = 0


def test_aggregate_composition_is_joint_exceedance():
    # Country exceedance (register C-49): aggregate the SAMPLES first, then reduce per
    # row. Two pgm cells → one country, same time; samples summed per draw (joint
    # sampling), so P(country total > c) is on the summed posterior — NOT recoverable
    # from the per-cell exceedances.
    idx = SpatioTemporalIndex(
        np.array([1, 1], dtype=np.int64),
        np.array([10, 11], dtype=np.int32),
        SpatialLevel.PGM,
    )
    grid = PredictionFrame(
        np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], dtype=np.float32), idx
    )
    country = aggregate_distributions(
        grid, {(1, 10): 100, (1, 11): 100}, SpatialLevel.CM
    )
    # summed draws = [6, 8, 10, 12]; P(sum > 9) = {10, 12} / 4 = 0.5.
    assert country.values.shape == (1, 4)
    assert np.isclose(exceedance(country, [9.0])[0, 0], 0.5)
    # ...and the joint result is unrecoverable from per-cell exceedances: each cell's
    # P(Y > 9) is 0, so no combination of them yields 0.5.
    per_cell = exceedance(grid, [9.0])
    assert (per_cell == 0.0).all()
    assert not np.isclose(float(per_cell.sum()), 0.5)


# 🟥 Red (fail-loud guards land in I1; the wider matrix is I2) ------------------


def test_nan_draw_raises():
    pf = _pf([[0.0, np.nan, 2.0, 3.0]])
    with pytest.raises(ValueError, match="non-finite"):
        exceedance(pf, [1.0])


@pytest.mark.parametrize("bad", [np.inf, -np.inf])
def test_inf_draw_raises(bad):
    # falsify audit 2026-06-25 (P5b): an ±inf DRAW silently blesses P as a
    # valid-looking probability (inf > c is True), masking the upstream bug. The guard
    # is `np.isfinite`, not `np.isnan`, so ±inf fails loud like NaN. (inf THRESHOLDS
    # stay valid — see test_infinite_thresholds; the guard is on draws, not thresholds.)
    pf = _pf([[0.0, 1.0, bad, 3.0]])
    with pytest.raises(ValueError, match="non-finite"):
        exceedance(pf, [1.0])


def test_empty_thresholds_raises():
    pf = _pf([[0.0, 1.0, 2.0, 3.0]])
    with pytest.raises(ValueError, match="at least one threshold"):
        exceedance(pf, [])


def test_reducer_path_also_fails_loud_on_nonfinite():
    # the frame path (collapse + exceedance_reducer) shares the same fail-loud core.
    pf = _pf([[0.0, np.nan, 2.0, 3.0]])
    with pytest.raises(ValueError, match="non-finite"):
        collapse(pf, exceedance_reducer(1.0))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_in_a_non_first_block_raises(bad):
    # register C-65: the np.isfinite guard lives INSIDE the per-block reducer, which
    # block_apply calls once per row-block — but every other non-finite test uses a
    # 1-row frame (the single-shot path, n <= ROW_BLOCK), so the multi-block path was
    # never exercised. Force >1 block with a tiny block_rows and put the bad draw ONLY
    # in a LATER block (block 0 is all-finite) — so a guard that checked only the first
    # block would silently pass, and this fails loud as it must.
    rows = [
        [0.0, 1.0, 2.0, 3.0],  # block 0, row 0 — finite
        [1.0, 2.0, 3.0, 4.0],  # block 0, row 1 — finite
        [0.0, 1.0, 2.0, 3.0],  # block 1, row 2 — finite
        [0.0, bad, 2.0, 3.0],  # block 1, row 3 — the non-finite draw (later block)
    ]
    pf = _pf(rows)
    # sanity: block 0 alone is clean, so the regression target (guard sees only block 0)
    # would NOT raise — only the per-block guard on block 1 catches this.
    assert np.isfinite(np.array(rows[:2], dtype=np.float32)).all()
    with pytest.raises(ValueError, match="non-finite"):
        exceedance(pf, [1.0], block_rows=2)
