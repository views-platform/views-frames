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


# 🟥 Red team: the MAP-containment law on TIED draws (register C-88).
#
# The law certified floors using `floor(m·S)+1`, the *index span* `_ks` builds a floor
# from. But the tip is the median of the draws whose VALUE lies inside the floor
# (`_in_range_span`), and duplicated endpoint values make that count larger. So floors
# were certified that hold less than half the tip floor's actual draws, and the
# containment assertion they were certified to satisfy then failed.
#
# Integer count data ties constantly — these are conflict fatality draws, this
# platform's primary shape — and no test in the suite used integer draws, which is why
# this survived. `assert_summarizer_contract` is published under ADR-016 and every
# consumer runs it in their own CI, so the failure landed in *other people's* pipelines
# on correct data.


def _count_posterior(rng, s):
    """A zero-inflated Poisson row — the shape that broke the law."""
    draws = rng.poisson(rng.uniform(0.5, 6.0), size=(1, s)).astype(np.float32)
    if rng.random() < 0.5:
        draws *= rng.random((1, s)) > 0.3
    return _pf(draws)


def test_map_containment_holds_on_tied_integer_draws():
    """500 zero-inflated Poisson posteriors must all satisfy the published law.

    Measured before the fix: 30 failures (6.0%), every one reporting
    "MAP-containment violated: tip above the 0.15 floor" — the narrowest floor the
    old arithmetic certified at S=64.
    """
    rng = np.random.default_rng(0)
    failures = []
    for _ in range(500):
        frame = _count_posterior(rng, int(rng.choice([32, 64, 128])))
        try:
            assert_summarizer_contract(frame)
        except (
            AssertionError
        ) as exc:  # pragma: no cover - the point is that it does not
            failures.append(str(exc))
    assert not failures, (
        f"{len(failures)}/500 tied-draw posteriors violate the MAP-containment law; "
        f"first: {failures[0]}"
    )
