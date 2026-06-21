
# Class Intent Contract: Protocols (Frame / SpatioTemporalIndexed / Sampled / Persistable)

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-21
**Related ADRs:** ADR-001, ADR-006, ADR-009, ADR-012, ADR-013

> Note: defined in `src/views_frames/protocols.py`. The protocols are the published
> *abstract surface*; concrete frames are implementation detail (DIP/ISP).

---

## 1. Purpose

The protocols are the contract consumers type against. They segregate the frame
surface so no consumer depends on methods it does not use: a reconciler needs only
`SpatioTemporalIndexed`, an aggregator only `Sampled`, an I/O adapter only
`Persistable`, and the math layer the small `Frame` composition.

---

## 2. Non-Goals (Explicit Exclusions)

- The protocols do **not** prescribe a concrete base class — there is **no**
  `_BaseFrame`; frames satisfy the protocols by composition (ADR-011 Option C).
- They do **not** include cross-level alignment data, evaluation/metric methods, or
  store/transport concerns.
- `Persistable` describes **format** round-trip, not **where** bytes are stored.

---

## 3. Responsibilities and Guarantees

- `SpatioTemporalIndexed`: exposes `n_rows` and `identifiers` (integer arrays).
- `Sampled`: exposes `sample_count`, `is_sample` (`S > 1`), and `collapse(method)`
  which reduces the **trailing** sample axis and returns a new frame with `S == 1`
  (ADR-012). The sample axis is always explicit (`S >= 1`).
- `Persistable`: `save(directory)` and `load(directory, mmap)`; `mmap` propagates so
  peak RAM stays the working set (register C-07). Round-trips frame-declared state
  (a `__frame_state__`-style contract) so `io/` carries no per-frame schema (C-09).
- `Frame`: the minimal `values` + index + `n_rows` composition.

---

## 4. Inputs and Assumptions

- Implementers are immutable value objects whose `values` are contiguous `float32`
  with an explicit trailing sample axis and whose identifiers are complete integers.

---

## 5. Outputs and Side Effects

- Protocol methods return new frames (`collapse`) or perform I/O (`save`/`load`).
  `collapse` and structural ops are side-effect-free on their inputs.

---

## 6. Failure Modes and Loudness

- A type that claims to satisfy a protocol but violates it (e.g. `collapse` mutating
  in place, or `is_sample` ignoring the trailing axis) is a contract bug.
- `runtime_checkable` `isinstance` checks confirm structural conformance; they do not
  validate semantics — semantic conformance is enforced by the conformance suite.

---

## 7. Boundaries and Interactions

- Consumers depend on the **protocols**, inject the concrete (DIP). Adapters
  (loaders, savers) are consumer-side and implement against `Persistable`/`Frame`.
- The protocols import only `typing` + numpy typing; no domain, no store.

---

## 8. Examples of Correct Usage

```python
def reconcile(frame: SpatioTemporalIndexed) -> None:
    n = frame.n_rows                      # depends only on the index surface

def summarize(frame: Sampled) -> Sampled:
    return frame.collapse("arithmetic_mean")
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: typing against a concrete class instead of the protocol
def reconcile(frame: PredictionFrame) -> None: ...   # over-couples to one frame

# WRONG: a Persistable.load that needs out-of-band schema not in the bytes
```

---

## 10. Test Alignment

- **Green:** each concrete frame satisfies its declared protocols (`isinstance`
  structural check + semantic conformance suite).
- **Beige:** `collapse` reduces the trailing axis for every `Sampled` frame.
- **Red:** a frame missing a protocol member fails the conformance suite; an
  in-place `collapse` is rejected.

---

## 11. Evolution Notes

- New protocols are additive (MINOR). Adding a **required** method to an existing
  protocol is a MAJOR break for every implementer (ADR-016 governs the bump).

---

## End of Contract

This document defines the **intended meaning** of the `views_frames` protocols.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
