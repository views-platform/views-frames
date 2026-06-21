"""Tests for the summarizers (I5-I7): map_estimate, hdi, quantiles."""

from __future__ import annotations

import numpy as np

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_summarize import hdi, map_estimate, quantiles


def _index(n):
    return SpatioTemporalIndex(
        time=np.arange(n, dtype=np.int64),
        unit=np.arange(100, 100 + n, dtype=np.int32),
        level=SpatialLevel.PGM,
    )


def _pf(rows):
    arr = np.array(rows, dtype=np.float32)
    return PredictionFrame(arr, _index(arr.shape[0]))


# --- I5: map_estimate --------------------------------------------------------


def test_map_estimate_zero_mass_rule():
    # >= 30% of samples ~0 -> MAP forced to 0.0
    pf = _pf([[0.0, 0.0, 0.0, 5.0, 6.0]])
    out = map_estimate(pf)
    assert isinstance(out, PredictionFrame)
    assert out.values.shape == (1, 1)
    assert out.values[0, 0] == 0.0


def test_map_estimate_recovers_the_peak():
    rng = np.random.default_rng(0)
    samples = rng.normal(loc=10.0, scale=0.5, size=5000).astype(np.float32)
    pf = PredictionFrame(samples[np.newaxis, :], _index(1))
    out = map_estimate(pf, bins=50)
    assert abs(float(out.values[0, 0]) - 10.0) < 1.0


def test_map_estimate_preserves_identifiers():
    pf = _pf([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    out = map_estimate(pf)
    assert np.array_equal(out.identifiers["unit"], pf.identifiers["unit"])


# --- I6: hdi -----------------------------------------------------------------


def test_hdi_shortest_interval_golden():
    # samples [1,2,3,4,100], mass=0.6 -> k=3; widths=[4-1,100-2]=[3,98]; pick (1,4)
    pf = _pf([[1.0, 2.0, 3.0, 4.0, 100.0]])
    out = hdi(pf, mass=0.6)
    assert out.shape == (1, 2)
    assert np.allclose(out[0], [1.0, 4.0])


def test_hdi_lower_le_upper_and_index_aligned():
    pf = _pf([[1.0, 5.0, 9.0, 3.0], [10.0, 2.0, 7.0, 4.0]])
    out = hdi(pf, mass=0.9)
    assert out.shape == (2, 2)  # one (lower, upper) per row, aligned to the 2 rows
    assert np.all(out[:, 0] <= out[:, 1])


# --- I7: quantiles -----------------------------------------------------------


def test_quantiles_shape_and_values():
    pf = _pf([[1.0, 2.0, 3.0, 4.0, 5.0]])
    out = quantiles(pf, [0.0, 0.5, 1.0])
    assert out.shape == (1, 3)
    assert np.allclose(out[0], [1.0, 3.0, 5.0])


def test_quantiles_are_monotonic():
    rng = np.random.default_rng(1)
    pf = PredictionFrame(rng.random((4, 200), dtype=np.float32), _index(4))
    out = quantiles(pf, [0.1, 0.5, 0.9])
    assert np.all(np.diff(out, axis=-1) >= 0)
