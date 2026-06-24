
# Class Intent Contract: SpatioTemporalIndex

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-24
**Related ADRs:** ADR-001, ADR-002, ADR-009, ADR-013, ADR-014, ADR-015

> Implemented in v0.1.0 (`src/views_frames/index.py`). This contract governs that
> implementation.

---

## 1. Purpose

`SpatioTemporalIndex` is the genuinely-reused primitive of the package: the
`{time, unit, level}` integer row identity plus the **same-level**, pure-numpy
alignment logic (intersect / align / reindex / searchsorted) that gives arrays the
label-alignment that today drags pandas back into the hot path.

---

## 2. Non-Goals (Explicit Exclusions)

- It does **not** own or perform **cross-level** (cm↔pgm, country↔grid) joins as a
  data operation. It exposes the `cross_level_align(mapping, target_level)` *protocol*
  (and the columnar `cross_level_align_arrays(map_keys, map_vals, target_level)`, register
  C-26) only; the time-varying `(time, unit) → target_unit` mapping is **injected by the
  consumer** and is never embedded, fetched, or versioned here (ADR-014, register C-14).
- It does **not** validate **temporal** semantics. `time` is an opaque integer;
  epoch, range, and monotonicity are a producer concern (register C-11).
- It does **not** import pandas/polars/geopandas or any `views_*` package, and it
  does **not** read viewser or any external store.
- It does **not** carry frame values, metadata, or serialization logic.

---

## 3. Responsibilities and Guarantees

- Holds two numpy integer arrays — `time[N]`, `unit[N]` — and a `SpatialLevel`,
  all length `N`, integer dtype, no NaN. Exposes `n_rows` / `__len__`, `identifiers`
  (`{time, unit}`), and value-object `__eq__` / `__hash__` (by `level` + the arrays' bytes).
- Guarantees **same-level** set operations over `(time, unit)` are pure-numpy and
  deterministic: `intersect`, `reindex` / `searchsorted`, `is_superset_of`, `argsort`,
  and `select` (rows at integer positions or a boolean mask).
- Exposes **cross-level** remap as an injected-mapping protocol — `cross_level_align`
  and the columnar `cross_level_align_arrays` (register C-26); see §2.
- **Row-uniqueness stance (register C-21):** duplicate `(time, unit)` rows are *allowed*
  (not validated at construction — `cross_level_align` can produce them); same-level joins
  *assume* uniqueness and are undefined on duplicates. `has_unique_rows()` is an opt-in
  check for consumers that need the guarantee.
- Guarantees the alignment laws the conformance suite pins: `intersect` commutativity and
  `reindex` self-round-trip (`tests/test_properties.py`), plus the cross-package
  `collapse ∘ reindex` order-independence law (`tests/test_value_object_and_laws.py`).
- Guarantees immutability: operations return a **new** index; structural results
  share buffers where possible (register C-07).

---

## 4. Inputs and Assumptions

- `time` and `unit` are integer numpy arrays of equal length `N`, complete (no NaN).
- `level` is a `SpatialLevel` (cm or pgm) — see its own contract.
- For `cross_level_align` / `cross_level_align_arrays`, the caller supplies the
  `(time, unit) → target_unit` mapping plus the `target_level`; the index never sources it.

Assumptions that do not hold **must raise** at construction (ADR-009), never fall back.

---

## 5. Outputs and Side Effects

- Produces new `SpatioTemporalIndex` instances and integer position arrays
  (`searchsorted` results, intersections). No I/O, no logging, no global state.

---

## 6. Failure Modes and Loudness

- Raises `TypeError` if any identifier array is not integer dtype.
- Raises `ValueError` if arrays differ in length, contain NaN, or `level` is invalid.
- `cross_level_align` raises if called without an injected mapping — it must **never**
  silently fetch or assume one (the defining boundary of ADR-014).
- Nothing fails silently.

---

## 7. Boundaries and Interactions

- **Trusts:** numpy, `SpatialLevel`.
- **Forbidden:** pandas/polars/geopandas, `viewser`, any `views_*`, any store client.
  Enforced by `tests/test_import_enforcement.py` (ADR-002).
- Frames *compose* an index; the index does not know about frames.

---

## 8. Examples of Correct Usage

```python
idx = SpatioTemporalIndex(time=months, unit=cells, level=SpatialLevel.PGM)
positions = idx.searchsorted(other_idx)          # same-level join
combined = idx.intersect(other_idx)              # same-level set op
rows = idx.select(positions)                     # rows at integer positions / mask
country_idx = idx.cross_level_align(            # consumer-injected (time,unit)->country
    mapping=pg_to_country, target_level=SpatialLevel.CM)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: expecting the index to know the mapping itself (mapping is required + injected)
idx.cross_level_align(target_level=SpatialLevel.CM)   # raises — mapping must be injected

# WRONG: passing float "time" and expecting epoch validation
SpatioTemporalIndex(time=year_floats, unit=cells, level=SpatialLevel.CM)  # raises
```

---

## 10. Test Alignment

- **Green:** alignment-law property tests (`intersect` commutativity, `reindex`
  self-round-trip, the cross-package `collapse ∘ reindex` order-independence);
  same-level intersect/reindex round-trips; value-object `__hash__`/`__eq__`/`argsort`.
- **Beige:** `cross_level_align` with a fixture mapping (the injected-mapping contract).
- **Red:** construction with mismatched lengths / NaN / float dtype raises;
  `cross_level_align` without a mapping raises; the import-enforcement test
  (`tests/test_import_enforcement.py`) guards the no-domain boundary.

---

## 11. Evolution Notes

- The public name may change before v1 to avoid the pandas-`Index`/`SpatioTemporalGrid`
  collision (register C-12) — a deliberate pre-pin decision.
- Adding a **required** identifier beyond `{time, unit}` is a MAJOR break (ADR-013);
  optional identifiers are MINOR.

---

## End of Contract

This document defines the **intended meaning** of `SpatioTemporalIndex`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
