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

The string values match pipeline-core's ``reconcile_frames`` constants verbatim, so the
mode is consistent across the repos that produce and consume it.
"""

from __future__ import annotations

from dataclasses import dataclass

from views_frames import PredictionFrame

#: A point country forecast (``sample_count == 1``) broadcast across the grid's draws.
POINT_BROADCAST = "point-broadcast"
#: A draws country forecast (``sample_count == S``) scaled draw-for-draw — the per-draw
#: approximation (the principled joint upgrade is a separate design, #145).
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
