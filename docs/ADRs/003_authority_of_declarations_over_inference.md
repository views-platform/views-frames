
# ADR-003: Authority of Declarations Over Inference

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

`views-frames` sits at a boundary where ambiguity is easy and dangerous. A frame is an
array plus identifiers; its `metadata` carries provenance; its `time` axis is a bare
integer. Each of these is a place where code could be tempted to *infer* intent — read a
domain meaning out of a free-form metadata dict, decode an epoch/month_id out of the
`time` integer, guess that a missing identifier is "probably fine," or accept a
half-valid array and patch it up later.

The design bible records the cost of inference-by-convention directly: the twins diverged
partly because behaviour lived in code-by-usage rather than in explicit declarations, and
the report-stage OOM (#181 / C-186) is what happens when an `object`-dtype representation
is allowed to carry implicit per-cell structure the array contract would have forbidden.
A clear rule is required to define **where semantic authority lives** and how ambiguity
is resolved.

---

## Decision

In this repository:

> **All meaningful semantics must be explicitly declared.  
> Inference of semantics across component boundaries is forbidden.**

Concretely, for this leaf:
- **Metadata is a typed header, not a free-form dict.** The leaf carries declared,
  optional-extensible provenance fields; it must not infer that some key means a level of
  analysis or a run identity. The consumer owns provenance *resolution* (ADR-001 Category 5).
  A free-form `Dict[str, Any]` is rejected precisely because it cannot be validated and
  re-opens the C-48 run-identity ambiguity.
- **`time` is an opaque integer.** The leaf validates *structure* (integer, length-N, no
  NaN) but never *temporal semantics*: month_id epoch, range, and monotonicity are a
  producer-adapter concern. The leaf is epoch-agnostic and must not infer or decode them.
- **The cross-level mapping is injected, never inferred.** The `priogrid→country`
  assignment is time-varying domain data supplied by the consumer to
  `cross_level_align(index, mapping)`; the leaf must not embed, fetch, or guess it.

When multiple representations of the same concept exist, **a single source of truth must
be designated** (the producer for `time` semantics; the consumer for metadata meaning and
the cross-level mapping; the leaf for structural identifier validity).

If required semantics are missing, ambiguous, or contradictory, the system **must not
guess** — it fails loud at construction (ADR-008).

---

## Global Invariant: Fail Loud on Semantic Ambiguity

In this repository, **silent failure is considered a bug**.

Whenever required semantics are:
- missing,
- ambiguous,
- contradictory,
- or inconsistent across representations,

the system **must fail loudly and immediately**.

This includes, but is not limited to:
- raising explicit runtime errors,
- failing validation or consistency checks,
- refusing to proceed without explicit declaration.

Warning-only behavior, implicit fallbacks, or “best-effort” inference are **forbidden**
for any decision-relevant semantics.

This rule applies regardless of environment:
development, experimentation, evaluation, or production.

---

## Rules of Semantic Authority

The following rules apply throughout the repository:

- Semantics must be **declared**, not inferred.
- Transformations are owned by the component that performs them.
- Metadata is a typed declaration; meaning is owned by the consumer, not read out by the leaf.
- `time` semantics are owned by the producer; the leaf validates structure only.
- No component may guess another component's intent.

Inference is permitted **only within a component's internal logic**, never across
component boundaries.

---

## Examples of Forbidden Behavior

- Reading a domain meaning out of the metadata header (e.g. assuming a key names a target/level of analysis).
- Decoding `time` as a month_id epoch or asserting monotonicity inside the leaf.
- Embedding or fetching the `priogrid→country` mapping instead of accepting it as an injected argument.
- Accepting an array with a NaN in the identifiers, or `object` dtype, and "fixing it up" instead of raising.
- Returning a half-valid frame and deferring validation, or proceeding after emitting a warning when an identifier is missing.

If behavior matters, it must be declared.

---

## Consequences

### Positive
- Eliminates silent semantic drift
- Improves reproducibility and debuggability
- Makes disagreements explicit and resolvable
- Enables principled failure under uncertainty

### Negative
- Requires more explicit configuration and metadata
- Some convenience patterns are disallowed
- Errors may surface earlier and more frequently

These costs are accepted intentionally.

---

## Notes

This ADR does not define:
- what concepts exist (ADR-001),
- or how components depend on each other (ADR-002).

It defines **who is allowed to say what something means**,  
and mandates **loud failure over silent misinterpretation**.
Its runtime enforcement (fail loud at construction) is detailed in ADR-008.

