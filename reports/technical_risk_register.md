# Technical Risk Register

| Register Info     | Details                              |
|-------------------|--------------------------------------|
| Project           | views-frames                         |
| Owner             | VIEWS platform maintainers           |
| Last Updated      | 2026-06-21                           |
| Total Concerns    | 26                                   |
| Open Concerns     | 12                                   |
| Resolved Concerns | 14                                   |
| Disagreements     | 6                                    |

---

## Tier Definitions

| Tier | Severity | Description |
|------|----------|-------------|
| 1 | Critical | Silent data corruption or output correctness risk. Requires immediate attention. |
| 2 | High | Structural fragility that will cause failures under realistic change scenarios. |
| 3 | Medium | Maintainability or coupling issues that increase cost of change. |
| 4 | Low | Code quality concerns that do not affect correctness or reliability. |

---

## Open Concerns

> Seeded 2026-06-21 from the four design critiques (`critiqus/critique_00..03.md`) and the
> 11 falsification stubs (`tests/test_falsification_*.py`). IDs are permanent; the gap at
> **C-04** is intentional (the original "SpatialLevel slippery slope" finding was merged into
> **C-18**). Many concerns are *resolved-by-decision* in README §13a and are formalised by the
> Epic-1 ADRs 011–016 — the "Resolution path" line names where; they move to **Resolved** when
> the owning ADR merges.

### C-01: `MetricFrame` does not satisfy the frame definition

| Field | Value |
|-------|-------|
| ID | C-01 |
| Tier | 2 |
| Source | falsification-audit (2026-06-20) |
| Trigger | When a developer adds `MetricFrame` as a frame sibling in `src/views_frames/`, verify it carries `(N rows of {time, unit})` — it does not; it is keyed `(target, step, unit)`. |
| Location | `README.md` §4 (frame definition) vs §4.2; `views-evaluation/.../evaluation_frame.py` |

`MetricFrame` is keyed by `(target, step, unit)`, not the `(N rows, {time, unit})` first-axis the §4 frame definition requires (critique_03 P5b, critique_00 §2). Hosting it in the leaf either breaks the abstraction or turns the leaf into a junk drawer. Resolution path: ADR-016 / README §13a.6 keep it (and `EvaluationFrame`) in views-evaluation; the leaf may only define the key/index protocol they conform to. See also D-05.

---

### C-02: "verbatim move" + "unify twins" + "defer sample-axis" cannot co-hold

| Field | Value |
|-------|-------|
| ID | C-02 |
| Tier | 2 |
| Source | falsification-audit (2026-06-20) |
| Trigger | When executing README §10.2 to relocate `PredictionFrame`, verify the sample-axis convention is already closed and the validation is rewritten numpy-only — the three claims are mutually exclusive as written. |
| Location | `README.md` §10.2 vs §4.1; `views-pipeline-core/.../data/prediction_frame.py:5,68` |

The migration plan simultaneously asserts a verbatim move, a twin unification, and a deferred sample-axis decision — which cannot all hold (critique_00 §4, critique_03 P3). Resolution path: ADR-011 (Option C) + ADR-012 (sample axis closed) + §10.2 reworded to "not verbatim". See also C-16, C-17.

---

### C-03: unified twin base under-specified on the fields the twins differ on

| Field | Value |
|-------|-------|
| ID | C-03 |
| Tier | 3 |
| Source | expert-review (2026-06-20) |
| Trigger | When implementing the shared frame machinery, decide whether `feature_names`/`metadata` are base-class fields or per-frame — leaving it implicit recreates a god-class. |
| Location | `README.md` §4.1, §5; `views-datafactory/src/datafactory_adapters/feature_frame.py` |

`FeatureFrame` carries `feature_names` + `metadata`; `PredictionFrame` carries neither (critique_00 §5). A shared base that holds both is the `_ViewsDataset`/C-36 anti-pattern. Resolution path: ADR-011 (Option C — separate siblings, shared index only). See also C-16.

---

### C-05: governance/ownership gap for an N-repo leaf

| Field | Value |
|-------|-------|
| ID | C-05 |
| Tier | 2 |
| Source | expert-review (2026-06-21) |
| Trigger | When the second downstream repo pins `views-frames`, confirm a named owner, a release cadence, and a process for a MAJOR bump that must land across N repos at once exist. |
| Location | `README.md` §8 (SemVer mechanics only) |

The package is load-bearing for ~12 register items across 3+ repos yet specifies no owner, release cadence, or coordinated-bump process (critique_01 §2.5/§3.7, critique_03 P6). A leaf that many repos import with no coordination model is a single point of stall. Resolution path: ADR-016 (conformance-floor + ownership/release). See also C-10, C-13.

---

### C-06: blocking decisions must close before first code

| Field | Value |
|-------|-------|
| ID | C-06 |
| Tier | 3 |
| Source | expert-review (2026-06-20) |
| Trigger | When scaffolding `src/views_frames/` begins, verify the sample-axis, twin-model, metadata, and cross-level decisions are ratified — building `protocols.py`/`_validation.py` before they close forces rework. |
| Location | `README.md` §0, §10.1 |

"Buildable against this doc" was oversold: the load-bearing pieces (index/protocols) cannot be finalised without the blocking decisions (critique_00 §8.2). Resolution path: closed in README §13a (2026-06-21) and ADRs 011–016.

---

### C-08: identifier-set widening is a platform-wide MAJOR break

| Field | Value |
|-------|-------|
| ID | C-08 |
| Tier | 2 |
| Source | expert-review (2026-06-20) |
| Trigger | When a consumer needs a new index axis (`step`, `origin`, `scenario`), verify it is added as an *optional* identifier or metadata field — adding a *required* identifier is a coordinated N-repo MAJOR bump. |
| Location | `README.md` §8 (canonical breaking change), §13a.3 |

The most likely future change (origin/step/provenance axes) is also the most expensive if modelled as a required identifier (critique_01 §3.2). Resolution path: ADR-013 — typed optional-extensible header + fixed `{time, unit}`; future identifiers optional-only. See also D-02.

---

### C-10: conformance-suite version-coordination paradox

| Field | Value |
|-------|-------|
| ID | C-10 |
| Tier | 2 |
| Source | expert-review (2026-06-20) |
| Trigger | When the second consumer adds the conformance suite to its CI at a different pin, confirm a single governed conformance-floor version applies — else consumers test different contracts and drift is not caught. |
| Location | `README.md` §9, §13b.4 |

The conformance suite ships with the leaf and consumers pin different versions, so it tests "my adapter vs my pin," not "all consumers agree" (critique_01 §3.4). Resolution path: ADR-016 (conformance-floor policy). See also C-05.

---

### C-12: `SpatioTemporalIndex` naming collision

| Field | Value |
|-------|-------|
| ID | C-12 |
| Tier | 4 |
| Source | expert-review (2026-06-20) |
| Trigger | When finalising the public API name (before the first consumer pins it), weigh renaming `SpatioTemporalIndex` to avoid collision with `pandas.Index`/`MultiIndex` and datafactory's `SpatioTemporalGrid` — a later rename is an N-repo MAJOR bump. |
| Location | `README.md` §4.3; `views-datafactory` `SpatioTemporalGrid` |

The central type's name overloads the thing it replaces (`pandas.Index`) and a sibling production concept (critique_01 §3.6). Cheap to rename now, expensive later. Out of scope for Epic 1; candidate for a future ADR.

---

### C-13: concentration risk — single point of coordination failure

| Field | Value |
|-------|-------|
| ID | C-13 |
| Tier | 2 |
| Source | expert-review (2026-06-20) |
| Trigger | When sequencing cross-repo adoption, ship a minimal stable v1 before N dependent efforts queue behind it — if the leaf stalls on an open decision or churns its contract, all ~12 dependent register items block at once. |
| Location | `README.md` §12 (~12 register items, 3+ repos) |

The leaf's breadth is both its value and a concentration risk (critique_01 §3.7). Resolution path: minimal stub-first v1 (Epic 1); ADR-016 ownership. See also C-05, D-06.

---

### C-15: cross-level alignment specified nowhere / not tracked

| Field | Value |
|-------|-------|
| ID | C-15 |
| Tier | 3 |
| Source | falsification-audit (2026-06-20) |
| Trigger | When reviewing the index API, confirm cross-level alignment appears as a specified operation with a documented mapping home — it was prose-only in §4.3 and absent from the operation list and the open-decisions list. |
| Location | `README.md` §4.3, §13 |

Both consumers require cross-level alignment yet it was motivated-only, not specified (critique_02 Probe 5). Resolution path: ADR-014 + README §4.3 split (same-level owned / cross-level protocol+injected mapping), added 2026-06-21. See also C-14.

---

### C-16: the twins are not near-1:1 (≥6 divergence axes)

| Field | Value |
|-------|-------|
| ID | C-16 |
| Tier | 2 |
| Source | falsification-audit (2026-06-20) |
| Trigger | When designing the unified contract, account for ≥6 real divergence axes (sample-axis position, `feature_names`/`metadata`, NaN-check, `collapse`/`mmap`, save footprint, pandas import) — "near-1:1" drives an over-optimistic verbatim/unify plan. |
| Location | `views-pipeline-core/.../data/prediction_frame.py` (166 LOC), `views-datafactory/src/datafactory_adapters/feature_frame.py` (220 LOC); `README.md` §1, §4.1 |

The two real classes diverge structurally, most critically on sample-axis position (PF axis-1-always vs FF axis-2-optional) (critique_03 P1). Resolution path: ADR-011 (Option C) + ADR-012 (sample axis) + README §1 corrected. See also C-02, C-03.

---

### C-18: relocating `SpatialLevel` ports C-65 + a gid/id inconsistency

| Field | Value |
|-------|-------|
| ID | C-18 |
| Tier | 3 |
| Source | falsification-audit (2026-06-20) |
| Trigger | When relocating `SpatialLevel`, fix the reversed (entity-first) index tuple → time-first `(month_id, entity)` and the `priogrid_gid`/`priogrid_id` inconsistency — do not port them into the keystone. |
| Location | `views-pipeline-core/.../domain/spatial.py` (`_INDEX_NAMES`, `index_names` vs `entity_column`) |

`SpatialLevel` is numpy-clean to relocate but carries a reversed index tuple (C-65) and a pre/post-rename `priogrid_gid`/`priogrid_id` self-inconsistency; relocating as-is ships both into the package every repo imports (critique_03 F-03, P5a). Resolution path: ADR-015 (fix-don't-port). (This entry subsumes the original C-04 "SpatialLevel slippery slope".)

---

## Disagreements

### D-01: `SpatioTemporalIndex` domain-purity fork (where does cross-level alignment live?)

| Field | Value |
|-------|-------|
| ID | D-01 |
| Source | falsification-audit (2026-06-20) |
| Perspectives | Consumers (reporting/pipeline-core: "the index should do the cm↔pgm join"), Leaf-purity (critique_02: "the mapping is time-varying viewser-sourced domain data — it cannot live in a numpy-only stable leaf") |
| Resolution | **Resolved** — leaf owns the `cross_level_align(index, mapping)` protocol; the consumer injects the mapping (ADR-014, README §13a.4). See C-14. |

---

### D-02: C-48 run-identity is a cross-repo decision the leaf only homes

| Field | Value |
|-------|-------|
| ID | D-02 |
| Source | expert-review (2026-06-20) |
| Perspectives | Reporting ("a stamped run/eval identity in frame metadata is the cure for C-48"), Leaf ("frames give provenance a *home*; selecting *the* run and where it is stored is a cross-repo decision frames do not auto-resolve") |
| Resolution | Partially resolved — ADR-013 gives provenance a typed home; the run-selection/storage decision remains cross-repo (tracked for views-evaluation/reporting). See C-08. |

---

### D-03: twin-unification model — A vs B vs C

| Field | Value |
|-------|-------|
| ID | D-03 |
| Source | expert-review (2026-06-20) |
| Perspectives | Option A (shared `_BaseFrame` — max sharing, but god-class/C-36 risk), Option B (composition + typed header — README intent, discipline-dependent), Option C (separate siblings, shared index only — lowest churn, ~80% value) |
| Resolution | **Resolved** — Option C, ratified by datafactory owner 2026-06-21; A rejected in writing (ADR-011, README §13a.1). See C-03, C-16. |

---

### D-04: the consumer perspectives are simulated, not elicited

| Field | Value |
|-------|-------|
| ID | D-04 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §5 ("uniform structure/idioms suggest one author wrote all three — they are the proposer's hypotheses, not stakeholder buy-in"), Author ("they pressure-test the design from multiple angles") |
| Resolution | Unresolved — add a "Ratified by: <name/date>" header to each perspective; only `from_views-datafactory` is ratified so far. Do not count unratified perspectives as buy-in. |

---

### D-05: missing views-evaluation and model-repo perspectives

| Field | Value |
|-------|-------|
| ID | D-05 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §5b ("views-evaluation owns `EvaluationFrame`/would produce `MetricFrame`; a model repo produces `PredictionFrame` — both absent, and they would stress the riskiest claims"), Scope ("write them before promoting `MetricFrame` from exploratory") |
| Resolution | Unresolved — write the views-evaluation + a model-repo perspective before any `MetricFrame` work. See C-01. |

---

### D-06: portfolio / WIP sequencing across three concurrent cross-repo initiatives

| Field | Value |
|-------|-------|
| ID | D-06 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §6 ("viewser→datafactory migration, views-appwrite extraction, and views-frames relocation compete for the same coordination budget and destroy change attribution if run concurrently"), Leverage ("views-frames is highest-leverage but also the largest coordination load") |
| Resolution | Unresolved — WIP limit: do not run views-frames relocation and views-appwrite extraction in the same repo concurrently; queue consumer adoption behind the data-migration baseline. See C-13. |

---

## Resolved Concerns

> Resolved 2026-06-21 by Epic 5 (leaf completion, v1.0.0, PRs #68–#72).

### C-24: `map_estimate` equivalence test non-portable (red on the numpy floor) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-24 |
| Resolved | 2026-06-21 (v1.0.0, PR #68) |
| Resolution | Root-caused in production, not the test: the tie-break was `argmax(counts/widths)` (matching `np.histogram(density=True)`), whose float64 bin widths differ by ~1 ulp across numpy versions and flip the argmax on ties — a full-bin divergence (15 failed on 1.26.4). Changed to **integer-counts argmax** (lowest-index), which is bit-identical on every numpy build, so `map_estimate` is deterministic and portable. The centre still differs by ~1 ulp (edges), so the test asserts float32 tolerance. The CI **`floor` job now runs pytest** at `numpy==1.26.4` (was mypy only) — the floor is behaviour-checked. CHANGELOG claim scoped to "float32 precision". See C-19, C-22 (resolved). |

---

### C-25: `hdi`/`quantiles` allocate full-grid temporaries, no scale guard — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-25 |
| Resolved | 2026-06-21 (v1.0.0, PR #69) |
| Resolution | Added a shared `ROW_BLOCK` + `block_apply` helper; `hdi`/`quantiles` now run row-blocked like `map_estimate` (peak memory bounded by one block, not the full grid). All three estimators take a `block_rows` kwarg. A `tracemalloc` guard covers `hdi` and `quantiles` at 1e6 rows. Output unchanged. |

---

### C-26: `cross_level_align` dict mapping is O(N) caller allocation at grid scale — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-26 |
| Resolved | 2026-06-21 (v1.0.0, PR #71) |
| Resolution | Benchmark (5M cells) confirmed the dict dominates: ~30× slower, ~10× the memory of the columnar form. Added `cross_level_align_arrays(map_keys, map_vals, …)` + `aggregate_distributions_arrays`, sharing one remap/aggregate path with the dict entries, so a producer holding a grid-scale mapping stays vectorized end-to-end. The `dict` form remains the ergonomic small-mapping path. See C-20 (resolved). |

---

### C-27: conformance floor stale + bump policy unstated — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-27 |
| Resolved | 2026-06-21 (v1.0.0, PR #72) |
| Resolution | At the v1.0 freeze, `CONFORMANCE_FLOOR = "1.0.0"`; GOVERNANCE now states the floor tracks the **whole published conformance surface** (frame contract + laws) and bumps on any breaking change to it (additive surface is MINOR, no bump). ADR-018 records the freeze. See C-10. |

---

> Resolved 2026-06-21 by Epic 4 (hardening, v0.3.0, PRs #63–#65 + register #51).

### C-19: `mypy --strict` not enforced at the numpy floor — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-19 |
| Resolved | 2026-06-21 (v0.3.0, PR #63) |
| Resolution | Added `src/views_frames/_typing.py` (`IntArray = NDArray[np.integer[Any]]`) and parameterized the 14 bare `NDArray[np.integer]` sites. A CI `type-floor` job pins `numpy==1.26.4`; `mypy --strict` is green at the floor (was 14 `[type-arg]` errors). |

---

### C-20: `cross_level_align` mapping static vs ADR-014 time-varying — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-20 |
| Resolved | 2026-06-21 (v0.3.0, PR #64) |
| Resolution | `cross_level_align`/`aggregate_distributions` now take `Mapping[tuple[int, int], int]` keyed by `(time, unit)`; the remap is vectorized (void-viewed keys + `searchsorted`) and fails loud on the old unit-only shape or a missing key. Published `assert_cross_level_alignment_law` + a time-varying test (one cell, two months → two countries). ADR-014 was already correct; the code matched it. See C-15. |

---

### C-21: `(time, unit)` row-uniqueness stance undocumented — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-21 |
| Resolved | 2026-06-21 (v0.3.0, PR #65) |
| Resolution | Documented the stance on `SpatioTemporalIndex` (duplicates allowed — `cross_level_align` makes them; same-level joins assume uniqueness) + added `has_unique_rows()` for consumers that need the guarantee. No construction-time behaviour change. |

---

### C-22: per-row Python loops on the report-stage reduction path — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-22 |
| Resolved | 2026-06-21 (v0.3.0, PRs #64, #65) |
| Resolution | `cross_level_align` (PR #64) and `map_estimate`/`hdi` (PR #65) are vectorized — no per-row Python loop. `map_estimate` uses a row-blocked batched histogram (peak memory `O(block × bins)`, bit-for-bit identical to v0.2.0 incl. the `density=True` tie-break). A `tracemalloc` scale guard at 1e6 rows asserts memory does not scale with `rows × bins`. |

---

### C-23: missing `py.typed` + doc↔code drift — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-23 |
| Resolved | 2026-06-21 (v0.3.0, PR #63) |
| Resolution | `py.typed` shipped in both packages (verified in the wheel); `index` added to the `SpatioTemporalIndexed` protocol (README §5 was already claiming it); README header → v0.3.0, dropped the nonexistent `align` (§4.3), fixed the `collapse` glossary (§13a.2/§14). |

---

> Resolved 2026-06-21 by the v0.1.0 implementation (Epic 2, PRs #31–#35).

### C-07: copy-vs-view semantics unspecified vs the scaling thesis — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-07 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | Frames are immutable; `with_metadata` returns a new frame **sharing** the `values` buffer (`np.shares_memory`), and only `collapse` allocates — the reduced array. `mmap` propagates via `io/npz`. Pinned in `tests/test_properties.py` + the conformance suite. |

---

### C-09: save/load sidecar asymmetry couples `io/` to per-frame schema — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-09 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `io/npz` operates on a generic frame **state dict** (values + identifiers + a JSON header carrying `feature_names`/`metadata`); the I/O layer carries no per-frame schema. `io/arrow` follows the same state contract. |

---

### C-11: the leaf guarantees structural, not temporal, validity — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-11 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `_validation` enforces integer dtype / length-N / completeness only; `time` is an opaque integer (no epoch/range/monotonicity check). Documented in the module + the `SpatioTemporalIndex` CIC. |

---

### C-14: cross-level cm↔pgm alignment needs domain data the leaf forbids — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-14 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `SpatioTemporalIndex.cross_level_align(mapping, target_level)` requires a **consumer-injected** mapping and raises without one; the leaf embeds/fetches no mapping (asserted in tests). Same-level alignment stays pure-numpy. |

---

### C-17: "move `PredictionFrame` verbatim" imports pandas into the numpy-only core — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-17 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `PredictionFrame` was relocated with numpy-only validation (the integer-dtype check replaces `pd.isna`); no pandas import. Guarded by `tests/test_import_enforcement.py`. |

---

---

## Register Conventions

- **ID format:** `C-xx` for concerns, `D-xx` for disagreements. IDs are permanent — gaps in numbering indicate merged or resolved entries.
- **Sources:** `repo-assimilation`, `expert-review`, `test-review`, `falsification-audit`, `persona-critique`, `clean-architecture-review`, `pr-review`, `tech-debt-audit`, `incident`, `manual`.
- **Resolution:** Move to "Resolved Concerns" with resolution date and summary when addressed.
- **Header counts:** Manually maintained — update whenever a concern is added or resolved.
- **Note:** Future concerns will often reference locations in external repos (`views-pipeline-core`, `views-datafactory`, `views-faoapi`, `views-reporting`) because this leaf de-duplicates a data contract not yet relocated. Confirm those locations when the package is stood up.
- **Governed by:** ADR-010 (`docs/ADRs/010_technical_risk_register.md`).
- **Note (v0.2.0, ADR-017):** sample-axis reduction (`collapse`/MAP/HDI/quantiles) was
  removed from the leaf into the `views_frames_summarize` sibling package, eliminating
  the statistics-menu scope leak; the leaf is now a pure data contract.
