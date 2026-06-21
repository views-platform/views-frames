"""views_frames_summarize — posterior / sample-axis summarization over frames.

A sibling package to `views_frames` (ADR-017): it operates on frames and owns the
volatile statistics the leaf must not. Depends on `views_frames` + numpy only;
never the reverse (enforced by ``tests/test_import_enforcement.py``).

Conventions (ADR-017): point estimates (mean/median/MAP, generic ``collapse``)
return a `(N, …, 1)` **frame**; interval estimates (HDI, quantiles) return numpy
arrays **aligned to the input frame's index** (the caller holds the index).
"""

from __future__ import annotations

from views_frames_summarize.collapse import collapse
from views_frames_summarize.interval import hdi, quantiles
from views_frames_summarize.point import map_estimate

__all__ = ["collapse", "hdi", "map_estimate", "quantiles"]
