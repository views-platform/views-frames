# Logging & Observability Standard — views-frames

**Status:** Active  
**Governing ADRs:** ADR-003 (Authority of Declarations Over Inference), ADR-005 (Testing), ADR-008 (Observability and Explicit Failure)  

---

## 1. Purpose

This document defines operational standards for logging behavior, log levels, error
propagation patterns, and observability expectations in `views-frames`. It operationalizes:

> Structural failures must be raised explicitly and logged persistently. (ADR-008)

It does not redefine architectural principles.

> **Scope is narrow by design.** `views-frames` is a **numpy-only value-object library**:
> it does no network I/O, no orchestration, no long-running work. There is almost nothing
> to *narrate* at runtime. The dominant — often the only — failure mode is a
> construction-time invariant violation, and **failing loud at construction is the primary
> observability mechanism**. The clear, specific exception message *is* the signal. Runtime
> logging is therefore minimal: prefer a precise `ValueError`/`TypeError` over a log line.
> A consumer that wraps the leaf in a pipeline owns the surrounding lifecycle logging.

---

## 2. Core Principles

### 2.1 Fail Loud and Persist

- Structural failures must:
  - be raised as exceptions (`ValueError`/`TypeError`) at construction
  - be logged at `ERROR` or higher **where a logger is in scope**
- Logging is not a substitute for raising.
- Raising is not a substitute for logging.

Silent degradation is prohibited: a frame is never returned half-valid, and an invalid
input is never "fixed up" (no NaN-coercion, no dtype-silent-cast).

---

### 2.2 Logs Must Support Understanding

Where the leaf does log (or where an exception message is constructed), it must:
- provide enough context to locate the failure — the offending field, the shape, the `SpatialLevel`, the operation (`construct`/`align`/`collapse`/`save`/`load`)
- avoid ambiguity

Logs and error messages must not:
- rely on implicit assumptions
- require tribal knowledge to interpret

---

### 2.3 Logs Must Not Leak Data

- The leaf handles no credentials or secrets.
- Frame **contents** must not be logged — log the shape, dtype, N, sample count, and `SpatialLevel`, never the `values` buffer or identifier arrays themselves (they can be large and are not diagnostic).

---

## 3. Log Levels (Normative Definitions)

We adopt the following level semantics:

### DEBUG
- Development diagnostics; detailed internal state (e.g. an intermediate shape during an alignment).
- Must not be required to understand a failure.

### INFO
- Sparse for a value-object library. At most: a frame `save`/`load` event with shape and target path, or an `io/arrow` round-trip. Most leaf operations log nothing.

### WARNING
- Unexpected but recoverable conditions that do **not** violate an invariant. Must not mask a structural error or an invariant violation. (A missing or NaN identifier is **not** a warning — it raises.)

### ERROR
- Structural failure within the leaf: a construction-time invariant violation, an alignment over mismatched levels, an `io/` deserialization failure. Must be raised (`ValueError`/`TypeError`) and logged where a logger is in scope.

### CRITICAL
- Irrecoverable failure (e.g. corrupt on-disk data that cannot be deserialized at all). Immediate attention required.

---

## 4. Error Propagation Pattern

Structural errors must follow this minimal pattern:

1. Construct a clear, descriptive error message.
2. Log the error (`ERROR` or `CRITICAL`).
3. Raise the appropriate exception with the same message.

Example:

```python
err_msg = (
    f"Frame identifiers contain NaN at indices {bad}; "
    f"identifiers must be complete integer arrays (no NaN)."
)
logger.error(err_msg)  # where a logger is in scope
raise ValueError(err_msg)
```

The leaf raises **specific** exception types (`ValueError` for invalid values/identifiers,
`TypeError` for wrong dtypes) so a consumer can catch precisely. Spacing conventions are
not mandated; clarity and consistency are.

---

## 5. Logging Scope Expectations

### 5.1 Required Logging

For a value-object leaf the required surface is small:

* All structural failures (logged at `ERROR`/`CRITICAL` where a logger is in scope, then raised)
* `io/` save/load and `io/arrow` round-trip events (shape, target, dtype — never the buffer)

### 5.2 Optional Logging

* Intermediate shapes during an alignment/collapse (DEBUG)
* Timing of a large `io/` operation
* Detailed internal diagnostics

---

## 6. Log Structure and Context

Log entries should include:

* Timestamp
* Level
* Module or component name
* Module/component name (e.g. `views_frames.index`, `views_frames.io.arrow`) and relevant diagnostics (shape, dtype, `SpatialLevel`, operation)

Structured logging (JSON or key-value format) is recommended where possible.

---

## 7. Alerting

Alerting is an operational layer built on logging.

At minimum:

* `ERROR` and `CRITICAL` logs must be alertable.
* `CRITICAL` logs must escalate.
* Alert routing must avoid noise amplification.

For a leaf this is almost entirely a **consumer concern**: the leaf raises, the consuming
pipeline routes alerts. Alert configuration (Slack, email, orchestration tools) is
operational and lives downstream.

---

## 8. Testing Requirements

Logging behavior must be testable where meaningful.

Tests should verify:

* Construction-time invariant violations raise the correct exception type (and log where applicable).
* A precise, locating message is produced (the offending field/shape is named).
* No frame `values` buffer is emitted to a log.

Logging tests must not rely on manual inspection. (Aligns with ADR-005.)

---

## 9. Anti-Patterns (Prohibited)

* Swallowing exceptions without logging
* Logging and continuing after an invariant violation (a construction invariant must *raise*, not warn)
* Downgrading errors to warnings to “keep things running”
* Using `print()` for structural diagnostics
* Logging an entire `values` buffer or identifier array (log shape/dtype/N, not the data)

---

## 10. Evolution

This document may evolve independently of ADRs.

If logging semantics change in a way that affects system meaning,
ADR-008 must be revisited.


