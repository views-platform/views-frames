
# Class Intent Contract: Protocols (Frame / SpatioTemporalIndexed / Sampled / Persistable)

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-24
**Related ADRs:** ADR-001, ADR-006, ADR-009, ADR-011, ADR-012, ADR-013, ADR-017

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

- `SpatioTemporalIndexed`: exposes `n_rows`, `identifiers` (integer arrays), and
  `index` (the `SpatioTemporalIndex` handle alignment is performed through).
- `Sampled`: exposes `sample_count`, `is_sample` (`S > 1`) — the **structural** facts
  about the trailing sample axis (always explicit, `S >= 1`; ADR-012). Reduction over
  the sample axis is **not** here — it lives in `views_frames_summarize` (ADR-017).
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

- Protocol accessors are pure reads; `Persistable` performs I/O (`save` / `load`).
  No protocol method mutates its frame — frames are immutable value objects. (Sample-axis
  reduction is a free function in `views_frames_summarize`, not a protocol method; ADR-017.)

---

## 6. Failure Modes and Loudness

- A type that claims to satisfy a protocol but violates it (e.g. `is_sample` ignoring
  the trailing axis, or a `save` / `load` that does not round-trip) is a contract bug.
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

def needs_samples(frame: Sampled) -> bool:
    return frame.is_sample                # sample_count > 1 — the structural fact
# Reduction over the sample axis is a free function in the sibling package, not a
# method here:  from views_frames_summarize import collapse; collapse(frame, np.mean)
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

- **Green:** each concrete frame satisfies its declared protocols — a direct
  `isinstance` structural check over all four protocols
  (`tests/test_properties.py::test_frames_satisfy_runtime_checkable_protocols`; it
  validates member *presence*, not signatures) plus the semantic conformance suite.
- **Beige:** `sample_count` / `is_sample` report the trailing axis for every `Sampled` frame.
- **Red:** a frame missing a protocol member is not an instance of that protocol and
  fails the conformance suite.

---

## 11. Evolution Notes

- New protocols are additive (MINOR). Adding a **required** method to an existing
  protocol is a MAJOR break for every implementer (ADR-016 governs the bump).

---

## End of Contract

This document defines the **intended meaning** of the `views_frames` protocols.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
