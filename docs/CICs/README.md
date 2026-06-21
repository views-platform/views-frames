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

## Status: infrastructure only (no contracts yet)

`views-frames` currently contains no code — it is a design bible (see `README.md`). This
directory holds the template (`cic_template.md`) and this README. **Contracts are authored
as each class is implemented**, when the twins are relocated and the leaf is stood up.

---

## Active Contracts

These CICs govern the classes implemented in v0.1.0 (`src/views_frames/`).

- `SpatioTemporalIndex.md` — the genuinely-reused alignment primitive; same-level logic owned,
  cross-level mapping injected (ADR-014).
- `Protocols.md` — the published surface `Frame`/`SpatioTemporalIndexed`/`Sampled`/`Persistable`
  (DIP/ISP; no shared base, ADR-011).
- `PredictionFrame.md` — model outputs `(N, S)`; numpy-only validation (not a verbatim move).
- `FeatureFrame.md` — model inputs `(N, F, S)` + `feature_names` + typed metadata header.
- `TargetFrame.md` — observed actuals `(N, 1)`; the array-native evaluation boundary.

The `_validation` helper and the tiny `SpatialLevel` value object are governed primarily by
tests (and ADR-015 for `SpatialLevel`) rather than a CIC.

---

## Governance Relationship

Intent Contracts are governed by:

- ADR-006 (Intent Contracts for Non-Trivial Classes)
- ADR-003 (Authority of Declarations)
- ADR-005 (Testing Doctrine)

If a class changes meaning, its Intent Contract must be updated.
