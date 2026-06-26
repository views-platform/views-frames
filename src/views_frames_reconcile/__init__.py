"""views_frames_reconcile — forecast reconciliation over frames (ADR-023).

A sibling package to ``views_frames`` (ADR-023, mirroring ADR-017): it makes grid
(``pgm``) predictions sum to their country (``cm``) totals, operating on frames.
Depends on ``views_frames`` + numpy only; never the reverse (enforced by
``tests/test_import_enforcement.py``).

The public surface — ``reconcile_proportional`` (the per-draw top-down proportional
method) and ``ReconciliationModule`` (the orchestrator holding the injected
``(time, unit) -> country`` mapping, never fetched here; ADR-014/ADR-023) — is
populated by the faithful port (story #134). This scaffold is intentionally empty.
"""
