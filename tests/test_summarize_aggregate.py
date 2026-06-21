"""Tests for aggregate_distributions (I8) + the summarizer conformance helper (I9)."""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_summarize import aggregate_distributions, hdi
from views_frames_summarize.conformance import assert_summarizer_contract


def _pf(values, time, unit, level=SpatialLevel.PGM):
    idx = SpatioTemporalIndex(
        np.array(time, dtype=np.int64), np.array(unit, dtype=np.int32), level
    )
    return PredictionFrame(np.array(values, dtype=np.float32), idx)


def test_aggregate_sums_samples_element_wise():
    # two pgm cells -> one country, same time: samples summed per draw (joint sampling)
    pf = _pf([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], time=[0, 0], unit=[10, 11])
    out = aggregate_distributions(pf, {10: 100, 11: 100}, SpatialLevel.CM)
    assert out.n_rows == 1
    assert out.index.level is SpatialLevel.CM
    assert np.array_equal(out.values, [[5.0, 7.0, 9.0]])
    assert np.array_equal(out.index.unit, [100])
    assert np.array_equal(out.index.time, [0])


def test_aggregate_groups_within_time():
    pf = _pf(
        [[1.0, 1.0], [2.0, 2.0], [10.0, 10.0], [20.0, 20.0]],
        time=[0, 0, 1, 1],
        unit=[10, 11, 10, 11],
    )
    out = aggregate_distributions(pf, {10: 100, 11: 100}, SpatialLevel.CM)
    assert out.n_rows == 2  # (0,100) and (1,100)
    assert np.array_equal(out.index.time, [0, 1])
    assert np.array_equal(out.values, [[3.0, 3.0], [30.0, 30.0]])


def test_aggregate_hdi_differs_from_summed_cell_hdi():
    # the C-70 guard: HDI(sum of distributions) != sum(per-cell HDI bounds)
    rng = np.random.default_rng(2)
    a = rng.normal(5.0, 1.0, 800).astype(np.float32)
    b = rng.normal(50.0, 5.0, 800).astype(np.float32)
    pf = _pf(np.stack([a, b]), time=[0, 0], unit=[10, 11])
    agg = aggregate_distributions(pf, {10: 100, 11: 100}, SpatialLevel.CM)
    hdi_of_sum = hdi(agg, 0.9)[0]
    sum_of_cell_hdi = hdi(pf, 0.9).sum(axis=0)
    assert not np.allclose(hdi_of_sum, sum_of_cell_hdi)


def test_aggregate_requires_an_injected_mapping():
    pf = _pf([[1.0, 2.0]], time=[0], unit=[10])
    with pytest.raises(ValueError, match="requires an injected"):
        aggregate_distributions(pf, {}, SpatialLevel.CM)


def test_summarizer_conformance_on_builtin_frame():
    pf = _pf(
        [[1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]], time=[0, 1], unit=[10, 11]
    )
    assert_summarizer_contract(pf)
