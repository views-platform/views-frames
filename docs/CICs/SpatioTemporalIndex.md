
# Class Intent Contract: SpatioTemporalIndex

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-21
**Related ADRs:** ADR-001, ADR-002, ADR-009, ADR-014, ADR-015

> Note: `SpatioTemporalIndex` is a **stub** in Epic 1 (`src/views_frames/index.py`
> raises on construction). This contract defines the *intended* behaviour the Epic-2
> implementation must satisfy.

---

## 1. Purpose

`SpatioTemporalIndex` is the genuinely-reused primitive of the package: the
`{time, unit, level}` integer row identity plus the **same-level**, pure-numpy
alignment logic (intersect / align / reindex / searchsorted) that gives arrays the
label-alignment that today drags pandas back into the hot path.

---

## 2. Non-Goals (Explicit Exclusions)

- It does **not** own or perform **cross-level** (cm↔pgm, country↔grid) joins as a
  data operation. It exposes the `cross_level_align(index, mapping)` *protocol* only;
  the time-varying `priogrid→country` mapping is **injected by the consumer** and is
  never embedded, fetched, or versioned here (ADR-014, register C-14).
- It does **not** validate **temporal** semantics. `time` is an opaque integer;
  epoch, range, and monotonicity are a producer concern (register C-11).
- It does **not** import pandas/polars/geopandas or any `views_*` package, and it
  does **not** read viewser or any external store.
- It does **not** carry frame values, metadata, or serialization logic.

---

## 3. Responsibilities and Guarantees

- Holds three numpy integer arrays — `time[N]`, `unit[N]` — and a `SpatialLevel`,
  all length `N`, integer dtype, no NaN.
- Guarantees **same-level** set operations over `(time, unit)` are pure-numpy and
  deterministic: `intersect`, `align`/`reindex`, `is_superset_of`, `argsort`,
  `searchsorted`-based joins.
- Guarantees the alignment laws the conformance suite pins (e.g. intersection is
  commutative; `align` then `collapse` == `collapse` then `align`).
- Guarantees immutability: operations return a **new** index; structural results
  share buffers where possible (register C-07).

---

## 4. Inputs and Assumptions

- `time` and `unit` are integer numpy arrays of equal length `N`, complete (no NaN).
- `level` is a `SpatialLevel` (cm or pgm) — see its own contract.
- For `cross_level_align`, the caller supplies the `(time, priogrid) → country`
  mapping as an argument; the index never sources it.

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
grid_idx = idx.cross_level_align(country_idx, mapping=pg_to_country)  # injected
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: expecting the index to know the country mapping itself
idx.cross_level_align(country_idx)               # raises — mapping must be injected

# WRONG: passing float "time" and expecting epoch validation
SpatioTemporalIndex(time=year_floats, unit=cells, level=SpatialLevel.CM)  # raises
```

---

## 10. Test Alignment

- **Green:** alignment-law property tests (commutativity, align/collapse order);
  same-level intersect/reindex round-trips.
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
