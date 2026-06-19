# `views-frames` from the `views-reporting` perspective

> A consumer's-eye view of why `views-frames` exists, what `views-reporting` will
> depend on it for, and — just as importantly — what it will **not**. Written from
> the downstream **presentation/synthesis** layer looking *toward* the leaf.
>
> Companion to the `views-frames` README (the design bible). Where this document
> and the README disagree, the README wins on the contract; this document wins on
> "what the reporting consumer actually needs." Reconcile before building.

---

## 0. TL;DR for a hurried reader

- `views-reporting` is a **downstream consumer** of `views-frames`. It depends
  *toward* the leaf and **renders frames into human-facing artifacts** (HTML
  reports, choropleth maps, posterior/HDI plots). It owns *adapters and rendering*
  — **not** the data contract.
- It will consume four things from `views-frames`: **`PredictionFrame`** (model
  outputs), **`TargetFrame`** (observed actuals), **`MetricFrame`/`ScoreFrame`**
  (evaluation outputs), and the two value objects **`SpatioTemporalIndex`** +
  **`SpatialLevel`** (alignment + cm/pgm vocabulary).
- `views-frames` is the keystone that lets `views-reporting` stop three things it
  does wrong today: **scraping evaluation metrics out of WandB** (its confirmed
  bug **C-48**), **mutating a pipeline-core object across the repo boundary**
  (**C-184**), and **reaching into private dataset internals** (`_time_id`,
  `_entity_id`, `.dataframe`, `.to_tensor`; **C-135/C-36**). It also breaks the
  `views-pipeline-core ↔ views-reporting` import cycle (**reporting issue #113**).
- **Naming, already settled:** `EvaluationFrame` (aligned pred×actual *input*)
  lives in **views-evaluation** — do not rebuild it. The thing `views-reporting`
  *renders* is the metric **output**, `MetricFrame`/`ScoreFrame`, owned here.

---

## 1. Who `views-reporting` is (so the contract serves the right consumer)

Per its own governance (ADR-001 "outer-layer presentation and analysis package";
ADR-002 "depend on pipeline-core **containers**, not services"; README "receives
evaluated predictions… produces HTML reports"), `views-reporting` is the
**render-from-given-data** layer of VIEWS:

- Its job **starts** when it is handed data and **ends** when it emits a rendered
  artifact for a human (a stakeholder, a partner like UN FAO, a model developer
  who wants a shareable page rather than a live dashboard).
- It is **orthogonal to WandB by design**: WandB is the developer's live
  experiment tracker; `views-reporting` is the frozen, shareable, offline
  evaluation/forecast *report*. (That these two surfaces both show eval numbers is
  not redundancy — it is a lab-notebook-vs-published-scorecard distinction.)
- It is *not* an evaluator and *not* a data producer. Scoring lives in
  `views-evaluation`; predictions come from the model repos; metadata comes from
  the data factory / viewser. `views-reporting` **presents** what those produce.

`views-frames` matters to this repo precisely because today the rendering layer is
*entangled* with acquisition (it fetches from WandB and viewser at render time) and
with pipeline-core internals (it reads private members and mutates foreign
objects). A typed, immutable, leaf-level data contract is what lets the rendering
layer go back to *just rendering what it is given*.

---

## 2. The relationship in one line

```
views-frames (leaf, numpy, stable, abstract)
        ▲
        │  depends toward (consumes frames + index + level)
        │
views-reporting (presentation/synthesis; renders frames → HTML / maps / plots)
```

`views-reporting` **imports from `views-frames`; `views-frames` imports nothing
from `views-reporting`, ever.** That single rule is what dissolves the current
import cycle (§4, #113).

---

## 3. What `views-reporting` consumes, frame by frame

### 3.1 `PredictionFrame` — model outputs (ŷ samples)
This is the data the whole forecast report is built on. Today `views-reporting`
ingests it through its **declared-format loader registry** (ADR-012):
`loaders/__init__.py:8-9` registers `dataframe` and `prediction_frame` loaders;
`loaders/prediction_frame_loader.py:9-11` imports `PredictionFrame` +
`PredictionFrameConverter` from pipeline-core, `:35` calls `PredictionFrame.load()`,
`:36` converts via `to_prediction_df()`, and `:41` wraps the result in a
`CMDataset`/`PGMDataset`. Everything downstream — MAP/HDI (`statistics/`),
choropleths (`mapping/`), historical-vs-forecast line graphs
(`visualizations/historical.py`) — is computed **from** these prediction samples.

**With `views-frames`:** `PredictionFrame` becomes the leaf-owned container the
loaders materialize (initially via the pipeline-core re-export shim per
views-frames §10, then directly). The loader registry is exactly the
"adapter-produces-a-frame" pattern `views-frames` expects — it stays here as a
consumer adapter; the *type* it yields is owned there.

### 3.2 `TargetFrame` / `ActualsFrame` — observed actuals
The historical/observed series that the forecast line graphs draw alongside the
predictions (today loaded as `calibration_viewser_df.parquet` and read via
`read_dataframe`, then wrapped in a dataset). This is structurally a
`PredictionFrame` with `S=1`. `views-reporting` consumes it to render
"historical vs forecast" and to anchor the forecast-launch / hindcast cutoff.

> Open naming question relevant here: `views-frames` §13.2 — `TargetFrame` vs
> `ActualsFrame`. From the reporting side the language is "observed actuals /
> historical"; either name is fine so long as the role (ground truth, `S=1`) is
> explicit in the contract.

### 3.3 `MetricFrame` / `ScoreFrame` — evaluation outputs (the headline)
**This is the type that fixes the worst thing `views-reporting` does.** The
evaluation report's "Model Metrics" tables need each model's scores
(MSLE/MSE/MCR_point; CRPS/Ignorance/MIS for samples — the ADR-017 canonical set).
Today it obtains them by **scraping WandB**: `templates/reports/evaluation.py:69`
calls `format_evaluation_dict(dict(wandb_run.summary))` and `:187-189` calls
`get_latest_run(...)` per constituent, then `:298-305` string-matches metric
tokens. That is the C-48 path (see §4).

**With `views-frames`:** the evaluation *outputs* become a first-class
`MetricFrame` — keyed by `(target, step, unit)`, carrying the canonical metric set
and provenance. `views-evaluation` **produces** it; `views-reporting` **renders**
it. The report stops scraping a mutable cloud mirror and starts consuming a typed,
addressable, versioned artifact. `views-reporting` is the **consumer of record**
for `MetricFrame` — the concrete downstream that motivates promoting it from
"exploratory" to real.

### 3.4 `SpatioTemporalIndex` — the alignment primitive
`views-reporting` re-implements (time, unit) alignment by hand, all over:
- `statistics/dataset_statistics.py:140-141` builds `pd.MultiIndex.from_product([
  time_steps, entities], names=[dataset._time_id, dataset._entity_id])`; `:101,108`
  pull axes via `.index.get_level_values(...)`.
- `mapping/mapping.py:452-457` pivots by location × time and reindexes to all
  locations; `:413-414` subsets by `(time_ids, entity_ids)`.
- `reconciliation/` checks `set(c._time_values) ^ set(pg._time_values)` for time
  coverage (`reconciliation.py:88`) and builds country↔grid maps by loop.

All of that is the *same* "align arrays on (time, unit)" logic, duplicated and
divergent — exactly what `SpatioTemporalIndex` centralizes (its `intersect`,
`align`/`reindex`, `searchsorted` joins). `views-reporting` should *consume* the
index, not keep re-deriving it. The cm↔pgm (country↔grid) join the reconciler
needs is a cross-`SpatialLevel` alignment — see §8.

### 3.5 `SpatialLevel` — the cm/pgm vocabulary
The `"cm"`/`"pgm"` strings and their per-level index/entity names are scattered:
`loaders/_constants.py:5` (`DATASET_CLASSES = {"cm": CMDataset, "pgm": PGMDataset}`),
`:7-10` (`INDEX_NAMES = {"cm": ["month_id","country_id"], "pgm": [...]}`), plus
`isinstance(_CDataset/_PGDataset)` dispatch in the reconciler and private
`_entity_id`/`_time_id` reads in `mapping/mapping.py:78-79`. `SpatialLevel` is the
single value object that defines `index_names`/`entity_column` (cm→`country_id`,
pgm→`priogrid_id`). `views-reporting` should ask the index for
`index.level.entity_column` instead of carrying string tables and reading private
members.

---

## 4. The concrete pains `views-frames` untangles (with what it *does* and *does not* fix)

> Register IDs: `C-22/C-27/C-44/C-46/C-48` are **views-reporting's** own register;
> `C-36/C-40/C-66/C-135/C-184` are **views-pipeline-core's** register (they
> describe behaviours that cross into reporting); `#113` is a views-reporting issue.

| Pain (this repo) | Where | What `views-frames` does |
|---|---|---|
| **C-48 — eval report reads the WandB cloud replica, not the authoritative output** | `evaluation.py:69,187-189,298-305` | **Enables the fix.** `MetricFrame` is the typed eval *output* the report consumes instead of scraping `get_latest_run`. Confirmed failure: `get_latest_run` returns the latest-*created* run, which for heavily re-run models lacks the metrics → **22/25 constituents rendered "not calculated"** while the real scores sat in an earlier run. A `MetricFrame` (with a stable identity in its metadata) makes the report consume *the* evaluation, not "whatever the tracker surfaced last." Note: the run-identity / where-it-is-stored decision is **still cross-repo** — frames give it a home, they don't auto-resolve it. |
| **C-184 — cross-repo mutation of a core object** | `reconciliation/dataset_export.py:103` (`pg_dataset.reconciled_dataframe = pg_dataset.dataframe.copy()`), `:122` (`.loc[(time_id, entity_id), feature] = new_samples`) | **Forbidden by construction.** Frames are immutable value objects (views-frames §3.3); operations return *new* frames. Reconciliation must produce a new frame, not reach across the boundary and write into a pipeline-core dataset. |
| **C-135 / C-36 — private-internal reads of a god-class dataset** | `_time_id`/`_entity_id`/`_time_values`/`_entity_values`/`.dataframe`/`.to_tensor`/`_country_to_grids_cache` across `statistics/`, `mapping/`, `reconciliation/`, `metadata/` | **Replaced by published protocols.** `views-reporting` types against `Frame` / `SpatioTemporalIndexed` / `SpatialLevel` instead of poking `_ViewsDataset` internals. |
| **#113 — pipeline-core ↔ reporting import cycle** | one direction declared, the other behind `try/except ImportError` | **Broken.** Both repos route their data contract through the `views-frames` leaf; the cycle cannot form (ADP). |
| **C-44 — undeclared wandb/viewser imports** | `evaluation.py:8`, `metadata/entity_metadata.py:10`, `reconciliation/reconciliation.py:10` | **Enables isolation.** Once metrics arrive as a `MetricFrame`, WandB collapses to (at most) one consumer-side acquisition adapter; the reporting core declares numpy/frames, not wandb. |
| **C-22 — viewser runtime fetch for entity metadata** | `metadata/entity_metadata.py:45-75,335-370` (`Queryset(...).publish().fetch()`) | **Shrinks, does not solve.** `SpatialLevel` owns the cm/pgm vocabulary and the index, reducing the metadata surface; but the static geographic lookup (lat/lon/isoab/name) remains a **consumer-side adapter** — `views-frames` never fetches viewser (its §3 forbids it). |

**The honest line:** `views-frames` *solves* the structural sins (mutation,
private leakage, the cycle) outright, and *enables* the integration fixes (C-48,
C-44, C-22) by giving the data a typed home — but those still need a cross-repo
decision about where evaluation outputs are stored and how a run is identified.

---

## 5. What stays in `views-reporting` (explicitly NOT `views-frames`)

Per `views-frames` §11 and SRP/CRP, the leaf takes the *contract*; this repo keeps
everything application-shaped:

- **Rendering & synthesis** — the HTML/Tailwind report builder, choropleth maps
  (geopandas/plotly), distribution & line-graph plots, the report templates, and
  the "package it for a stakeholder" composition. This *is* `views-reporting`'s
  reason to exist.
- **Acquisition adapters** — the declared-format loaders (adapter → frame); the
  WandB/store adapter that yields a `MetricFrame`; the viewser/static-lookup
  metadata adapter; the **pandas/geopandas edge conversion** for shapefile joins
  (the array is authoritative inside; pandas is a thin edge, never the transport).
- **Reconciliation math** — the proportional country↔grid scaling. Frames give it
  a typed payload, but the algorithm (and its open relocation question, pipeline-core
  Cluster B / C-24 "should reconciliation even live in a reporting repo") stays out
  of the leaf.
- **Posterior summarization (MAP/HDI)** — deriving display summaries *from* a
  `PredictionFrame` is presentation work and stays here. This is distinct from
  **scoring** (CRPS/MSLE vs actuals), which is `views-evaluation`'s job and reaches
  this repo as a `MetricFrame`.

---

## 6. How `views-reporting`'s existing patterns already point at frames

- The **loader registry** (`loaders/_protocol.py` + `_registry.py` + per-format
  loaders, ADR-012) is *already* "an injected adapter that produces a typed
  container." Extending it to yield `views-frames` frames is continuity, not a
  rewrite.
- `ForecastReportTemplate.generate(forecast_dataframe=…, prediction_path=…)`
  (`forecast.py:33`) **already receives its data** — it is the DIP-clean template.
- `EvaluationReportTemplate` (`evaluation.py`) is the lone violator: it *fetches*
  (get_latest_run) instead of *receiving*. The component-principle resolution is to
  make it receive a `MetricFrame` like the forecast template receives its data —
  depend on the `views-frames` contract, inject the source as an adapter.

---

## 7. Migration implications for `views-reporting` (Strangler, aligned with views-frames §10)

Each step is independently shippable and back-compatible via shims:

1. When `views-frames` owns `PredictionFrame` (pipeline-core re-exports a shim),
   `views-reporting`'s `PredictionFrameLoader` keeps working untouched; later
   re-point its import to `views_frames.PredictionFrame`.
2. Add a **`MetricFrame`-consuming evaluation path** (an injected
   `evaluation source` adapter returning a `MetricFrame`) and **retire
   `get_latest_run` from the template** → closes C-48 from the consumer side. WandB
   becomes one adapter (or is dropped).
3. Make **reconciliation return a new frame** instead of writing
   `pg_dataset.reconciled_dataframe` → closes C-184.
4. Replace private `_entity_id`/`_time_id`/`.dataframe`/`.to_tensor` reads with the
   published `index` / `SpatialLevel` / frame accessors → closes the reporting side
   of C-135.
5. Replace `DATASET_CLASSES`/`INDEX_NAMES` string tables and
   `isinstance(_CDataset/_PGDataset)` dispatch with `SpatialLevel`.

---

## 8. What `views-reporting` needs the contract to guarantee (asks / open questions)

These are the things this consumer would raise on the `views-frames` design:

1. **`MetricFrame` schema** — keyed by `(target, step, unit)`; carries the ADR-017
   canonical metric set; and **carries provenance in metadata** (model, run_type,
   evaluation window, data-version, scoring-code revision). This last point ties
   directly to `views-frames` §13.5 and is, from this repo's view, **the single
   highest-value open decision**: a stamped, stable run/eval identity in frame
   metadata is exactly what lets the report select *the* evaluation rather than
   "the most recent run" — i.e. the consumer-side cure for C-48 (and the
   reporting register's C-34 "reports carry no provenance").
2. **cm↔pgm alignment in `SpatioTemporalIndex`** — the reconciler joins
   country-level totals to grid-level cells; the index must support cross-
   `SpatialLevel` alignment (country → its priogrid cells), not just same-level
   intersection.
3. **`TargetFrame` vs `ActualsFrame` naming + `S=1` convention** (§13.2 / §13.6) —
   the report renders "observed actuals" with a single realized value; the role
   must be explicit so the line-graph code can treat it distinctly from samples.
4. **A consumer-side `to_pandas()` / geopandas edge** — `views-frames` keeps pandas
   out of the core (§7/§11), and rendering genuinely needs pandas/geopandas at the
   very end (shapefile joins in `mapping/`). Confirm that this conversion is a
   *consumer* adapter that depends on `views-frames`, so the array stays
   authoritative and pandas stays an edge.

---

## 9. Naming clarification (so this repo never reintroduces the confusion)

| Type | Owner | Meaning | Relation to `views-reporting` |
|---|---|---|---|
| `EvaluationFrame` | **views-evaluation** (exists) | aligned pred × actual × (origin, step) — the scoring **input** | not consumed here; do **not** rebuild it |
| `MetricFrame` / `ScoreFrame` | **views-frames** (this contract) | the computed metrics — the scoring **output** | **this is what the eval report renders** |
| `PredictionFrame` / `TargetFrame` | **views-frames** | model outputs / observed actuals | consumed by loaders + all rendering |
| `SpatioTemporalIndex` / `SpatialLevel` | **views-frames** | (time, unit) alignment + cm/pgm vocabulary | replaces hand-rolled index logic + bare strings |

There is no `EvaluationResults` type — an earlier reporting-side sketch used that
name; it is superseded by the views-frames `MetricFrame`.

---

## 10. Cross-references

- `views-frames` README: §1 (problems), §2 (DAG position), §3 (hard constraints),
  §4 (frame family — esp. §4.2 `MetricFrame`, §4.3 `SpatioTemporalIndex`), §5
  (protocols), §7 (serialization), §10 (migration), §11 (scope boundaries — what
  is NOT here), §12 (risk register), §13 (open decisions — esp. §13.5 provenance).
- `views-reporting` governance: ADR-001 (ontology), ADR-002 (topology / depend on
  containers not services), ADR-012 (declared-format ingestion), ADR-017 (canonical
  evaluation-report metrics).
- `views-reporting` register: C-22 (viewser), C-24 (torch/reconciliation
  placement), C-27 (WandB runtime dep), C-44 (undeclared deps), C-48 (cloud metric
  replica — the headline), and the cross-repo C-135/C-184/#113.
- `views-evaluation`: `views_evaluation/evaluation/evaluation_frame.py`
  (`EvaluationFrame` — the input artifact this repo does **not** rebuild).
