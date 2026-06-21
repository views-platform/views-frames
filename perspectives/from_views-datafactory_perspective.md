# `views-frames` from the `views-datafactory` perspective

> The **data-production** repo's view of `views-frames`. Unlike pipeline-core
> (which donates `PredictionFrame` and carries the #181 OOM) and reporting (which
> consumes everything downstream), `views-datafactory` is the **other twin owner**
> — it donates `FeatureFrame` and gains a unified type. It is a **producer** of
> frames, a **zero-internal-dependency** repo that would take its first cross-repo
> dependency, and the place where dense grids become the `(N, F)` arrays that the
> rest of the platform consumes.
>
> Companion to the `views-frames` README (the design bible). Where they disagree,
> the README wins on the contract; this document wins on "what the data production
> repo actually builds today and what it must give up / keep." Reconcile before
> building.
>
> **Ratified by:** Simon (views-datafactory lead), 2026-06-21.
> **Last updated:** 2026-06-21 — post-critique revision. Incorporates findings
> from `critiqus/critique_00–03.md`, the `from_views-faoapi_perspective.md`
> "third twin" evidence, and positions on the three blocking decisions the
> critique cycle surfaced. §§8–9 are substantially revised from the original.

---

## 0. TL;DR for a hurried reader

- `views-datafactory` is the **data production** layer: it harvests raw sources,
  consolidates, compiles to a dense `[T, H, W, C]` grid, assembles all sources,
  and converts to consumer formats via its adapter/query edge. Nine internal
  packages, graph architecture (ADR-012), **zero cross-repo dependencies** today.
- It will **give `views-frames` one thing it currently owns**: `FeatureFrame`
  (relocate, re-export a shim). The grid-specific conversion functions
  (`grid_to_feature_frame`, `grid_to_dataframe`, `grid_to_country_month`,
  `feature_frame_to_grid`) all **stay** — they are adapters, not frame logic.
- Adding `views-frames` would be the **first internal dependency**, but it only
  touches the outermost edge (`datafactory_adapters` + `datafactory_query`),
  never the core pipeline (Layers 0–4).
- No `SpatialLevel` or `SpatioTemporalIndex` exists in this repo today — the
  cm/pgm distinction is implicit in function names. Adoption is straightforward
  but low-priority.
- The architecture is **already aligned**: pandas confined to 3 files at the
  adapter edge, core pipeline pure numpy+pyarrow, `FeatureFrame` docstring
  already says "Designed to be extractable."
- **Post-critique position (2026-06-21):** we endorse **Option C** from
  `critique_01.md` §4 — do *not* unify the concrete frame classes; unify only
  `SpatioTemporalIndex` + protocols + `io/npz`. Relocate FeatureFrame and
  PredictionFrame as separate sibling classes. We endorse the cross-level
  alignment resolution from the falsification audits: the leaf owns the
  *protocol*; the consumer (us) injects the *mapping* as producer-materialized
  metadata — the pattern `views-faoapi` already uses in production (§8.7).

---

## 1. Who `views-datafactory` is (so the contract serves the right producer)

Per its own governance (CLAUDE.md, ADR-012 "graph, not pipeline"), `views-datafactory`
is the **data production** layer of VIEWS:

- It owns the **data graph** — 10 sources (UCDP, ACLED, GHS-POP, GHS-BUILT-S,
  V-Dem, SHDI, PRIO-GRID static, GAUL admin, plus WDI in progress) flow through
  independent paths: harvesting → consolidation → viewpoint → compilation →
  assembly → query. Not all paths traverse all layers (ADR-012).
- It is where raw event records **become a grid**: the assembler concatenates
  compiled source grids into a canonical `[T, H=360, W=720, C]` npy array — the
  dense spatiotemporal cube that downstream models consume.
- It owns the **consumer-facing edge**: `datafactory_adapters` converts the grid
  to `FeatureFrame` and `pd.DataFrame`; `datafactory_query` provides the
  `load_dataset()` API with temporal, geographic, and feature subsetting.
- It has **zero cross-repo dependencies** — nine internal packages
  (`datafactory_provenance`, `_http`, `_priogrid`, `_harvester`,
  `_consolidation`, `_viewpoint`, `_compilation`, `_adapters`, `_query`) plus
  external libraries (numpy, pandas, pyarrow, etc.). No `views_*` import exists
  anywhere in the codebase. This isolation has been a deliberate strength:
  independent release, independent testing, no diamond dependency problems.

`views-frames` matters to this repo because datafactory currently **defines a
transport type (`FeatureFrame`) that is also defined — independently and
divergently — in `views-pipeline-core`.** The contract belongs in a neutral leaf,
not duplicated across two producers with separate release cadences.

---

## 2. The relationship in one line

```
views-frames (leaf, numpy, stable, abstract)
        ▲
        │  datafactory depends toward it — AND donates FeatureFrame
        │  Only datafactory_adapters + datafactory_query touch the leaf.
        │  The core pipeline (Layers 0–4) has zero involvement.
        │
views-datafactory (data production; harvests sources, assembles grids, converts to frames)
```

`views-datafactory` will **import from `views-frames`; `views-frames` imports
nothing from datafactory, ever.** The grid-specific conversion logic stays here
as consumer adapters — the leaf has no concept of a grid, a PRIO-GRID cell, or a
harvested data source.

---

## 3. What datafactory hands off / consumes, frame by frame

### 3.1 `FeatureFrame` — datafactory OWNS it today (donate it)

`datafactory_adapters/feature_frame.py` (221 LOC) is the current home:
`y_features (N, F)` or `(N, F, S)` float32, `REQUIRED_IDENTIFIERS = {"time",
"unit"}`, construction-time validation (`_validate`), `feature_names: list[str]`,
`metadata: dict[str, Any]`, `save`/`load` (npy + npz + json). Properties:
`n_rows`, `n_features`, `sample_count`, `is_sample`. The module docstring already
declares: *"Designed to be extractable: when moved to views-pipeline-core or a
micro-service, only numpy comes with it."*

**Grid coupling that must NOT move:** the `from_grid()` classmethod (lines
157–191) lazy-imports `datafactory_adapters._validation.validate_grid_pgids` and
`datafactory_adapters.grid_to_dataframe.grid_to_feature_frame` — both are
grid-specific. When `FeatureFrame` moves to the leaf, `from_grid()` becomes a
standalone function in `datafactory_adapters` (or is dropped in favor of calling
`grid_to_feature_frame()` directly, which is the canonical path).

**Migration:** relocate the class to `views-frames` and re-export a shim from
`datafactory_adapters/feature_frame.py` (`from views_frames import
FeatureFrame`) so every existing `from datafactory_adapters import FeatureFrame`
keeps working. The adapter's `__init__.py` re-exports are already explicit — the
shim is a one-line change.

**What FeatureFrame has that PredictionFrame does not:** `feature_names` and
`metadata`. The unified leaf type must accommodate both. This is the §13 open
decision that most directly affects datafactory.

### 3.2 `SpatioTemporalIndex` — datafactory should CONSUME it on adapter output

Today `grid_to_feature_frame()` manually constructs identifiers:
```python
identifiers = {"time": all_month_ids, "unit": all_pgids.astype(np.int32)}
```
With the leaf, this becomes a proper `SpatioTemporalIndex` construction. The
`_flatten_grid()` function (the shared helper that does `[T, H, W, C]` →
`(N, C)`) already produces the three arrays needed: `flat_data`, `all_month_ids`,
`all_pgids` — these map directly to the index's `time`, `unit` fields.

**The complement, not the competitor:** `datafactory_priogrid` has a
`SpatioTemporalGrid` (`GridConfig` + `TemporalConfig`) that defines the
production backbone — 360×720 cells, 0.5° resolution, pgid numbering. This is
the *grid*: a fixed spatial structure that produces the dense cube. The leaf's
`SpatioTemporalIndex` is the *frame-level row identifier*: a variable-length
array of `(time, unit)` pairs that locates each row in the flattened output.
These are complementary — the grid produces the data, the index labels it.

### 3.3 `SpatialLevel` — datafactory has NO existing usage (low priority)

There is zero usage of `SpatialLevel`, `spatial_level`, `"cm"`, or `"pgm"` as
vocabulary anywhere in the codebase. The cm/pgm distinction is implicit:

- **pgm** is the native grid level — every cell in the `[T, H, W, C]` grid is a
  PRIO-GRID cell × month.
- **cm** is produced by `grid_to_country_month()` via GAUL code grouping — it is
  a function, not a type.

Adopting `SpatialLevel` would formalize this distinction (e.g., the query API's
`output_format="country_month"` maps cleanly to `SpatialLevel.cm`), but it is
not urgent — datafactory is a producer, not a consumer of the level vocabulary.

### 3.4 Protocols — future improvement for consumer typing

Consumers of `load_dataset()` could type against `Frame` or
`SpatioTemporalIndexed` instead of the concrete `FeatureFrame`. This is a future
improvement — today all consumers know they are getting `FeatureFrame` from the
data factory, and the protocol advantage (accepting *any* frame type) matters
more in pipeline-core and reporting where multiple frame types coexist.

---

## 4. The concrete pains `views-frames` untangles (with what it *does* and *does not* fix)

> Register IDs here are **views-datafactory's** own register.

| Pain (this repo) | Where | What `views-frames` does |
|---|---|---|
| **Diverging implementations — at least three** (`FeatureFrame` here, `PredictionFrame` in pipeline-core, `FAO_PGMDataset` in faoapi — see `from_views-faoapi_perspective.md` §9) | `feature_frame.py` vs pipeline-core's `prediction_frame.py` vs faoapi's `data/handlers.py` (~1,550 LOC, drifted further — accepts both `priogrid_gid` and `priogrid_id`, carries 9 geo-metadata columns) | **Solves.** Shared leaf, one release cadence, one test suite. The implementations now converge on a shared contract (REP). Note: the twins are *not* near-1:1 (`critique_03.md` P1 — ≥6 divergence axes); the unification must account for real structural differences. |
| **`from_grid()` couples the frame to grid internals** | `feature_frame.py:157-191` lazy-imports `_validation` + `grid_to_dataframe` | **Solves.** `from_grid()` becomes an adapter function; the frame class in the leaf has no grid knowledge. Separation of concerns (SRP). |
| **Implicit cm/pgm — no typed spatial level** | `grid_to_country_month()` function name; `load_dataset(output_format="country_month")` string | **Enables.** `SpatialLevel` formalizes what is currently implicit. Low-priority for this repo. |
| **Untyped consumer bridge** | `generate_consumer_data.py` renames factory→VIEWSER vocabulary | **Enables.** Frames give the bridge a typed input; long-term, the VIEWSER vocabulary (`lr_sb_best`, `lr_ns_best`) becomes redundant as consumers adopt frames directly. |

**The honest line:** views-datafactory has fewer pains than pipeline-core or
reporting because its architecture is already clean — no cross-repo leakage, no
mutation of foreign objects, no god-class data handler, no pandas in the hot
path. The main value is **contract unification** (the FeatureFrame/PredictionFrame/
FAO_PGMDataset divergence — at least three independent implementations — is the
concrete risk views-frames removes) and **typed contracts** at the consumer
boundary. Post-critique, we also note: the twins are not near-1:1 (critique_03
P1 documents ≥6 divergence axes), so unification requires explicit decisions on
the sample-axis convention and the `feature_names`/`metadata` placement — not a
trivial merge.

---

## 5. What stays in `views-datafactory` (explicitly NOT `views-frames`)

Per README §11 and SRP/CRP, the leaf takes the *contract*; this repo keeps
everything production-shaped:

- **The entire production pipeline** — harvesting, consolidation, viewpoint,
  compilation, assembly. The leaf has no concept of a raw data source, a snapshot,
  a viewpoint builder, or a compiled grid.
- **All adapter functions** — `grid_to_feature_frame()`, `grid_to_dataframe()`,
  `grid_to_country_month()`, `feature_frame_to_grid()`. These are grid-specific
  conversion logic. The leaf never knows about `[T, H, W, C]` arrays.
- **`_flatten_grid()`** — the shared helper that transforms `[T, H, W, C]` →
  `(N, C)` and constructs the `(time, unit)` identifier arrays. This is the
  heart of the grid→frame conversion and is purely a production concern.
- **ADR-040 conservation and reconciliation assertions** — `assert_cm_conservation()`
  and `assert_hierarchical_reconciliation()`. These verify domain-specific invariants
  (count conservation, GAUL nesting) that belong in the data producer, not the
  transport contract.
- **The consumer bridge** — `generate_consumer_data.py` and its VIEWSER
  vocabulary mapping (`ged_sb_best` → `lr_sb_best`). This stays as a strangler
  adapter until all consumers migrate to frames.
- **The `SpatioTemporalGrid`** — `datafactory_priogrid`'s grid backbone
  (`GridConfig` + `TemporalConfig`, cell generators, pgid↔latlon mapping). This
  is complementary to the leaf's `SpatioTemporalIndex`, not replaced by it (§3.2).
- **Pandas at the adapter edge** — the 3 files that import pandas
  (`grid_to_dataframe.py`, `grid_to_country_month.py`, `dataset.py`) stay
  because DataFrame output is a consumer format. The leaf bans pandas; we use it
  at the boundary, which is exactly the adapter pattern the leaf expects.

---

## 6. How datafactory's existing patterns already point at frames

- **"Designed to be extractable"** — both the `FeatureFrame` module docstring
  (line 7: *"when moved to views-pipeline-core or a micro-service, only numpy
  comes with it"*) and the `__init__.py` docstring (line 6: *"this module may
  move to views-pipeline-core or a dedicated micro-service"*) explicitly
  anticipate the extraction that views-frames formalizes.
- **pandas is already confined to the edge.** The entire core pipeline (Layers
  0–4: provenance, http, priogrid, harvester, consolidation, viewpoint,
  compilation) uses only numpy + pyarrow. Pandas appears in exactly 3 source
  files, all at the consumer-facing boundary. This is the adapter-at-the-edge
  pattern views-frames expects from consumers.
- **`_flatten_grid()` is already factored out.** The grid→frame conversion is
  cleanly separated from the frame itself — `_flatten_grid()` produces the raw
  arrays, and `grid_to_feature_frame()` wraps them in a `FeatureFrame`. This
  adapter-constructs-frame pattern is exactly what the leaf migration preserves.
- **`from_grid()` uses lazy imports** to minimize coupling (lines 179–187). This
  was a deliberate design choice to keep `FeatureFrame` extractable — it can be
  imported without pulling in grid validation or conversion code.
- **`REQUIRED_IDENTIFIERS = {"time", "unit"}`** — the same constant, the same
  semantics, the same validation, in both twins. The contract is already
  converged; only the location is duplicated.

---

## 7. Migration implications for datafactory (Strangler, aligned with README §10)

datafactory's migration is one of the simpler ones — step 3 of README §10,
with minimal follow-on work.

> **Post-critique caveat (2026-06-21).** The critiques (especially critique_03
> F-01, P1, P3) have shown that the README's "move `PredictionFrame` verbatim"
> framing is self-contradictory (PF imports pandas; the leaf forbids pandas — the
> move requires a numpy-only rewrite of identifier validation). Our FeatureFrame
> is already numpy-only, so our migration *is* close to verbatim — but we should
> not assume the leaf's `FeatureFrame` class will be a byte-for-byte copy of
> ours. The **sample-axis convention** (§13.6) must be decided first: our sample
> axis is at position 2 (optional, `(N, F, S)`), pipeline-core's is at position 1
> (always present, `(N, S)`). Until this is resolved, the two classes cannot share
> a common validation path.

**Steps (gated on blocking decisions being resolved first — see §8.7):**

1. **Relocate `FeatureFrame`** to the leaf; re-export a shim from
   `datafactory_adapters/feature_frame.py` (`from views_frames import
   FeatureFrame`). Every `from datafactory_adapters import FeatureFrame` keeps
   working. The `__init__.py` re-export (currently line 12:
   `from datafactory_adapters.feature_frame import FeatureFrame`) becomes
   `from views_frames import FeatureFrame` — one line changes.
2. **Extract `from_grid()`** from `FeatureFrame` class to a standalone function
   in `datafactory_adapters` (or deprecate in favor of the existing
   `grid_to_feature_frame()` which is already the canonical path — `from_grid()`
   is a convenience wrapper around it). The 2 internal callers (`examples/
   ex_feature_frame_output.py`, tests) are trivially updated.
3. **`grid_to_feature_frame()`** continues constructing the leaf's `FeatureFrame`
   — it becomes a factory function for the external type. No signature change.
4. **`feature_frame_to_grid()`** continues accepting the leaf's `FeatureFrame` —
   parameter type unchanged (it reads `.identifiers["time"]`,
   `.identifiers["unit"]`, `.y_features`, `.n_features` — all preserved by the
   leaf).
5. **`load_dataset()` return type** annotation updates from
   `FeatureFrame | pd.DataFrame` to `views_frames.FeatureFrame | pd.DataFrame`.
6. **`pyproject.toml`** adds `views-frames>=1.0,<2` to dependencies — the first
   internal dependency, touching only the adapter/query edge.
7. **CI** — run views-frames' conformance test suite against
   `grid_to_feature_frame()` output. This verifies our adapter produces valid
   frames.
8. **Tests** — the 39 FeatureFrame references across test files update imports
   via the shim (most require zero changes).

> Sequencing: none of this blocks on pipeline-core's migration (§10.1–2). The
> two frame classes can be relocated independently; the leaf unifies them at
> the contract level (shared index, shared protocols, shared validation) while
> keeping them as separate sibling classes (Option C, critique_01 §4).

---

## 8. What datafactory needs the contract to guarantee (asks / open questions)

1. **`feature_names: list[str]` and `metadata: dict` must be first-class** in the
   unified `FeatureFrame`. These fields exist in datafactory's version but not in
   `PredictionFrame`. If the leaf's `FeatureFrame` drops or renames them, every
   adapter in this repo breaks. (README §4.1 already lists `feature_names` as an
   existing field — confirm `metadata` is also preserved.)
2. **`save(dir)` / `load(dir)` roundtrip must preserve `feature_names` and
   `metadata`.** The current on-disk format writes `feature_names.json` and
   `metadata.json` as sidecars alongside `y_features.npy` and
   `identifiers.npz`. The leaf's `io/npz.py` must handle these (or the
   `Persistable` protocol must allow consumer extensions — but frame-level fields
   should serialize with the frame, not require an adapter).
3. **`from_grid()` as an adapter pattern, not a frame method.** Confirm that the
   leaf does *not* provide grid-construction classmethods — this is consumer-side
   logic. Datafactory will provide `grid_to_feature_frame()` as its adapter.
4. **`SpatioTemporalGrid` vs `SpatioTemporalIndex` — complementary, not
   competing.** Confirm the leaf's naming does not create confusion with
   datafactory's production-side grid concept. The grid is a fixed 360×720
   spatial structure; the index is a variable-length row identifier. These are
   different layers of abstraction. (critique_01 §3.6 raises the broader naming
   collision — `SpatioTemporalIndex` overloads `pandas.Index` and our
   `SpatioTemporalGrid`; consider a less loaded name.)
5. **Conformance test suite must be runnable against adapter output.** The
   views-frames `tests/conformance/` suite should be importable so that
   datafactory's CI can call it on `grid_to_feature_frame()` output, verifying
   that every produced `FeatureFrame` satisfies the leaf's contract. (Note:
   critique_01 §3.4 flags a version-coordination paradox — pinned consumers
   running different conformance versions is not the same as a shared contract.
   A **conformance floor** policy is needed.)
6. **`month_id` temporal convention.** Datafactory uses VIEWS month_ids with
   configurable epoch (default 1980: January 1980 = month_id 1). The leaf's
   `SpatioTemporalIndex` should be epoch-agnostic — the `time` identifier is an
   opaque integer whose interpretation belongs to the producer, not the transport.
   (critique_01 §3.5 correctly notes this means the leaf's "valid identifiers"
   guarantee is *structural*, not *temporal* — state this explicitly.)
7. **Copy-vs-view semantics for immutable frame operations.** critique_01 §3.1
   identifies a latent contradiction: §3.3 immutability + §7 scaling. On the
   9–18 GB tensors that motivate the package, a naive `with_metadata()` that
   copies the `values` buffer reintroduces the blow-up §7 exists to kill.
   Structural/metadata-only operations must return frames that *share* the
   underlying buffer (numpy view / zero-copy), and `mmap` must propagate. Pin
   this in the conformance suite.

---

## 8b. Datafactory's positions on the three blocking decisions

> Added 2026-06-21 after reviewing `critiqus/critique_00–03.md` and
> `from_views-faoapi_perspective.md`. The critique cycle surfaced three decisions
> that **must close before the first relocation** — they are no longer open
> questions but forced choices. This section states our position on each.

### Position 1: Twin unification — Option C (separate classes, shared index)

We endorse **Option C** from `critique_01.md` §4. Do *not* unify the concrete
frame classes into a shared base. Unify only `SpatioTemporalIndex` +
`_validation` + protocols + `io/npz`. Relocate `FeatureFrame` and
`PredictionFrame` as **separate sibling classes** that both compose the shared
index and satisfy the same protocols.

**Why (from our vantage point):**

- Our `FeatureFrame` carries `feature_names` (required) + `metadata` (required)
  + a feature axis `(N, F)` or `(N, F, S)`. PredictionFrame has none of these.
  A shared base that carries all fields is the `_ViewsDataset` anti-pattern
  (C-36) reborn (Option A — reject).
- Option B (composition + protocols) is the README's stated intent, but its
  discipline requirement ("the small `_validation` helper must not become a
  god-class") is exactly the kind of promise that erodes under pressure.
  Option C captures ~80% of the value (shared index, shared validation, single
  release cadence) without the risk.
- faoapi's `FAO_PGMDataset` (the third implementation, `critique_03.md` P1,
  `from_views-faoapi_perspective.md` §9) diverges even further — it accepts
  both `priogrid_gid` and `priogrid_id`, carries 9 geo-metadata columns, and
  collapses samples its own way. A single shared base cannot accommodate three
  implementations; separate classes behind shared protocols can.

**Upgrade to B** if and when a third frame (e.g. `TargetFrame`) proves the
composed metadata header is genuinely reused — not before.

### Position 2: Cross-level alignment — leaf protocol, consumer-injected mapping

We endorse the resolution the falsification audits forced
(`critique_02.md`, the entire audit; `critique_03.md` F-02):

- **Same-level alignment** (intersect, reindex, searchsorted over `(time, unit)`
  at a single `SpatialLevel`) **lives in the leaf** — domain-free, pure-numpy.
- **Cross-level alignment** (country→grid, cm↔pgm joins) needs a
  `priogrid→country` mapping that is *external, viewser-sourced, time-varying*
  (`views-reporting/metadata/entity_metadata.py`). The leaf **owns the
  protocol** (`cross_level_align(index, mapping)` or similar); the **consumer
  injects the mapping**.
- **The mapping is producer-materialized metadata.** This is not a theoretical
  resolution — `views-faoapi` has already proven it in production
  (`from_views-faoapi_perspective.md` §3.5, §8.3): faoapi resolves
  `pg→country/gaul` by reading 9 pre-joined metadata columns, materialized by
  the upstream `un_fao` postprocessor. **We are the canonical example of the
  producer side**: our area-majority GAUL work (ADR-044) produces the
  `pgid→country` mapping, and our V-Dem and SHDI viewpoint builders broadcast
  country-level values to grid cells using it. We would inject that mapping into
  the cross-level protocol.
- **The leaf never embeds, fetches, or versions the mapping.** This is what
  preserves maximal stability (critique_02 Probe 4).

### Position 3: MetricFrame — out of the leaf

We endorse the position from `critique_00.md` §2, `critique_01.md` §2.2, and
`critique_03.md` P5b: `MetricFrame` does not satisfy the frame definition (§4:
"an array whose first axis is N rows carrying `{time, unit}`"). It is keyed by
`(target, step, unit)` — a different shape and key space.

- Keep it in **views-evaluation** alongside `EvaluationFrame`.
- If it must live in a shared package, generalize the index protocol first —
  but that generalization should be a deliberate v2 decision, not a v1 stretch.
- faoapi's perspective (§3.5) confirms this: the platform's most external
  consumer never wants `MetricFrame`. It is an evaluation artifact, not a data
  transport type.

### Sequencing: the WIP constraint

`critique_01.md` §6 raises a real portfolio concern: three concurrent cross-repo
extractions (viewser→datafactory data migration, views-appwrite, views-frames)
all touch the same repos and compete for the same coordination budget. From our
vantage point:

- The viewser→datafactory data migration changes *data values* and needs an
  attributable diff. It should reach baseline first.
- Our readiness gate stories (#211, #212, #213) are still pending.
  `development` is ahead of `main`. We are not yet at the baseline the
  sequencing requires.
- views-frames v1 (the index + protocols + twin relocation, behavior-preserving)
  can proceed in parallel with our data migration *only* because it is
  contract-preserving. But our **consumer adoption** (§7 steps 1–8) should
  queue behind the data migration baseline.
- Do not run views-frames relocation and views-appwrite extraction in the same
  repo at the same time.

---

## 9. The dependency posture question

This section is unique to the datafactory perspective. Pipeline-core and
reporting already have cross-repo dependencies; for datafactory, `views-frames`
would be the **first**.

**What isolation has bought us:**
- Independent release cadence — deploy datafactory without touching any other
  repo.
- Independent testing — the full test suite (1913 tests, ~6 min) runs with zero
  network or cross-repo setup.
- No diamond dependency problems — `numpy` version is ours to choose.

**Why the leaf is the right first dependency:**
- `views-frames` is maximally stable (SDP) and maximally abstract (SAP) — the
  safest possible dependency to take.
- Its dependency is `numpy` only — no pip/uv resolution conflicts with our
  existing stack.
- The dependency touches only the adapter/query edge (2 of 9 packages). The
  core pipeline (provenance, http, priogrid, harvester, consolidation, viewpoint,
  compilation) remains untouched and independently testable.
- The alternative — continuing to own a diverging twin — is already a liability.
  Two repos defining "an array aligned to (time, unit)" with different release
  cadences is how contract drift happens silently.

**Mitigations:**
- Pin to `>=1.0,<2` — MAJOR bumps require explicit opt-in.
- Run the conformance test suite in CI — contract drift is caught before release.
- The shim pattern means rollback is a one-line change — remove the re-export,
  restore the local class.

---

## 10. Cross-references

- `views-frames` README: §1 (problems — the diverging-twins bullet, which faoapi
  extends to triplets), §2 (DAG position), §3 (hard constraints — numpy-only, no
  app logic), §4 (frame family — §4.1 existing, §4.3 `SpatioTemporalIndex`), §7
  (serialization — npz native), §10 (migration — step 3 is datafactory's), §11
  (scope — adapters stay in consumer repos), §13 (open decisions — §13.5
  metadata, §13.6 sample-axis convention).
- `views-frames` critiques: `critiqus/critique_00.md` (broad reflection — 7 core
  findings, the index-purity fork as #1), `critique_01.md` (independent second
  pass — converges, adds 7 net-new findings, worked twin-unification analysis
  with Options A/B/C), `critique_02.md` (falsification of the domain-free
  cross-level claim — 5 hard, definitive), `critique_03.md` (wider falsification
  — 4 hard, 1 soft, 1 mixed; "the README describes the destination, then claims
  it as the origin").
- `views-frames` falsification tests:
  `tests/test_falsification_domain_free_crosslevel.py` (5 stubs, P2),
  `tests/test_falsification_twin_parity.py` (3 stubs, P1/P3),
  `tests/test_falsification_immutability_copy.py` (1 stub, P4),
  `tests/test_falsification_spatiallevel_and_metricframe.py` (2 stubs, P5).
- Companion perspectives:
  `perspectives/from_views-pipeline-core_perspective.md` (the PredictionFrame
  owner; carries the #181 OOM story),
  `perspectives/from_views-reporting_perspective.md` (the downstream consumer;
  carries the C-48 eval-report story),
  `perspectives/from_views-appwrite_perspective.md` (the other leaf — storage
  client; frame-ready because frame-ignorant),
  `perspectives/from_views-faoapi_perspective.md` (the third twin —
  `FAO_PGMDataset`; the existence proof for producer-materialized-metadata as
  the cross-level alignment answer).
- `views-datafactory` governance: CLAUDE.md (architecture, package layout,
  design principles), ADR-012 (graph, not pipeline — layer decoupling), ADR-009
  (boundary contracts — `[T, H, W, C]` grid shape), ADR-040 (conservation and
  reconciliation invariants), ADR-044 (source taxonomy — GAUL admin boundaries
  produce the `pgid→country` mapping that would be injected into a cross-level
  protocol).
- The `FeatureFrame` source:
  `views-datafactory/src/datafactory_adapters/feature_frame.py` (221 LOC).
- The adapter layer:
  `views-datafactory/src/datafactory_adapters/__init__.py` (5 public exports).
- The consumer API:
  `views-datafactory/src/datafactory_query/dataset.py` (`load_dataset()`).
