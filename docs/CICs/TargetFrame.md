
# Class Intent Contract: TargetFrame

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-24
**Related ADRs:** ADR-001, ADR-008, ADR-011, ADR-012, ADR-013

> Implemented in v0.1.0 (`src/views_frames/target_frame.py`). This contract governs
> that implementation.

---

## 1. Purpose

`TargetFrame` is the immutable container for observed **actuals** (ground truth):
`y_true (N, 1)` float32 aligned to a `SpatioTemporalIndex`. It makes the evaluation
boundary array-native, replacing the pandas actuals the eval adapter takes today.

---

## 2. Non-Goals (Explicit Exclusions)

- It does **not** inherit from `PredictionFrame` (separate sibling; ADR-011) even
  though it is structurally `PredictionFrame` with `S == 1`.
- It does **not** carry posterior samples (`S` is exactly 1), scoring logic, or metrics
  (scoring is views-evaluation's job; `MetricFrame` stays out of the leaf, ADR-016).
- It does **not** import pandas or any `views_*`/store package.

---

## 3. Responsibilities and Guarantees

- Validates at construction: `values` contiguous `float32` of shape `(N, 1)` — the
  trailing sample axis is explicit with `S == 1` (ADR-012); no object dtype;
  identifiers integer, length-`N`, complete.
- Immutable with the same copy-vs-view semantics as the other frames (register C-07).
- Carries a typed `metadata` header (ADR-013) and the same row/metadata surface as the
  sibling frames: `with_metadata`, `select(positions | mask)`, `reindex(other)` (raises
  unless this index is a superset of `other`); `sample_count == 1`, `is_sample == False`.
- The role (ground truth, single realized value) is explicit so line-graph / eval code
  can treat it distinctly from sampled frames.

---

## 4. Inputs and Assumptions

- `y_true`: `(N, 1)` contiguous `float32`.
- `index`: a `SpatioTemporalIndex` of length `N`.

Violations raise at construction (ADR-008).

---

## 5. Outputs and Side Effects

- New frames from operations; `save` writes `y_true.npy` + `identifiers.npz`. No other
  side effects.

---

## 6. Failure Modes and Loudness

- Raises on `S != 1`, non-`float32`/object dtype, or incomplete identifiers.
  Structural, not temporal (register C-11).

---

## 7. Boundaries and Interactions

- Composes `SpatioTemporalIndex`; satisfies `Frame`/`SpatioTemporalIndexed`/`Sampled`
  (with `is_sample == False`)/`Persistable`. Consumed by the evaluation adapter and the
  reporting line-graphs through the same surface as `PredictionFrame`.

---

## 8. Examples of Correct Usage

```python
tf = TargetFrame(y_true=actuals.reshape(-1, 1).astype("float32"), index=idx)
assert tf.is_sample is False        # S == 1
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: passing a 1-D (N,) array — the trailing axis must be explicit (N, 1)
TargetFrame(y_true=actuals_1d, index=idx)        # raises

# WRONG: treating it as a sampled frame and asking for many quantiles
```

---

## 10. Test Alignment

- **Green:** construction validation (`(N, 1)`, dtype, identifiers); save/load round-trip.
- **Beige:** serves through the same protocol surface as `PredictionFrame`
  (`is_sample == False`).
- **Red:** `(N,)` or `(N, S>1)` input raises; no-pandas import-enforcement.

---

## 11. Evolution Notes

- Naming (`TargetFrame` vs `ActualsFrame`) is an open question (README §13b.2); the
  role contract (`S == 1`, ground truth) is what must stay stable.

---

## End of Contract

This document defines the **intended meaning** of `TargetFrame`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
