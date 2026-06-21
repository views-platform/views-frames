
# Class Intent Contract: PredictionFrame

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-21
**Related ADRs:** ADR-001, ADR-008, ADR-011, ADR-012, ADR-013

> Note: stub in Epic 1 (`src/views_frames/prediction_frame.py` raises on
> construction). This contract defines the intended behaviour, including the
> numpy-only validation rewrite (the source class in views-pipeline-core imports
> pandas — relocation is **not verbatim**; register C-17).

---

## 1. Purpose

`PredictionFrame` is the immutable container for model **outputs**: posterior /
ensemble samples `y_pred (N, S)` float32 aligned to a `SpatioTemporalIndex`.

---

## 2. Non-Goals (Explicit Exclusions)

- It does **not** inherit from or share a base class with `FeatureFrame`/`TargetFrame`
  (separate siblings; ADR-011 Option C).
- It does **not** import pandas (its identifier NaN-check is rewritten numpy-only;
  register C-17) or any `views_*`/store package.
- It does **not** perform scoring, reconciliation, report rendering, or store I/O.
- It does **not** carry the cross-level mapping.

---

## 3. Responsibilities and Guarantees

- Validates at construction: `values` contiguous `float32`, **no object dtype**;
  identifiers integer, length-`N`, complete; the sample axis is the **trailing** axis
  and always explicit (`S >= 1`; ADR-012).
- Immutable: `collapse`, `select`, `with_metadata` return **new** frames. Structural /
  metadata-only ops share the `values` buffer (zero-copy); `mmap` propagates; only a
  reduction allocates the reduced array (register C-07).
- `collapse(method)` reduces the trailing sample axis to `S == 1`.
- Carries a typed, optional-extensible `metadata` header (provenance; ADR-013).

---

## 4. Inputs and Assumptions

- `y_pred`: `(N, S)` contiguous `float32`, `S >= 1`.
- `index`: a `SpatioTemporalIndex` of length `N`.

Violations raise at construction (ADR-008) — never log-and-continue.

---

## 5. Outputs and Side Effects

- New frames from operations; `save` writes `y_pred.npy` + `identifiers.npz`
  (+ header). No other side effects.

---

## 6. Failure Modes and Loudness

- Raises `TypeError` on non-`float32`/object-dtype values; `ValueError` on shape,
  length, or completeness violations. The structural guarantee is **not temporal**
  (register C-11).

---

## 7. Boundaries and Interactions

- Composes `SpatioTemporalIndex`; satisfies `Frame`/`SpatioTemporalIndexed`/`Sampled`/
  `Persistable`. Producers (model engines) construct it; consumers type against the
  protocols. Numpy-only (import-enforcement test, ADR-002).

---

## 8. Examples of Correct Usage

```python
pf = PredictionFrame(y_pred=samples.astype("float32"), index=idx)   # (N, S)
point = pf.collapse("arithmetic_mean")                              # (N, 1)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: list-in-cell / object dtype (the measured non-scaler) — raises
PredictionFrame(y_pred=np.array(list_of_lists, dtype=object), index=idx)

# WRONG: mutating in place
pf.values[:] = 0          # frames are immutable; build a new frame instead
```

---

## 10. Test Alignment

- **Green:** construction validation; `collapse` shape/semantics; save/load round-trip.
- **Beige:** `mmap` load keeps peak RAM at the working set; `with_metadata` allocates
  no second `values` buffer (the copy-vs-view property, C-07).
- **Red:** object-dtype / wrong-dtype / NaN-identifier construction raises;
  no-pandas import-enforcement.

---

## 11. Evolution Notes

- Adding optional `metadata` fields is MINOR (ADR-013). Changing the sample-axis
  convention or a dtype is MAJOR (ADR-016 governs the cross-repo bump).

---

## End of Contract

This document defines the **intended meaning** of `PredictionFrame`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
