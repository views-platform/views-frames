
# ADR-001: Ontology of the Repository

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

`views-frames` exists to be the platform's **data-contract leaf**: the single, shared
definition of "an array aligned to `(time, unit)`" that every model, evaluator,
reconciler, and report agrees on. Its entire value proposition depends on a sharp
boundary — it must contain everything about *being an immutable array+identifier value
object* and **nothing** about VIEWS domain logic, pandas, or where bytes end up. The
design bible is explicit that the most likely way this leaf fails is accretion: someone
adds an adapter, then grid knowledge, then a domain mapping, and it becomes
"pipeline-core-lite" — re-acquiring the very god-class (`_ViewsDataset`, C-36) the leaf
exists to escape.

Without an explicit ontology, systems accumulate implicit concepts, overloaded
abstractions, and objects that mix responsibilities. For this leaf the danger is
concrete: the twins it unifies already diverged (`PredictionFrame` even imports pandas),
and the alignment math keeps trying to drag domain reference data (the priogrid→country
mapping) into the core. The design bible's README §11 already enumerates the
non-entities; this ADR ratifies the closed set of categories that *are* allowed.

No code exists yet. The categories below describe the **intended** architecture from
README §4–§6 and §13a. When implementation begins, classes must map onto these
categories or be rejected.

---

## Decision

This repository defines a **closed set of conceptual categories** that are allowed to
exist. Each category has a clear semantic role, an expected stability level, and explicit
boundaries.

Anything that does not clearly belong to one of these categories — in particular,
anything that encodes VIEWS domain meaning, pandas, or application logic — is considered
**out of scope** and must be redesigned or rejected.

---

## Core Ontological Categories

Each category lists its purpose, authority level, expected stability, representative
entities (planned), and what it must not contain.

### 1. Spatiotemporal Index
- **Purpose:** The genuinely-reused primitive — `{time, unit, level}` plus same-level, pure-numpy alignment (`intersect`, `align`/`reindex`, `is_superset_of`, `searchsorted`-based joins over `(time, unit)` at a single `SpatialLevel`). This is the label-alignment that today drags pandas back into the hot path; it lives here unconditionally (README §4.3).
- **Representative entities:** `SpatioTemporalIndex` — planned in `src/views_frames/index.py`.
- **Authority:** Authoritative (the shared identifier/alignment contract).
- **Stability:** Stable.
- **Must not contain:** The cross-level `priogrid→country` mapping data (consumer-injected; the leaf owns only the `cross_level_align(index, mapping)` signature), any `views_*` import, or pandas.

### 2. Identifier Vocabulary
- **Purpose:** The cm/pgm level labels that name the unit column (`entity_column`, `index_names`: cm→`country_id`, pgm→`priogrid_id`). Ends the bare-string `"cm"`/`"pgm"` sprawl (C-38).
- **Representative entities:** `SpatialLevel` — relocated here into `src/views_frames/spatial_level.py` (with the C-65 time-first index-tuple and the `priogrid_gid`/`priogrid_id` inconsistency **fixed, not ported**).
- **Authority:** Authoritative for the level vocabulary.
- **Stability:** Stable.
- **Must not contain:** Unit values or ranges, the GAUL hierarchy, `month_id` epoch semantics, or the cross-level mapping. Labels only.

### 3. Frames
- **Purpose:** The data contract itself — immutable array+identifier value objects, each a numeric array (first axis = N rows) carrying complete `{time, unit}` identifiers and an explicit trailing sample axis `S ≥ 1`.
- **Representative entities:** `FeatureFrame`, `PredictionFrame`, `TargetFrame` (later `WeightFrame`, `MaskFrame`) — `src/views_frames/feature_frame.py`, `prediction_frame.py`, etc. **Separate sibling classes, no shared base** (Option C; README §5/§13a).
- **Authority:** Authoritative (the published data contract).
- **Stability:** Stable.
- **Must not contain:** pandas/`object`-dtype, grid knowledge (`from_grid`, `SpatioTemporalGrid`), application logic, or a `_BaseFrame` god-class they extend.

### 4. Protocols
- **Purpose:** The published abstract surface consumers type against (DIP/ISP). Segregated so no consumer depends on methods it does not use.
- **Representative entities:** `Frame`, `SpatioTemporalIndexed`, `Sampled`, `Persistable` — `src/views_frames/protocols.py`.
- **Authority:** Authoritative (the abstract contract; concretes are an implementation detail).
- **Stability:** Stable.
- **Must not contain:** Concrete implementation, I/O bodies, or consumer-specific methods.

### 5. Metadata Header
- **Purpose:** A typed, optional-extensible header carrying provenance (model, run_type, timestamp, seed) and `feature_names` — the typed home for the run-identity cure (C-48 / #178). Not a free-form dict (that re-opens C-48 store-side and cannot be validated).
- **Representative entities:** the typed metadata header composed into frames.
- **Authority:** Derived / pass-through — the consumer owns provenance *resolution*; the leaf only carries the typed fields.
- **Stability:** **Evolving** — new **optional** fields are MINOR additions (README §8).
- **Must not contain:** Required domain fields, or any field whose meaning the leaf must resolve.

### 6. Construction Validation
- **Purpose:** The shared construction-time invariant helper that enforces the §3 constraints (float32 values, integer/length-N/no-NaN identifiers, no `object` dtype) and **fails loud** in `__init__`.
- **Representative entities:** `_validation` — `src/views_frames/_validation.py` (private helper).
- **Authority:** Infrastructure.
- **Stability:** Stable.
- **Must not contain:** Temporal/epoch semantics (`time` is an opaque integer — the producer's concern), or accreting business rules into a god-class.

### 7. Serialization Adapters (`io/`)
- **Purpose:** Frame↔bytes **format** — native (`.npy` + `.npz`, `mmap`-capable) and flat columnar interchange (`.parquet`, the scalable replacement for list-in-cell). Format, not transport.
- **Representative entities:** `io/npz`, `io/arrow` — `src/views_frames/io/`.
- **Authority:** Infrastructure.
- **Stability:** Stable for the native format and the public round-trip; `io/arrow` may **evolve** as the disk format matures, but the round-trip guarantee stays constant.
- **Must not contain:** Knowledge of *where* bytes go (store/appwrite/forecasts) — that is a consumer adapter; `pyarrow` lives only behind `io/`, never in the core.

---

## Stability Rules

- Categories 1–4 and 6 are expected to be **stable** across the lifetime of the project. They change only on deliberate, ADR-worthy decisions.
- **Metadata Header (5)** is explicitly allowed to evolve — new optional fields are back-compatible MINOR additions; the leaf declares no opinion on what provenance *means*.
- **Serialization Adapters (7):** `io/arrow` may evolve as the columnar disk format matures, but its public round-trip (frame in == frame out) must stay constant.

This encodes the design bible's governing principle: *unstable depends on stable* (README §8, SAP). The evolving surfaces are isolated so churn does not propagate into the stable contract.

---

## Explicit Non-Entities

The following are **not allowed** as first-class concepts in this repository (from README §11):

- **Forbidden dependencies in the core** — `pandas`, `polars`, `geopandas`, `wandb`, `viewser`, `torch`, or **any `views_*` import**. numpy only; `pyarrow` allowed only behind `io/`.
- **The cross-level mapping** — the `priogrid→country` / GAUL hierarchy is viewser-sourced, time-varying domain reference data; it is **consumer-injected**, never embedded, fetched, or versioned here (resolves `critiqus/critique_02.md`).
- **`MetricFrame` / `EvaluationFrame`** — eval-output vocabulary owned by `views-evaluation`; the leaf may define only the *index protocol* they conform to.
- **Adapters** — `from_grid()`, `PredictionFrameConverter`, store/pandas/appwrite/forecasts edges, reconciliation math, model code, report rendering. These are *edges* in consumer repos.
- **The grid backbone** — `SpatioTemporalGrid` stays out of the leaf.
- **list-in-cell `object` dtype** — the measured non-scaler (C-40/C-66/C-186); banned.
- **A `_BaseFrame` god-class** — recreates `_ViewsDataset` (C-36); the base is a Protocol, code is shared by composition.
- Implicit or inferred semantics; objects that mix multiple ontological roles; "convenience" abstractions that hide meaning.

**Review test:** *"Would this concept make sense to any consumer of an array aligned to
`(time, unit)`, with zero VIEWS-domain knowledge?"* If it needs domain meaning to make
sense, it does not belong here at all.

---

## Consequences

### Positive
- Shared vocabulary across contributors and the N consumer repos that depend on the leaf
- A concrete review test for every PR (the zero-domain-knowledge test above)
- Reduced conceptual drift; the boundary that prevents a second god-class is written down

### Negative
- Requires upfront discipline; convenient shortcuts (a built-in pandas loader, an embedded mapping) are disallowed
- Consumers must own their own adapters, provenance resolution, and the cross-level mapping

These trade-offs are accepted.

---

## Notes

This ADR defines *what exists*, not *how components depend on each other*.
Dependency rules (the platform DAG and intra-package layering) are defined in ADR-002;
semantic authority (typed declarations over inference) in ADR-003; boundary contracts
(the protocols, construction validation, the injected-mapping boundary) in ADR-009.
