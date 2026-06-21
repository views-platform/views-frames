
# Class Intent Contract: FeatureFrame

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-21
**Related ADRs:** ADR-001, ADR-008, ADR-011, ADR-012, ADR-013

> Note: stub in Epic 1 (`src/views_frames/feature_frame.py` raises on construction).
> This contract defines the intended behaviour.

---

## 1. Purpose

`FeatureFrame` is the immutable container for model **inputs** (X): a feature/channel
array `y_features (N, F, S)` float32 aligned to a `SpatioTemporalIndex`, carrying
`feature_names` and a typed `metadata` header.

---

## 2. Non-Goals (Explicit Exclusions)

- It does **not** inherit from `PredictionFrame`/`TargetFrame` (separate siblings;
  ADR-011 Option C).
- It does **not** know about grids (`[T, H, W, C]`), PRIO-GRID cells, or harvested
  sources — `from_grid`/`grid_to_feature_frame` are **consumer adapters** in
  views-datafactory, not methods here.
- It does **not** import pandas or any `views_*`/store package.

---

## 3. Responsibilities and Guarantees

- Validates at construction: `values` contiguous `float32`, no object dtype;
  identifiers integer, length-`N`, complete; the sample axis is the **trailing** axis,
  always explicit (`S >= 1`; ADR-012) — a non-sampled feature frame is `(N, F, 1)`.
- Carries `feature_names: list[str]` (length `F`) and a typed `metadata` header
  (ADR-013); both serialize **with** the frame (register C-09).
- Immutable with copy-vs-view semantics identical to `PredictionFrame` (C-07).

---

## 4. Inputs and Assumptions

- `y_features`: `(N, F, S)` contiguous `float32`, `S >= 1`.
- `index`: a `SpatioTemporalIndex` of length `N`.
- `feature_names`: a list of length `F`.

Violations raise at construction (ADR-008).

---

## 5. Outputs and Side Effects

- New frames from operations; `save` writes `y_features.npy` + `identifiers.npz`
  + `feature_names`/`metadata` (via the frame-state round-trip contract).

---

## 6. Failure Modes and Loudness

- Raises on non-`float32`/object dtype, shape/length mismatch (incl.
  `len(feature_names) != F`), or incomplete identifiers. Structural, not temporal
  (register C-11).

---

## 7. Boundaries and Interactions

- Composes `SpatioTemporalIndex`; satisfies the `Frame`/`SpatioTemporalIndexed`/
  `Sampled`/`Persistable` protocols. Constructed by datafactory's
  `grid_to_feature_frame` adapter; consumers type against the protocols.

---

## 8. Examples of Correct Usage

```python
ff = FeatureFrame(
    y_features=x.astype("float32"),     # (N, F, S)
    index=idx,
    feature_names=["ged_sb", "pop", "v2x_libdem"],
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: a 2-D (N, F) array — the sample axis must be explicit (use (N, F, 1))
FeatureFrame(y_features=x2d, index=idx, feature_names=names)   # raises

# WRONG: calling a grid constructor on the frame — that adapter lives in datafactory
FeatureFrame.from_grid(cube)          # no such method here
```

---

## 10. Test Alignment

- **Green:** construction validation incl. `feature_names` length; save/load round-trip
  preserving `feature_names`/`metadata`.
- **Beige:** copy-vs-view property (`with_metadata` allocates no second buffer).
- **Red:** 2-D input / object dtype / mismatched `feature_names` raises; no-pandas
  import-enforcement.

---

## 11. Evolution Notes

- New optional `metadata` header fields are MINOR (ADR-013). The `feature_names`
  contract and the trailing sample axis are stable; changing them is MAJOR (ADR-016).

---

## End of Contract

This document defines the **intended meaning** of `FeatureFrame`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
