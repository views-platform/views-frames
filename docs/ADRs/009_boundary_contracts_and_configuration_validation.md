
# ADR-009: Boundary Contracts and Configuration Validation

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

`views-frames` is almost entirely *boundary*. Its reason to exist is the interface every
model, evaluator, reconciler, and report types against: the **published protocols**
(`Frame`, `SpatioTemporalIndexed`, `Sampled`, `Persistable`) and the frames that satisfy
them. Consumers hand the leaf arrays and identifiers and get back validated, immutable
value objects; they inject the cross-level mapping; they read and write frames through
`io/`. This makes the contract surface the single most important thing in the system, and
the place silent drift would do the most damage — it is exactly the divergence that let
the twins drift apart with no shared contract.

Ambiguous inputs, hidden defaults, and implicit contracts introduce silent semantic drift
and runtime fragility. To preserve fail-loud guarantees (ADR-003), all boundaries must be
explicit and validated **at construction**, before an invalid frame can exist.

---

## Decision

This repository adopts the following invariants:

> All architectural boundaries must declare explicit contracts.  
> All configuration must be validated at entry.  
> No semantic defaults may exist silently.

---

## 1. Boundary Contracts

The leaf's boundaries and their contracts:

- **Consumer → leaf (the published protocols):** `Frame`, `SpatioTemporalIndexed`,
  `Sampled`, `Persistable` are the explicit abstract surface consumers type against (DIP).
  Each is segregated so no consumer depends on methods it does not use (ISP). The protocols
  *are* the contract; the concrete frames are implementation detail.
- **Consumer → leaf (frame construction):** the input contract is `values` (float32,
  contiguous, no `object` dtype) + integer, length-N, no-NaN identifiers carrying the
  required `{time, unit}` and a `SpatialLevel`. The leaf makes the structural demand and
  *only* the structural demand — `time` is opaque (ADR-003).
- **Consumer → leaf (the injected mapping):** `cross_level_align(index, mapping)` takes the
  time-varying `priogrid→country` mapping as an **argument**. The leaf owns the operation
  signature; the consumer owns the mapping data. The leaf must not embed or fetch it.
- **Leaf ↔ disk (the `io/` round-trip):** `save`/`load` and `io/arrow` define a
  self-describing, exact round-trip — a frame written and read back is identical. `io/` is
  the only place a serialization dependency (`pyarrow`) lives.
- **Packaging boundary:** the leaf is built with **uv + hatchling** (the platform-modern
  toolchain, like views-datafactory/-bayesian/-appwrite), with `numpy` as the only core
  dependency and `pyarrow` behind an optional `[arrow]` extra — never setuptools.

Implicit contracts are prohibited. If a boundary assumption cannot be declared clearly,
the boundary must be redesigned.

---

## 2. The Contract as First-Class Artifact

The frame/index/protocol contract is an architectural artifact, not a convenience layer.
It must be:

- Explicit — every invariant a frame guarantees is a declared, validated rule.
- Versioned — changes follow the SemVer policy for an N-repo leaf (README §8; ADR-004 when activated).
- Externally inspectable — the protocols and the published conformance suite (ADR-005) make the contract testable by every consumer.
- Validated before use — at construction (§3).
- Free of hidden defaults — no inferred metadata meaning, no decoded `time` epoch, no embedded mapping.

Changing the contract must not silently alter what a frame *means*.

---

## 3. Validation at Construction (Handshake Principle)

A frame and its `SpatioTemporalIndex` are validated **at construction**, in `__init__`,
before the object is usable and before any operation runs. The system must fail early if:

- Required identifiers (`{time, unit}`) are missing
- dtypes are wrong (`object` dtype, non-integer identifiers, non-float32 values)
- Array length and identifier length disagree
- A declared invariant is violated (a NaN in an identifier, `sample_count < 1`)

Borrowed or assumed state is prohibited: the leaf must not reach back into a consumer to
derive a missing value, and must not accept the cross-level mapping from anywhere but its
explicit argument (ADR-002).

---

## 4. Separation of Contract Domains

The contract's domains must be separated conceptually:

- **Structural invariants** (dtype, shape, identifier completeness) — owned and enforced by the leaf.
- **Temporal/epoch semantics** of `time` — owned by the producer; the leaf is epoch-agnostic.
- **Provenance / metadata meaning** — owned by the consumer; the leaf carries the typed header but does not resolve it.

Cross-domain coupling must be explicit. A semantic concern (what `time` means) must not be
smuggled into a structural check.

---

## 5. Redundancy and Consistency Checks

Where ambiguity risk is high, explicit redundancy is preferred and must be validated for
consistency:

- The sample axis is **always** an explicit trailing axis (`S ≥ 1`) — one shape contract across the family, no `ndim` branching (README §13a.2), so shape and sample-count never disagree.
- Identifier arrays and the values array must agree on N; checked, not assumed.
- An `io/` round-trip is the redundancy check on serialization: the loaded frame must equal the saved one.

Silent derivation is discouraged where semantic meaning is involved.

---

## 6. Failure Semantics

Construction and boundary-validation failures must:

- Be logged where a logger is in scope (ADR-008)
- Be raised explicitly as `ValueError`/`TypeError` (ADR-008)
- Halt — never return a half-valid frame

Warnings are insufficient for structural contract errors.

---

## Consequences

### Positive

- Eliminates hidden configuration drift
- Reduces boundary fragility
- Strengthens fail-loud guarantees
- Improves reproducibility and traceability

### Negative

- Requires explicit schemas
- Adds validation boilerplate
- Increases up-front configuration clarity requirements

These costs are accepted.

---

## Notes

This ADR does not prescribe:

- Specific file layouts
- Specific configuration libraries
- Specific schema frameworks

Operational configuration structures may vary by project,
provided they comply with the invariants defined here.
