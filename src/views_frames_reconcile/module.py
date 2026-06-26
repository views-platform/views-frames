"""Frames-native reconciliation orchestration (epic #31, story #36).

`ReconciliationModule` holds the injected `(time, priogrid_gid) -> country_id`
mapping (geography is injected, never embedded — views-frames ADR-014) and
applies it: `reconcile(cm_frame, pgm_frame)` validates the inputs and scales the
grid forecasts to the country totals, returning a **new** pgm frame (de-mutated,
C-184).

**SRP:** orchestration only — the scaling math is the leaf (`proportional`), the
grouping is `grouping`, the guards are `validation`, the I/O is `frames`. No
torch, no pandas, no viewser, no wandb: the original's `ProcessPoolExecutor` and
WandB alerting are dropped (numpy is fast; there is no GPU). If scale ever needs
parallelism, add it behind this same interface (OCP). Multi-target inputs are
reconciled by calling `reconcile` once per target.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame
from views_frames_reconcile.grouping import reconcile_pgm_to_cm
from views_frames_reconcile.validation import validate_reconciliation_inputs


class ReconciliationModule:
    """Reconcile pgm forecasts to cm country totals (one target per call)."""

    def __init__(
        self,
        map_keys: NDArray[np.integer] | object,
        map_vals: NDArray[np.integer] | object,
    ) -> None:
        """Inject the `(time, priogrid_gid) -> country_id` mapping.

        Args:
            map_keys: ``(M, 2)`` int array of ``(time, priogrid_gid)`` pairs.
            map_vals: ``(M,)`` int ``country_id`` for each key.

        Raises:
            ValueError: ``map_keys`` is not ``(M, 2)`` or ``map_vals`` is not
                length ``M``.
        """
        keys = np.asarray(map_keys)
        vals = np.asarray(map_vals)
        if keys.ndim != 2 or keys.shape[1] != 2:
            raise ValueError("map_keys must be an (M, 2) array of (time, priogrid_gid)")
        if vals.shape != (keys.shape[0],):
            raise ValueError("map_vals must be a length-M array aligned to map_keys")
        self._map_keys = keys
        self._map_vals = vals

    def reconcile(
        self, cm_frame: PredictionFrame, pgm_frame: PredictionFrame
    ) -> PredictionFrame:
        """Validate the inputs, then return a new pgm frame reconciled to cm totals.

        Raises:
            ValueError: the inputs fail validation (level / sample-count / time
                coverage / missing country forecast).
        """
        validate_reconciliation_inputs(
            cm_frame, pgm_frame, self._map_keys, self._map_vals
        )
        return reconcile_pgm_to_cm(pgm_frame, cm_frame, self._map_keys, self._map_vals)
