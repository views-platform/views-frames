"""The reconciliation result — the reconciled frame plus *how* it was produced (#144).

The reconciliation **mode** (`point-broadcast` vs `aligned-draws`) and **method** are
reported here, on a reconcile-package result object — deliberately **not** stamped onto
the leaf's generic ``FrameMetadata``. That header is governed *generic-only* (ADR-020 /
register C-47): the numpy leaf carries provenance meaningful for *any* frame (`run_id`,
`data_version`) and must never carry domain/operation vocabulary it cannot know — as
evaluation provenance lives in views-evaluation's ``MetricFrame``, not the leaf.
Reconciliation is a sibling operation, so its provenance is reported by the sibling.

A caller that needs the mode reads it off :class:`ReconciliationResult`
(``ReconciliationModule.reconcile_result``); a caller that only needs the frame uses
``ReconciliationModule.reconcile``, which returns the frame directly.

The mode reflects **what this reconcile call did** (broadcast a point, or scaled aligned
draws) — not upstream provenance: a caller that pre-tiles a point country to ``S`` draws
before calling reconciles in ``aligned-draws`` mode. The string values match
pipeline-core's ``reconcile_frames`` constants verbatim, so the *vocabulary* is shared
across the repos that produce and consume the mode.
"""

from __future__ import annotations

from dataclasses import dataclass

from views_frames import PredictionFrame

#: Mode — the call **broadcast a point**: the country arrived as a point
#: (``cm.sample_count == 1``) against a multi-draw grid and was tiled across the grid's
#: ``S`` draws (every draw rescaled to the same total).
POINT_BROADCAST = "point-broadcast"
#: Mode — the call **scaled aligned draws**: the country already carried the grid's draw
#: count (``cm.sample_count == S``) and was scaled draw-for-draw — the per-draw
#: approximation (the principled joint upgrade is a separate design, #145). The mode
#: describes *what this call did*: a point against a single-draw grid, or a point the
#: caller pre-tiled to ``S``, also reads as aligned-draws (nothing was broadcast).
ALIGNED_DRAWS = "aligned-draws"
#: The reconciliation algorithm — top-down proportional, per draw.
METHOD_PROPORTIONAL = "proportional"


@dataclass(frozen=True)
class ReconciliationResult:
    """A reconciled grid frame plus how it was produced.

    Attributes:
        frame: the reconciled pgm ``PredictionFrame`` (identical to what ``reconcile``
            returns).
        mode: :data:`POINT_BROADCAST` or :data:`ALIGNED_DRAWS`.
        method: the reconciliation method, e.g. :data:`METHOD_PROPORTIONAL`.
    """

    frame: PredictionFrame
    mode: str
    method: str
