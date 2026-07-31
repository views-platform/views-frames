# Class Intent Contracts (CICs) — views-frames

This directory contains **Intent Contracts** as defined in
[ADR-006](../ADRs/006_intent_contracts_for_non_trivial_classes.md).

An Intent Contract is a human-readable, unambiguous declaration of:

- what a non-trivial class is meant to do,
- what it must never do,
- its invariants,
- and its failure semantics.

Intent Contracts are architectural artifacts.
They are not implementation documentation.

---

## When Is an Intent Contract Required?

An Intent Contract is mandatory for:

- Core domain classes
- Architectural boundary classes
- Orchestration components
- State-owning components
- Classes that enforce invariants
- Classes that modify semantics or transformation

Trivial value objects and pure utility functions do not require one.

---

## Structure of an Intent Contract

Each contract must define:

1. Purpose
2. Responsibility Boundary
3. Invariants
4. Explicit Non-Responsibilities
5. Failure Semantics
6. Observable Effects (if applicable)

Contracts must be clear enough that:

- Tests (ADR-005) can be derived from them.
- Architectural violations can be detected.
- Silicon-based agents cannot reinterpret intent (ADR-007).

---

## Status: fully contracted

Every non-trivial surface across the three shipped packages (`views_frames`,
`views_frames_summarize`, `views_frames_reconcile`) is governed by an active CIC below.
New contracts are authored **with** the class/package that introduces them. Two gaps were
found after the fact rather than authored alongside: `Reconcile.md` (closed 2026-06-28,
register C-64) and `Conformance.md` (closed 2026-07-31, register C-81) — the second found
only because this claim of completeness was audited against the code.

---

## Active Contracts

These CICs govern the shipped surface (`src/`, three packages, frozen since v1.0.0).

- `SpatioTemporalIndex.md` — the genuinely-reused alignment primitive; same-level logic owned,
  cross-level mapping injected (ADR-014).
- `Protocols.md` — the published surface `Frame`/`SpatioTemporalIndexed`/`Sampled`/`Persistable`
  (DIP/ISP; no shared base, ADR-011).
- `PredictionFrame.md` — model outputs `(N, S)`; numpy-only validation (not a verbatim move).
- `FeatureFrame.md` — model inputs `(N, F, S)` + `feature_names` + typed metadata header.
- `TargetFrame.md` — observed actuals `(N, 1)`; the array-native evaluation boundary.
- `Summarize.md` — the `views_frames_summarize` sibling package (collapse / MAP / HDI /
  quantiles / aggregation over frames; ADR-017).
- `Reconcile.md` — the `views_frames_reconcile` sibling package (`ReconciliationModule` /
  `reconcile_proportional` / `ReconciliationResult`; pgm→cm top-down proportional
  reconciliation, injected mapping, self-describing mode; ADR-023/ADR-024).
- `Conformance.md` — the published conformance suite consumers run in **their** CI
  (`assert_frame_contract` / `assert_frame_envelope` / the alignment, fill and cross-level
  laws + `CONFORMANCE_FLOOR`); the only surface here whose primary caller is another
  repository (ADR-016).

The `_validation` helper and the tiny `SpatialLevel` value object are governed primarily by
tests (and ADR-015 for `SpatialLevel`) rather than a CIC.

---

## Governance Relationship

Intent Contracts are governed by:

- ADR-006 (Intent Contracts for Non-Trivial Classes)
- ADR-003 (Authority of Declarations)
- ADR-005 (Testing Doctrine)

If a class changes meaning, its Intent Contract must be updated.
