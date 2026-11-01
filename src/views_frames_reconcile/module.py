"""Frames-native reconciliation orchestration (epic #31, story #36).

`ReconciliationModule` holds the injected `(time, priogrid_gid) -> country_id`
mapping (geography is injected, never embedded — views-frames ADR-014) and
applies it: `reconcile(cm_frame, pgm_frame)` validates the inputs, gives every draw
whose grid is empty but whose country is positive a donor draw's pattern (ADR-030),
and scales the grid forecasts to the country totals, returning a **new** pgm frame
(de-mutated, C-184).

**SRP:** orchestration only — the scaling math is the leaf (`proportional`), the
grouping is `grouping`, the empty-draw fill is `donor_fill`, the guards are
`validation`, the I/O is `frames`. No
torch, no pandas, no viewser, no wandb: the original's `ProcessPoolExecutor` and
WandB alerting are dropped (numpy is fast; there is no GPU). If scale ever needs
parallelism, add it behind this same interface (OCP). Multi-target inputs are
reconciled by calling `reconcile` once per target.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from views_frames import PredictionFrame
from views_frames_reconcile.donor_fill import fill_empty_grid_draws
from views_frames_reconcile.grouping import reconcile_pgm_to_cm
from views_frames_reconcile.result import (
    ALIGNED_DRAWS,
    METHOD_DONOR_FILL,
    POINT_BROADCAST,
    ReconciliationResult,
)
from views_frames_reconcile.validation import validate_reconciliation_inputs


def _broadcast_point_country(
    cm_frame: PredictionFrame, n_samples: int
) -> PredictionFrame:
    """Tile a point country forecast (``sample_count == 1``) across ``n_samples`` draws.

    Bit-identical to the WET broadcast pipeline-core's ``align_country_to_grid`` does
    (views-frames#143): the single column is repeated, so every draw is rescaled to the
    same total. It lives in the orchestrator so the leaf ``proportional`` and the
    parity-frozen ``grouping`` hot loop stay **untouched** — the equal-count path is
    byte-for-byte identical and only ``sample_count == 1`` takes this new path.
    """
    tiled = np.tile(np.asarray(cm_frame.values, dtype=np.float32), (1, n_samples))
    return PredictionFrame(tiled, cm_frame.index, cm_frame.metadata)


class ReconciliationModule:
    """Reconcile pgm forecasts to cm country totals (one target per call)."""

    def __init__(
        self,
        map_keys: NDArray[np.integer[Any]] | object,
        map_vals: NDArray[np.integer[Any]] | object,
        *,
        seed: int = 0,
    ) -> None:
        """Inject the `(time, priogrid_gid) -> country_id` mapping.

        Args:
            map_keys: ``(M, 2)`` int array of ``(time, priogrid_gid)`` pairs.
            map_vals: ``(M,)`` int ``country_id`` for each key.
            seed: non-negative int; seeds the donor choice for draws whose grid is empty
                (ADR-030). Group ``(time, country)`` draws from
                ``default_rng([seed, time, country])``, so the same inputs and seed give
                the same output however the calls are chunked.

        Raises:
            ValueError: ``map_keys`` is not ``(M, 2)``, ``map_vals`` is not length
                ``M``, or ``seed`` is not a non-negative int.
        """
        keys = np.asarray(map_keys)
        vals = np.asarray(map_vals)
        if keys.ndim != 2 or keys.shape[1] != 2:
            raise ValueError("map_keys must be an (M, 2) array of (time, priogrid_gid)")
        if vals.shape != (keys.shape[0],):
            raise ValueError("map_vals must be a length-M array aligned to map_keys")
        is_int = isinstance(seed, (int, np.integer)) and not isinstance(seed, bool)
        if not is_int or seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {seed!r}")
        self._map_keys = keys
        self._map_vals = vals
        self._seed = int(seed)

    def reconcile_result(
        self, cm_frame: PredictionFrame, pgm_frame: PredictionFrame
    ) -> ReconciliationResult:
        """Reconcile, also reporting the mode — a ``ReconciliationResult``.

        A **point** country (``cm.sample_count == 1``) is broadcast across the grid's
        draws before reconciling (mode ``point-broadcast``); an **aligned** country
        (``cm.sample_count == S``) scales draw-for-draw (mode ``aligned-draws``, the
        documented per-draw approximation). Any other count fails loud.

        The mode is **returned**, never stamped on the leaf's generic ``FrameMetadata``
        (ADR-020 / register C-47 — the leaf carries no reconciliation vocabulary; see
        ``result.py``).

        Raises:
            ValueError: the inputs fail validation (level / sample-count — cm must be 1
                or pgm's ``S`` / time coverage / missing country forecast), or a
                ``(time, country)`` has a positive country value in a draw whose grid is
                empty and no draw of that group has grid mass to borrow (ADR-030).
        """
        validate_reconciliation_inputs(
            cm_frame, pgm_frame, self._map_keys, self._map_vals
        )
        if cm_frame.sample_count != pgm_frame.sample_count:
            cm = _broadcast_point_country(cm_frame, pgm_frame.sample_count)
            mode = POINT_BROADCAST
        else:
            cm = cm_frame
            mode = ALIGNED_DRAWS
        filled, filled_draws = fill_empty_grid_draws(
            pgm_frame, cm, self._map_keys, self._map_vals, self._seed
        )
        frame = reconcile_pgm_to_cm(filled, cm, self._map_keys, self._map_vals)
        return ReconciliationResult(
            frame=frame, mode=mode, method=METHOD_DONOR_FILL, filled_draws=filled_draws
        )

    def reconcile(
        self, cm_frame: PredictionFrame, pgm_frame: PredictionFrame
    ) -> PredictionFrame:
        """Validate the inputs, then return a new pgm frame reconciled to cm totals.

        Point/aligned handling and fail-loud are as :meth:`reconcile_result`; this
        returns only the reconciled frame. Call :meth:`reconcile_result` when you also
        need the reconciliation *mode* (point-broadcast vs aligned-draws).

        Raises:
            ValueError: the inputs fail validation (level / sample-count — cm must be 1
                or pgm's ``S`` / time coverage / missing country forecast), or a
                ``(time, country)`` has a positive country value in a draw whose grid is
                empty and no draw of that group has grid mass to borrow (ADR-030).
        """
        return self.reconcile_result(cm_frame, pgm_frame).frame
