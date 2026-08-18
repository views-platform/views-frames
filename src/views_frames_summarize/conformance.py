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
from views_frames_summarize.exceedance import exceedance
from views_frames_summarize.expected_shortfall import expected_shortfall
from views_frames_summarize.interval import hdi, quantiles
from views_frames_summarize.point import map_estimate
from views_frames_summarize.summarize_tower import summarize_tower
from views_frames_summarize.tower import _in_range_span, hdi_tower
from views_frames_summarize.tower_point import tower_point

__all__ = ["assert_summarizer_contract"]


def _require_assertions() -> None:
    """Fail loud if assertions are stripped (``python -O``/``-OO``).

    Mirrors ``views_frames.conformance._require_assertions`` (falsify audit 2026-07,
    F3): under optimized bytecode every ``assert`` silently passes — refuse to run.
    """
    if not __debug__:  # pragma: no cover — pytest always runs with assertions on
        raise RuntimeError(
            "the summarize conformance suite requires assertions; run without "
            "python -O/-OO (PYTHONOPTIMIZE), otherwise every check silently passes"
        )


def assert_summarizer_contract(frame: AnyFrame) -> None:
    """Assert the summarizers behave on ``frame``.

    Raises:
        AssertionError: a summarizer violates its output contract.
    """
    _require_assertions()
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

    # exceedance laws (ADR-021): a survival function — in [0, 1], non-increasing in the
    # threshold, with P(> -inf) = 1 and P(> +inf) = 0.
    thresholds = [-np.inf, 0.5, 1.5, np.inf]
    exc = exceedance(frame, thresholds)
    assert exc.shape[0] == n, "exceedance must be aligned to the frame's rows"
    assert exc.shape[-1] == len(thresholds), "exceedance → one column per threshold"
    assert ((exc >= 0.0) & (exc <= 1.0)).all(), (
        "exceedance must be a probability in [0, 1]"
    )
    assert (np.diff(exc, axis=-1) <= 1e-6).all(), (
        "exceedance must be non-increasing in the threshold"
    )
    assert (exc[..., 0] == 1.0).all(), "P(> -inf) must be 1"
    assert (exc[..., -1] == 0.0).all(), "P(> +inf) must be 0"

    # expected-shortfall laws (ADR-022): a tail mean — in [min, max], non-decreasing as
    # the tail deepens (t → 0), and dominating its VaR (ES(t) ≥ the (1 − t) quantile).
    tails = [1.0, 0.5, 0.1]  # widening tails (deepening worst-case)
    es = expected_shortfall(frame, tails)
    lo = frame.values.min(axis=-1)[..., np.newaxis]
    hi = frame.values.max(axis=-1)[..., np.newaxis]
    assert es.shape[0] == n, "expected_shortfall must be aligned to the frame's rows"
    assert es.shape[-1] == len(tails), "expected_shortfall → one column per tail"
    assert ((es >= lo - 1e-6) & (es <= hi + 1e-6)).all(), "ES must lie in [min, max]"
    assert (np.diff(es, axis=-1) >= -1e-6).all(), (
        "ES must be non-decreasing as the tail deepens"
    )
    var = quantiles(frame, [0.0, 0.5, 0.9])  # the (1 − t) quantiles for t = 1, 0.5, 0.1
    assert (es >= var - 1e-6).all(), "ES(t) must dominate the (1 − t) quantile"

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

    # MAP-containment law (ADR-019 amendment 2026-07-24; corrected 2026-08-18, C-88).
    # Wider-than-tip_mass floors contain the tip by nesting. Below tip_mass, a nested
    # floor still contains it whenever it holds MORE THAN HALF the tip floor's draws:
    # a contiguous sub-window longer than half the parent cannot trim away the parent's
    # middle draw(s), and the tip is their median/average.
    #
    # The count must be the draws whose VALUE lies in the floor — what `_in_range_span`
    # returns and what `tower_point` takes the median of. The law originally used
    # `floor(m·S)+1`, the *index span* `_ks` builds a floor from. Those agree only when
    # draws are distinct: duplicated endpoint values put more draws inside the same
    # bounds, so the tip floor held more than the formula said and narrower floors were
    # certified that hold less than half of it. On zero-inflated integer counts — this
    # platform's primary shape — that failed ~6% of rows, in consumers' own CI.
    #
    # Rows differ, so a floor may qualify in one row and not another; it is asserted
    # only where it qualifies. Floors qualifying nowhere carry NO guarantee and sit
    # below platform sample resolution (see tower_point.py and the tip_mass study).
    #
    # Only floors at or below tip_mass are candidates. A wider floor contains the tip by
    # nesting from the tip_mass floor, which the assertion above already covers.
    candidates = tuple(
        float(m) for m in config.canonical_floors() if float(m) <= tip_mass
    )
    law_tower = hdi_tower(frame, masses=candidates)

    # Nesting across the candidate grid, asserted UNCONDITIONALLY. Qualification is
    # derived from `law_tower` — the output under test — so without this a broken tower
    # could disarm the law with its own defect: degenerate narrow floors give a small
    # in-range count, fail `2·n_floor > n_tip`, and skip themselves. Nesting needs no
    # qualification (it is true by construction), so it keeps the teeth.
    lo_grid, hi_grid = law_tower[..., 0], law_tower[..., 1]
    assert (np.diff(lo_grid, axis=-1) <= 1e-6).all(), (
        "sub-tip_mass floors must nest: lowers non-increasing"
    )
    assert (np.diff(hi_grid, axis=-1) >= -1e-6).all(), (
        "sub-tip_mass floors must nest: uppers non-decreasing"
    )

    # Counted block-wise, in the same row blocks `hdi_tower` uses. The published suite
    # must stay inside the memory discipline of the code it certifies (C-22/C-25/C-71):
    # sorting the whole grid at once would allocate a full copy of a 1M×1000 frame.
    #
    # A `zero_cutoff` row (C-45) collapses to (0, 0) in both tower and tip, so its
    # in-range counts are 0, nothing qualifies, and the row is skipped — correctly:
    # containment of tip 0 in floor (0, 0) is trivially true there.
    s_count = int(frame.values.shape[-1])
    flat = np.ascontiguousarray(frame.values).reshape(-1, s_count)
    flat_lo = lo_grid.reshape(-1, len(candidates))
    flat_hi = hi_grid.reshape(-1, len(candidates))
    flat_tip = np.ravel(tip.values[..., 0])
    tip_lo, tip_hi = np.ravel(tlo), np.ravel(thi)
    block_rows = int(config.get("row_block"))

    for start in range(0, flat.shape[0], block_rows):
        stop = min(start + block_rows, flat.shape[0])
        srt = np.sort(flat[start:stop], axis=-1)
        _, n_tip = _in_range_span(srt, tip_lo[start:stop], tip_hi[start:stop])
        for j, m in enumerate(candidates):
            glo, ghi = flat_lo[start:stop, j], flat_hi[start:stop, j]
            _, n_floor = _in_range_span(srt, glo, ghi)
            qualifies = 2 * n_floor > n_tip
            if not qualifies.any():
                continue
            tips = flat_tip[start:stop]
            assert (tips[qualifies] >= glo[qualifies] - 1e-6).all(), (
                f"MAP-containment violated: tip below the {m:.2f} floor"
            )
            assert (tips[qualifies] <= ghi[qualifies] + 1e-6).all(), (
                f"MAP-containment violated: tip above the {m:.2f} floor"
            )

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
