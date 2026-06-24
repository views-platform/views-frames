"""Conformance checks for the summarize package (ADR-016/017).

A consumer can re-run these against its own frame factories to confirm the
summarizers behave: point estimates return same-type `(N, …, 1)` frames; interval
estimates return arrays aligned to the input frame's rows.
"""

from __future__ import annotations

import numpy as np

from views_frames_summarize import config
from views_frames_summarize._common import AnyFrame
from views_frames_summarize.bimodality import bimodality
from views_frames_summarize.collapse import collapse
from views_frames_summarize.interval import hdi, quantiles
from views_frames_summarize.point import map_estimate
from views_frames_summarize.summarize_tower import summarize_tower
from views_frames_summarize.tower import hdi_tower
from views_frames_summarize.tower_point import tower_point


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

    _assert_tower_contract(frame, n)


def _assert_tower_contract(frame: AnyFrame, n: int) -> None:
    """Assert the constrained-nested tower's contract + its laws (ADR-019)."""
    tip = tower_point(frame)
    assert type(tip) is type(frame), "tower_point must return the same frame type"
    assert tip.values.shape[-1] == 1 and tip.n_rows == n, "tower_point → (N,…,1)"

    flag = bimodality(frame)
    assert flag.shape[0] == n and flag.shape[-1] == 1, "bimodality → (N,…,1)"
    assert np.isin(flag, (0.0, 1.0)).all(), "bimodality must be a 0/1 flag"

    tower = hdi_tower(frame, masses=(0.5, 0.9, 0.99))
    assert tower.shape[0] == n, "hdi_tower must be aligned to the frame's rows"
    assert tower.shape[-2:] == (3, 2), "hdi_tower → (…, M, 2)"

    # Nesting law: every wider HDI contains the next-narrower one.
    lower, upper = tower[..., 0], tower[..., 1]
    assert (np.diff(lower, axis=-1) <= 1e-6).all(), (
        "tower lowers must be non-increasing"
    )
    assert (np.diff(upper, axis=-1) >= -1e-6).all(), (
        "tower uppers must be non-decreasing"
    )

    # Tip-in-tip_mass-floor law (ADR-019, outside-in redesign): the point is the median
    # of the configured ``tip_mass`` floor, so it lies inside that floor. (It is *not*
    # tied to the narrowest *requested* floor any longer — a caller may request a
    # narrower or wider band than ``tip_mass``.)
    tip_mass = float(config.get("tip_mass"))
    tip_floor = hdi_tower(frame, masses=(tip_mass,))
    tlo, thi = tip_floor[..., 0, 0], tip_floor[..., 0, 1]
    assert (tip.values[..., 0] >= tlo - 1e-6).all(), "tip below the tip_mass floor"
    assert (tip.values[..., 0] <= thi + 1e-6).all(), "tip above the tip_mass floor"

    # Reproducibility law: the 50% HDI is independent of the other requested masses.
    just_50 = hdi_tower(frame, masses=(0.5,))
    assert np.array_equal(just_50[..., 0, :], tower[..., 0, :]), (
        "the 50% HDI must be identical whether or not other masses are requested"
    )

    # The bundle is exactly the three composable functions.
    bundle = summarize_tower(frame, masses=(0.5, 0.9, 0.99))
    assert np.array_equal(bundle.point.values, tip.values), "bundle point ≠ tower_point"
    assert np.array_equal(bundle.intervals, tower), "bundle intervals ≠ hdi_tower"
    assert np.array_equal(bundle.bimodal, flag), "bundle bimodal ≠ bimodality"
