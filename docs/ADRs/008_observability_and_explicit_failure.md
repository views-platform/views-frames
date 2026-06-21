
# ADR-008: Observability and Explicit Failure

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

`views-frames` is a numpy-only value-object leaf: it does no network I/O, no orchestration,
no long-running work. Its failure surface is therefore narrow and sharp — almost all of it
is **construction-time invariant validation**. A frame is validated in `__init__` and then
treated as read-only; the dangerous failure is the one where an invalid frame (a NaN in an
identifier, a length mismatch, an `object` dtype, a missing required `{time, unit}`) is
allowed to exist and propagates a silently-wrong array to N consumers (README §3.4).

The platform's "Fail Loud and Proud" rule applies with full force here: invariants are
checked at construction and raise `ValueError`/`TypeError` **immediately** — never return
a half-valid object, never log-and-continue. Stack traces alone are insufficient when a
frame crosses a repo boundary, so a structural failure is both raised and recorded.

---

## Decision

The repository adopts the following invariant:

> Structural failures must be both **logged persistently** and **raised explicitly**.

### 1. Explicit Failure

- Construction-time invariant violations must raise exceptions — `ValueError` for invalid values/identifiers, `TypeError` for wrong dtypes/types.
- A frame must never be returned half-valid; validation happens in `__init__`, before the object is usable.
- Structural failures must not be downgraded to warnings, and must not be log-and-continued.
- No `object` dtype, no NaN in identifiers, no missing required `{time, unit}` may slip through under any "best-effort" path.

Fail-loud (ADR-003) applies fully to runtime behavior. The leaf raises on its own
behalf; a *consumer* that chooses to handle a malformed input gracefully does so on its
own side of the boundary — the leaf never makes that decision for it.

---

### 2. Persistent Observability

- Raised structural failures should be logged at `ERROR` level or higher where a logger is in scope.
- Critical, irrecoverable failures must be logged at `CRITICAL`.
- Logging must occur before or at the point of raising.
- Logging is not a substitute for raising; raising is not a substitute for logging.

> For a numpy-only value-object leaf, runtime logging is **minimal by design**: there is
> no I/O or orchestration to narrate, and **failing loud at construction is the primary
> observability mechanism**. The clear, specific exception message *is* the signal (see
> `standards/logging_and_observability_standard.md`).

---

### 3. Scope

This ADR applies to:

- frame construction-time validation failures (dtype, length, NaN, missing identifier),
- `SpatioTemporalIndex` alignment failures (mismatched level, non-overlapping index),
- `io/` round-trip / deserialization failures,
- a malformed injected mapping passed to `cross_level_align`,
- and other structural failures.

It does not prescribe formatting, spacing, or specific logging utilities.
Operational conventions may evolve separately.

---

## Consequences

### Positive

- Persistent traceability of structural failures
- Reduced debugging entropy
- Strong alignment with fail-loud invariant (ADR-003)
- Improved production observability

### Negative

- Slight increase in boilerplate
- Requires discipline in error handling

These costs are accepted.

---

## Notes

This ADR defines architectural requirements for failure handling.

It does not define log formatting standards, log retention policies,
or logging infrastructure configuration, which are operational concerns.

Observability must support understanding.
Failure must never be silent.
