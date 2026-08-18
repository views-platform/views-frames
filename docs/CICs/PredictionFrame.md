
# Class Intent Contract: PredictionFrame

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-08-18
**Related ADRs:** ADR-001, ADR-008, ADR-011, ADR-012, ADR-013, ADR-017, ADR-026

> Implemented in v0.1.0 (`src/views_frames/prediction_frame.py`), relocated from
> views-pipeline-core with numpy-only validation — the source imports pandas, so the
> relocation is **not verbatim** (register C-17).

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
- Immutable: `with_metadata` returns a **new** frame sharing the `values` buffer
  (zero-copy); `mmap` propagates (register C-07). **Immutability is enforced for the
  index** (`time`/`unit` are `setflags(write=False)`) and, **since 2.0.0, for the value
  buffer as well** — held as a read-only *view*, so zero-copy and `mmap` survive and the
  caller's own array is left writeable (ADR-028 / register C-66). It was immutable only
  by convention until then (ADR-025 / register C-63).
- Row ops return new frames: `select(positions | mask)` and `reindex(other)` — the
  latter raises unless this frame's index is a superset of `other`. Selection **copies**
  the selected `values` (only structural/metadata ops share the buffer).
- `reindex_fill(other, *, fill_value)` (ADR-026) is the dense-grid companion: aligns to
  `other` with **no** superset requirement — present rows pass through **bit-exact**,
  absent rows get the caller's `fill_value` (keyword-only, required; no silent default,
  ADR-009). Allocates the full dense buffer; assumes unique rows in *self* (C-21);
  law-pinned by `assert_reindex_fill_law` in the published conformance suite.
- Sample-axis reduction (collapse/MAP/HDI) is **not** a method here — it lives in
  `views_frames_summarize` (ADR-017). The frame exposes the structural `sample_count`/
  `is_sample` only.
- Carries a typed, optional-extensible `metadata` header (provenance; ADR-013).
- **Read-only accessors** (frozen v1 surface, ADR-018): `values`, `index`, `identifiers`,
  `metadata`, `n_rows`, `sample_count`, `is_sample`. `values`, `index` and `metadata`
  return the stored objects with no copy. **`identifiers` builds a fresh `{time, unit}` dict
  on every call** — the *arrays* inside it are shared and write-protected, but the wrapper is
  not free, so do not call it in a hot loop.

---

## 4. Inputs and Assumptions

- `y_pred`: `(N, S)` contiguous `float32`, `S >= 1`.
- `index`: a `SpatioTemporalIndex` of length `N`.

Violations raise at construction (ADR-008) — never log-and-continue.

---

## 5. Outputs and Side Effects

- New frames from operations; `save` writes `values.npy` + `identifiers.npz`
  (+ header). No other side effects.

---

## 6. Failure Modes and Loudness

- Raises `ValueError` on object-dtype values (list-in-cell is banned), on shape,
  length, or completeness violations, and on `reindex(other)` when `other` is not a
  subset of this frame's index. Other numeric dtypes (e.g. float64) are **coerced**
  to float32 by copy at construction — accepted, not rejected (the no-copy fast path
  is float32-only, register C-07). The structural guarantee is **not temporal**
  (register C-11).
- Raises `TypeError` when `index` is not a `SpatioTemporalIndex` (since 2.0.0, ADR-028). Before that, construction read one attribute off `index` — `n_rows` — so a frame, or any object exposing `n_rows`, was accepted silently and the published summarizer checker then certified the result.
- Raises `TypeError` from `reindex`/`reindex_fill` when handed something that is not a `SpatioTemporalIndex`; it previously leaked `AttributeError` naming a private attribute (ADR-008 requires `ValueError`/`TypeError` at every guard).
- Raises `ValueError` on in-place `.values` assignment — the buffer is write-protected.


---

## 7. Boundaries and Interactions

- Composes `SpatioTemporalIndex`; satisfies `Frame`/`SpatioTemporalIndexed`/`Sampled`/
  `Persistable`. Producers (model engines) construct it; consumers type against the
  protocols. Numpy-only (import-enforcement test, ADR-002).

---

## 8. Examples of Correct Usage

```python
pf = PredictionFrame(y_pred=samples.astype("float32"), index=idx)   # (N, S)
from views_frames_summarize import collapse
point = collapse(pf, np.mean)                                       # (N, 1) frame
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: list-in-cell / object dtype (the measured non-scaler) — raises
PredictionFrame(y_pred=np.array(list_of_lists, dtype=object), index=idx)

# WRONG: mutating the value buffer in place. Since 2.0.0 this RAISES — the buffer is
# write-protected (ADR-028 / register C-66). Until then it silently corrupted every
# frame sharing the buffer, e.g. via with_metadata. Build a new frame instead.
pf.values[:] = 0          # ValueError: assignment destination is read-only

# WRONG: passing something that is not an index. Raises since 2.0.0; before that it
# was accepted silently, because only `index.n_rows` was ever read (ADR-028).
PredictionFrame(y_pred=arr, index=some_other_frame)      # TypeError
```

---

## 10. Test Alignment

- **Green:** construction validation; `select`/`reindex` parity (`test_frame_parity.py`);
  save/load round-trip.
- **Beige:** `mmap` load returns an `np.memmap` and is read-only
  (`tests/test_io.py::test_npz_mmap_returns_memmap`) — a **type** check, not a memory
  measurement. Memmap implies lazy paging by definition, so the proxy is sound, but
  §10 previously read as though peak RAM were measured here; it is not (register
  C-80). `with_metadata` allocates no second `values` buffer — that one *is* measured
  (`tests/test_properties.py::test_with_metadata_shares_the_values_buffer`, C-07).
- **Red:** object-dtype / wrong-dtype / NaN-identifier construction raises;
  a non-`SpatioTemporalIndex` `index` raises, including a frame and a bare object with
  only `n_rows` — `tests/test_construction_red.py`; `reindex`/`reindex_fill` raise on a
  non-index argument — `tests/test_select.py`; the value buffer is read-only while the
  caller's array is not — `tests/test_properties.py`; no-pandas import-enforcement.

---

## 11. Evolution Notes

- Adding optional `metadata` fields is MINOR (ADR-013). Changing the sample-axis
  convention or a dtype is MAJOR (ADR-016 governs the cross-repo bump).

---

## End of Contract

This document defines the **intended meaning** of `PredictionFrame`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
