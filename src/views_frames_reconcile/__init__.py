"""Forecast reconciliation (pgm forecasts reconciled to cm totals).

Slice 1 ports the top-down proportional method from views-reporting as a pure
numpy function. New methods (e.g. principled probabilistic reconciliation, C-37)
should be added as sibling modules, not by modifying ``proportional``.
"""

from views_frames_reconcile.module import ReconciliationModule
from views_frames_reconcile.proportional import reconcile_proportional
from views_frames_reconcile.result import (
    ALIGNED_DRAWS,
    METHOD_PROPORTIONAL,
    POINT_BROADCAST,
    ReconciliationResult,
)

__all__ = [
    "ALIGNED_DRAWS",
    "METHOD_PROPORTIONAL",
    "POINT_BROADCAST",
    "ReconciliationModule",
    "ReconciliationResult",
    "reconcile_proportional",
]
