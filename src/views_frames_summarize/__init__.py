"""views_frames_summarize — posterior / sample-axis summarization over frames.

A sibling package to `views_frames` (ADR-017): it operates on frames and owns the
volatile statistics the leaf must not. Depends on `views_frames` + numpy only;
never the reverse (enforced by ``tests/test_import_enforcement.py``).

Conventions (ADR-017): point estimates (mean/median/MAP, generic ``collapse``)
return a `(N, …, 1)` **frame**; interval estimates (HDI, quantiles) return numpy
arrays **aligned to the input frame's index** (the caller holds the index).
"""

from __future__ import annotations

from views_frames_summarize.aggregate import (
    aggregate_distributions,
    aggregate_distributions_arrays,
)
from views_frames_summarize.bimodality import bimodality
from views_frames_summarize.collapse import collapse
from views_frames_summarize.exceedance import exceedance, exceedance_reducer
from views_frames_summarize.interval import hdi, quantiles
from views_frames_summarize.point import map_estimate
from views_frames_summarize.summarize_tower import TowerSummary, summarize_tower
from views_frames_summarize.tower import hdi_tower
from views_frames_summarize.tower_point import tower_point

__all__ = [
    "TowerSummary",
    "aggregate_distributions",
    "aggregate_distributions_arrays",
    "bimodality",
    "collapse",
    "exceedance",
    "exceedance_reducer",
    "hdi",
    "hdi_tower",
    "map_estimate",
    "quantiles",
    "summarize_tower",
    "tower_point",
]
