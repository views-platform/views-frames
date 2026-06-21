# `views-frames` from the `views-faoapi` perspective

> The **delivery / external-serving** repo's view of `views-frames`. Unlike
> pipeline-core (which donates `PredictionFrame` and carries the #181 OOM),
> datafactory (which donates `FeatureFrame`), and reporting (which renders to
> HTML), `views-faoapi` is the **furthest-downstream consumer** — a FastAPI service
> that serves VIEWS conflict forecasts to the **United Nations FAO** over HTTP. It
> is the place where a frame finally crosses the wire to an *external* organisation.
>
> It is also the platform's **unacknowledged third twin**: `views-faoapi` carries
> its *own* fork of the `_ViewsDataset`/`PGMDataset` family
> (`data/handlers.py`, ~1,550 LOC) and its *own* fork of the Appwrite layer
> (`managers/appwrite.py`, ~2,020 LOC). The README frames the duplication as
> "twins" (FeatureFrame ≠ PredictionFrame); this repo is the proof the duplication
> is worse than that — at least **triplets** for the data handler. That makes
> `views-faoapi` the single clearest demonstration of *why* the leaf exists.
>
> Companion to the `views-frames` README (the design bible). Where they disagree,
> the README wins on the contract; this document wins on "what the delivery layer
> actually serves and what it must give up / keep." Reconcile before building.

---

## 0. TL;DR for a hurried reader

- `views-faoapi` is the **serving/delivery** layer: a FastAPI service that pulls
  prediction + historical parquet from Appwrite, computes posterior summaries
  (MAP + HDI) and geographic aggregations, and serves them as JSON to UN FAO. It is
  a *consumer*, an *external boundary*, and — uncomfortably — a *third independent
  re-implementation* of the platform's core data handler.
- It will **consume three things** from `views-frames`: `PredictionFrame` (the
  forecast samples it serves), `TargetFrame` (the historical observations it serves
  alongside), and the `SpatioTemporalIndex` + `SpatialLevel` vocabulary (it has its
  own `(month_id, priogrid_id)` index logic, its own `pg/country/gaul0/1/2`
  level dispatch, and its own `priogrid_gid→priogrid_id` shim).
- It **donates nothing the leaf wants** — but it *retires* a fork. Its
  `FAO_PGMDataset`/`_ViewsDataset` (`data/handlers.py`) is a drifted copy of
  pipeline-core's `_ViewsDataset` (this repo's **C-37/D-11** duplication, the same
  family as pipeline-core **C-36**). views-frames lets faoapi delete the fork and
  consume the shared contract.
- **The two leaf extractions split faoapi's two forks cleanly:** its *data-handler*
  fork → `views-frames`; its *Appwrite-client* fork → `views-appwrite`. Neither is a
  blocker for the other.
- **faoapi is the existence proof for the hardest open question in the design.**
  It performs cm↔pgm-style cross-level aggregation (`pg`→`country`/`gaul`) **without**
  computing a country↔grid join in code — it consumes a file where the producer (the
  `un_fao` postprocessor's mapper) has already **materialised** the
  `priogrid→country/gaul` mapping as 9 metadata columns. That is exactly the
  resolution `views-frames` needs for its cross-level / domain-data boundary (see
  `critiqus/critique_03.md` F-02): **the hierarchy mapping is producer-materialised
  metadata, not a leaf operation.**

---

## 1. Who `views-faoapi` is (so the contract serves the right consumer)

Per its own governance (ADR-001 ontology; ADR-005 testing-as-critical-infrastructure;
ADR-017 reference-data-in-repo; ADR-021 dense-grid fill — which *explicitly mirrors*
views-datafactory's convention), `views-faoapi` is the **decision-support delivery**
layer of VIEWS:

- Its job **starts** when a prediction/historical parquet lands in the Appwrite
  `unfao_bucket` and **ends** when a JSON response is on the wire to a UN FAO
  consumer (an analyst, a dashboard, the `FaoApiClient`). It does not train, does not
  forecast, does not reconcile.
- It owns the **serving lifecycle** — `FAOApiManager` (`managers/api.py`) wires a
  3-tier cache (in-memory → filelocked disk pickle → Appwrite download), a
  multi-format parse cascade, ~30 HTTP routes across five geographic levels, and the
  array→JSON edge.
- It owns **server-side posterior analysis** — `PosteriorDistributionAnalyzer`
  (`data/statistics.py`) computes empirical MAP + HDI from the prediction sample
  arrays; `FAO_PGMDataset.calculate_hdi_map` (`data/handlers.py`) drives it per cell
  and per aggregated geographic unit.
- It owns a **fork of the data contract it should be importing**: `_ViewsDataset` →
  `_PGDataset` → `FAO_PGMDataset` (`data/handlers.py`) is the same tensor-backed
  `(time × entity × sample × feature)` handler as pipeline-core's, re-derived with
  FAO-specific geo-metadata and aggregation. This is exactly the coupling
  `views-frames` is meant to end.

`views-frames` matters to this repo because faoapi today **re-implements the
universe's data type instead of importing it** — and that fork has already *drifted*
(faoapi's accepts both `priogrid_gid` and `priogrid_id`, carries 9 metadata columns,
collapses samples its own way). It is the most concrete cost of the missing leaf.

---

## 2. The relationship in one line

```
views-frames (leaf, numpy, stable, abstract)
        ▲
        │  faoapi depends toward it — and DELETES a fork to do so
        │  (its _ViewsDataset/FAO_PGMDataset handler → consume the shared frame+index)
        │  faoapi imports from views-frames; views-frames imports nothing from faoapi, ever.
        │
views-faoapi (delivery/serving; Appwrite → MAP/HDI + aggregation → JSON to UN FAO)
```

faoapi is the **only consumer that serves an external organisation over the wire**,
so it is where the array→interchange boundary (README §7) is most load-bearing — and
where the list-in-cell `object`-dtype blow-up that motivates the package actually
reaches a production response (`dataframe_to_dict` over sample arrays;
`/data/historical/latest` is ~1.7 GB as JSON, ~5.6 M rows).

---

## 3. What `views-faoapi` consumes, frame by frame

### 3.1 `PredictionFrame` — the forecast samples it serves
The forecast file is a `PredictionFrame` in all but name: `pred_ln_sb_best` /
`pred_ln_ns_best` / `pred_ln_os_best` columns, each cell an `np.ndarray` of `S`
posterior draws, indexed `(month_id, priogrid_id)`. faoapi loads it, wraps it in
`FAO_PGMDataset` (which converts every target column to a `float32` sample array —
the same `(N, S)` semantics PF guarantees), and serves subsets / HDI-MAP. **With
`views-frames`:** the loaded file *is* a `PredictionFrame`; faoapi's tensor reshape
and `calculate_hdi_map` consume `frame.values` + `frame.index` instead of a
re-derived `_ViewsDataset`. faoapi is a **consumer of record for the `Sampled`
protocol** — it is the live use-case for `collapse` + a quantile/HDI reduction (§8).

### 3.2 `TargetFrame` / `ActualsFrame` — the historical observations it serves
The historical file is structurally a `TargetFrame` (`S=1`): `lr_ged_sb` /
`lr_ged_ns` / `lr_ged_os` scalar observed-conflict columns over the same
`(month_id, priogrid_id)` grid. faoapi serves it through the *same* endpoints
(`/data/historical/...`) and the *same* `FAO_PGMDataset` machinery as the forecast —
which is the README's point that `TargetFrame` is `PredictionFrame` with `S=1`. faoapi
is the consumer that proves the two must share one contract: it serves both through
one code path. (Note: this is the file at the centre of the live
`viewser→views-datafactory` migration — its provenance is changing under faoapi.)

### 3.3 `SpatioTemporalIndex` — faoapi re-derives it by hand, everywhere
faoapi has its own `(month_id, priogrid_id)` index logic: `_rebuild_index_mappings`,
`_get_time_index`/`_get_entity_index` (`searchsorted`-style positional lookup),
`get_subset_tensor`/`get_subset_dataframe`, and a dense-grid `_preprocess_dataframe`
(zero-fill, ADR-021). This is the *same* "align an array on `(time, unit)`" primitive
`SpatioTemporalIndex` centralises — re-implemented a third time. faoapi should
*consume* the index, not re-derive it.

### 3.4 `SpatialLevel` — faoapi owns a fourth copy of the cm/pgm vocabulary
faoapi hardcodes the level vocabulary in two places: the `priogrid_gid→priogrid_id`
rename shim (`data/handlers.py:91-98`, again at `:1181,:1191`; this repo's **C-61**)
and the geographic-level dispatch (`self.levels = {"country": "country_iso_a3",
"gaul0": ..., "gaul1": ..., "gaul2": ...}`). `SpatialLevel` owning the canonical
index/entity names — *with the C-65 tuple order fixed and the gid/id inconsistency
resolved* (critique_03 F-03) — lets faoapi drop the shim and the string table.

### 3.5 What faoapi does **not** consume: `MetricFrame`
faoapi computes its *own* MAP/HDI for *presentation* and does not consume evaluation
scores — so it has no need for `MetricFrame`, and it is a data point for keeping
`MetricFrame` out of the leaf (critique_03 P5): the platform's most external
consumer never wants it.

---

## 4. The concrete pains `views-frames` untangles (with what it *does* and *does not* fix)

> Register IDs are **views-faoapi's** own register unless noted.

| Pain (this repo) | Where | What `views-frames` does |
|---|---|---|
| **Forked `_ViewsDataset`/`FAO_PGMDataset` (~1,550 LOC), drifted from pipeline-core's** | `data/handlers.py` (this repo's C-37/D-11 family; pipeline-core C-36) | **Repays.** faoapi deletes the fork and consumes the shared `PredictionFrame`/`TargetFrame` + `SpatioTemporalIndex`; `FAO_PGMDataset` shrinks to a thin FAO-specific adapter (geo-metadata join + HDI/MAP) over the leaf. |
| **`priogrid_gid` shim + acceptance, duplicated** | `data/handlers.py:91-98,1181,1191`; `managers/api.py:587` (C-61–C-65) | **Owns the boundary once.** `SpatialLevel` + the index carry the entity-column vocabulary; faoapi stops re-implementing the rename. |
| **list-in-cell / object-dtype on the wire** | `managers/api.py` `dataframe_to_dict`, `flatten_numeric_list_columns`; ~1.7 GB JSON historical | **Solves the representation.** Dense `float32` frame + the flat-columnar `io/arrow` format; faoapi's array→JSON is a thin *edge adapter* over a dense frame, not a round-trip through object-dtype DataFrames. |
| **cross-level aggregation re-implemented** | `_aggregate_distributions`, `_elementwise_sum`, `_get_pg_cells` (`data/handlers.py`); C-70 (joint-sampling assumption) | **Partly.** The `Sampled` protocol gives a typed collapse/aggregate; **but** the `pg→country/gaul` *mapping* stays producer-materialised metadata (see §8.3). The leaf gives the operation a typed payload, not the geography. |
| **Appwrite-client fork (~2,020 LOC)** | `managers/appwrite.py`, `managers/prediction.py` (C-37, C-51 resolved, D-11) | **NOT `views-frames`.** This is **`views-appwrite`'s** job. The boundary is clean: data-handler dup → views-frames; storage-client dup → views-appwrite. |
| **No typed provenance → stale data served silently** | `managers/api.py` staleness check (C-50); newest-by-`$createdAt` with no gate (C-71) | **Enables.** A stamped run/production identity in frame `metadata` (README §13.5) is what lets faoapi detect staleness and refuse a regressed file — frames give it a home, they do not auto-resolve the promotion gate. |

**The honest line:** `views-faoapi` is the **loosest-coupled** consumer (separate
repo, separate deploy, external-facing) and currently a *fork rather than a
consumer* — so views-frames *repays* a large duplication here but its **adoption is a
late strangler step**, not an early one. faoapi gains the most from the leaf
existing; it should be among the last to migrate onto it, because re-unifying a
drifted fork that serves a live UN-facing product must not change the served numbers.

---

## 5. What stays in `views-faoapi` (explicitly NOT `views-frames`)

Per README §11 and SRP/CRP, the leaf takes the *contract*; this repo keeps
everything delivery-shaped:

- **HTTP serving & the API** — FastAPI app, the ~30 routes, per-API-key
  multi-tenant caching, auth, the array→JSON edge (`dataframe_to_dict`,
  `convert_numpy_types`). The leaf has no concept of a request.
- **Server-side MAP/HDI summarisation** — `PosteriorDistributionAnalyzer` and
  `calculate_hdi_map`. Like reporting's MAP/HDI, deriving *display* summaries from a
  `PredictionFrame` is presentation work and stays here (distinct from *scoring*,
  which is views-evaluation's).
- **The format/parse cascade + the disk cache** — Appwrite download, parquet/feather
  parsing, the 3-tier cache. Acquisition/persistence adapters, not the contract.
- **Geographic metadata enrichment** — the 9 `_METADATA_COLS` arrive *pre-joined* in
  the file (produced upstream by the `un_fao` postprocessor's mapper). faoapi reads
  them; it does not compute the geography. The leaf never fetches or joins geography.
- **The Appwrite client** — stays, but migrates to **`views-appwrite`**, not here and
  not the frames leaf.

---

## 6. How `views-faoapi`'s existing patterns already point at frames

- **`FAO_PGMDataset` is already "array + identifiers + validation"** — it converts
  targets to `float32` sample arrays, validates a 2-level `(month_id, priogrid_id)`
  MultiIndex at construction, and fails loud on missing metadata columns. That is the
  frame contract, re-derived; relocating onto the leaf is continuity, not invention.
- **The `metadata` sidecar pattern already exists** — faoapi splits the 9
  `_METADATA_COLS` into a `geo_metadata` frame aligned to the data index. That is
  precisely "frame + a metadata header aligned by the same index" the leaf formalises
  — and the template for materialised cross-level mapping (§8.3).
- **`PredictionStoreManager`'s `OperationResult`/loader shape** is already
  "an injected adapter that yields a typed payload" — the adapter-produces-a-frame
  pattern the leaf expects.
- **ADR-021 already couples faoapi to the platform contract** — its dense-grid
  zero-fill is documented as *mirroring* views-datafactory. faoapi has already
  accepted that grid semantics are a shared, upstream-owned contract; the frame is
  the next step of that same acceptance.

---

## 7. Migration implications for `views-faoapi` (Strangler, aligned with README §10)

faoapi's migration is a **late** strangler step and is gated on the leaf being
stable; each step is shippable behind a shim and behavior-preserving:

1. **Consume the leaf's `PredictionFrame`/`TargetFrame`** at the load boundary
   (`_get_latest_dataframe` → construct a frame), keeping `FAO_PGMDataset` as a thin
   adapter that wraps the frame + the `geo_metadata` join. No served-output change.
2. **Relocate the index logic** — replace `_rebuild_index_mappings`/`_get_*_index`
   and the `priogrid_gid` shim with the leaf's `SpatioTemporalIndex` + `SpatialLevel`
   (after C-65/gid-id are fixed in the relocation, F-03).
3. **Adopt the dense flat-columnar `io/arrow`** for the internal path and make the
   JSON response a thin edge adapter over a dense frame — retiring the list-in-cell
   round-trip on the historical/forecast hot path.
4. **Decompose the `FAO_PGMDataset` fork** *behind* the leaf protocols once steps 1–2
   land — never before (the same C-135-style trap pipeline-core flags).
5. **Carry production provenance in frame `metadata`** so the staleness/promotion
   logic (C-50, C-71) keys off a stamped identity, not `$createdAt`.

> Sequencing: faoapi's adoption **overlaps the `views-appwrite` extraction** (both
> touch its storage edge) and follows the live `viewser→datafactory` data migration.
> Do not run all three in faoapi at once — the data migration changes *values* and
> needs an attributable diff; the two fork-retirements are contract-preserving and
> can follow it. (See `critiqus/critique_01.md` §6 — the platform WIP question.)

---

## 8. What `views-faoapi` needs the contract to guarantee (asks / open questions)

1. **The `Sampled` protocol must expose HDI/quantile reduction, not just
   `collapse(mean)`.** faoapi computes empirical 90% HDI + MAP per cell and per
   aggregated unit (`PosteriorDistributionAnalyzer`); a mean-only collapse is
   insufficient. This is the same ask as pipeline-core #1, from a second consumer of
   record — which should promote it from "confirm" to "required."
2. **`TargetFrame` (`S=1`) and `PredictionFrame` must serve through one interface.**
   faoapi serves historical and forecast through identical endpoints; the role
   (`S=1` ground truth vs `S≥1` samples) must be explicit but the *surface* shared,
   or faoapi keeps two code paths.
3. **Cross-level mapping stays producer-materialised metadata — please make this the
   documented pattern.** faoapi resolves `pg→country/gaul` by reading 9
   pre-joined metadata columns, *not* by joining geography at serve time. This is the
   working answer to the leaf's hardest open question (critique_03 F-02): the
   `priogrid→country/gaul` (and the cm↔pgm) mapping is **producer-side reference data
   materialised into the frame's metadata**, never a leaf operation. The README
   should state this boundary explicitly and cite faoapi as the existence proof.
4. **Sample-axis alignment must be preserved across an aggregate.** faoapi's
   `_elementwise_sum` sums sample *i* across constituent cells (joint-sampling, this
   repo's C-70). If the leaf offers any cross-row reduction, the `Sampled` contract
   must guarantee sample-index alignment, or the aggregated uncertainty is wrong.
5. **A frame→records/JSON edge adapter belongs in the consumer.** Confirm (README
   §7/§11) that the array stays authoritative and the JSON serialisation faoapi
   serves to UN FAO is an *edge adapter* depending on `views-frames`, never the
   transport — so faoapi can keep `convert_numpy_types`/`dataframe_to_dict` as a thin
   boundary over a dense frame.
6. **Provenance/run-identity in `metadata` (README §13.5)** is, from this repo, a
   delivery-safety requirement: faoapi serves to an external humanitarian consumer
   with no promotion gate (C-71); a stamped production identity is what lets it
   detect a regressed/stale file before it reaches UN FAO.

---

## 9. The "third twin" posture (unique to this perspective)

This section is unique to faoapi. The README's central motivating defect is
"diverging *twins*" (FeatureFrame ≠ PredictionFrame). `views-faoapi` is the evidence
that the divergence is **not a pair but a family**: it independently re-implemented
`_ViewsDataset`/`PGMDataset` (and the Appwrite layer) in a *separate repo with a
separate deploy cadence*, and the copy has **already drifted** — it accepts
`priogrid_gid`, carries FAO geo-metadata, and collapses samples its own way.

Two implications for the leaf's design:

- **The REP/de-duplication argument is stronger than stated.** A contract two repos
  re-implement is a risk; a contract *three+* repos re-implement, one of them serving
  the UN, is the strongest possible case for a single stable leaf.
- **The unification framing should not assume "two."** §4.1/§10 plan to unify two
  twins; faoapi is a third concrete implementation with its own deltas. The contract
  must be defined from the *union* of real implementations (incl. faoapi's
  `float32`-sample conversion, dense-grid fill, and metadata sidecar), not from the
  two the README happens to name — or faoapi will be a fourth shim, not a clean
  consumer. This reinforces critique_03 P1 (the twins are not near-1:1) by adding a
  third data point that diverges further still.

The cautionary half: because faoapi's fork is **load-bearing for a live UN-facing
product**, its re-unification is the one migration where "behavior-preserving" is
non-negotiable down to the served numbers. faoapi is the best argument *for* the
leaf and the strictest constraint *on* how it is adopted.

---

## 10. Cross-references

- `views-frames` README: §1 (problems — the diverging-twins bullet, which faoapi
  extends to triplets), §2 (DAG position), §3 (hard constraints — esp. no-domain /
  no-pandas), §4 (frame family — §4.1 PredictionFrame/TargetFrame, §4.3
  `SpatioTemporalIndex`), §5 (protocols — esp. `Sampled`), §7 (serialization — the
  array→JSON edge faoapi lives on), §10 (migration — faoapi is a late step), §11
  (scope — Appwrite/JSON adapters stay here), §13 (open decisions — esp. §13.5
  provenance, §13.6 sample axis).
- `views-frames` critiques: `critiqus/critique_03.md` (the falsification pass —
  F-02 cross-level/domain data, which faoapi's materialised-metadata pattern
  resolves; P1 twins-not-near-1:1, which faoapi's third fork reinforces).
- `views-faoapi` governance: ADR-021 (dense-grid fill, mirrors datafactory),
  ADR-017 (reference data in repo), ADR-005 (testing as critical infrastructure);
  CICs `FAO_PGMDataset.md`, `_ViewsDataset.md`, `PosteriorDistributionAnalyzer.md`,
  `FAOApiManager.md`.
- `views-faoapi` register: C-37 / C-51 (resolved) / D-11 (the Appwrite + prediction
  duplication → views-appwrite), C-61–C-65 (priogrid rename boundary), C-70/C-71/C-72
  (upstream-data trust boundary — provenance, value validation), C-73 (decision-support
  output contract), C-50 (staleness).
- Companion perspectives: `from_views-pipeline-core_perspective.md` (the data-handler
  this repo forked), `from_views-datafactory_perspective.md` (the new historical
  source under faoapi's live migration), `from_views-reporting_perspective.md` (the
  other downstream presentation consumer — same MAP/HDI split).
