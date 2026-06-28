"""Negative tests for the summarize conformance suite (register C-51 analogue).

`assert_summarizer_contract` is exercised positively elsewhere (`test_proxy_adapter.py`,
`test_summarize_aggregate.py`) — but only against the REAL, conforming summarizers, so
no test exercises an assertion's raise-path (100% branch coverage does not). These
substitute a deliberately non-conforming summarizer and prove the conformance suite
fails loud — i.e. it has teeth and would reject a bad consumer implementation.

numpy + views-frames only.
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_summarize import conformance as _conformance
from views_frames_summarize.conformance import assert_summarizer_contract


def _pf(rows):
    arr = np.array(rows, dtype=np.float32)
    index = SpatioTemporalIndex(
        time=np.arange(arr.shape[0], dtype=np.int64),
        unit=np.arange(100, 100 + arr.shape[0], dtype=np.int32),
        level=SpatialLevel.PGM,
    )
    return PredictionFrame(arr, index)


def test_conformance_accepts_a_conforming_frame():
    # baseline: the real summarizers pass (so the negative below isolates the bad impl).
    assert_summarizer_contract(_pf([[0.0, 1.0, 2.0, 3.0], [1.0, 1.0, 1.0, 9.0]]))


def test_conformance_rejects_a_non_collapsing_point_estimator(monkeypatch):
    # A point estimator that fails to reduce the sample axis to 1 (here: returns the
    # frame unchanged, trailing axis S=4) must trip the `map_estimate → (N,…,1)` law.
    pf = _pf([[0.0, 1.0, 2.0, 3.0], [1.0, 1.0, 1.0, 9.0]])
    monkeypatch.setattr(_conformance, "map_estimate", lambda frame: frame)
    with pytest.raises(AssertionError, match="map_estimate"):
        assert_summarizer_contract(pf)
