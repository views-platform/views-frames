"""Conformance checks for the summarize package (ADR-016/017).

A consumer can re-run these against its own frame factories to confirm the
summarizers behave: point estimates return same-type `(N, …, 1)` frames; interval
estimates return arrays aligned to the input frame's rows.
"""

from __future__ import annotations

import numpy as np

from views_frames_summarize._common import AnyFrame
from views_frames_summarize.collapse import collapse
from views_frames_summarize.interval import hdi, quantiles
from views_frames_summarize.point import map_estimate


def assert_summarizer_contract(frame: AnyFrame) -> None:
    """Assert the summarizers behave on ``frame``.

    Raises:
        AssertionError: a summarizer violates its output contract.
    """
    n = frame.n_rows

    point = collapse(frame, np.mean)
    assert type(point) is type(frame), "collapse must return the same frame type"
    assert point.values.shape[-1] == 1, "collapse must reduce the sample axis to 1"
    assert point.n_rows == n, "collapse must preserve rows"

    mode = map_estimate(frame)
    assert mode.values.shape[-1] == 1 and mode.n_rows == n, "map_estimate → (N,…,1)"

    lo_hi = hdi(frame, mass=0.9)
    assert lo_hi.shape[0] == n, "hdi must be aligned to the frame's rows"
    assert lo_hi.shape[-1] == 2, "hdi must produce (lower, upper)"

    qs = quantiles(frame, [0.1, 0.5, 0.9])
    assert qs.shape[0] == n, "quantiles must be aligned to the frame's rows"
    assert qs.shape[-1] == 3, "quantiles must produce one column per quantile"
