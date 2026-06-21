# `views-frames` from the `views-pipeline-core` perspective

> The **origin/orchestration** repo's view of `views-frames`. Unlike the
> presentation layer, `views-pipeline-core` is *not* a pure downstream consumer —
> it is the repo that **owns these types today** (`PredictionFrame`, the
> `_ViewsDataset` family, `PredictionFrameConverter`) and **hands the contract off**
> to the leaf. It is at once a *producer* (it runs the models that emit frames), a
> *transport owner* (it persists, aggregates, and reports on them), and the place
> where most of the migration work — and most of the debt `views-frames` repays —
> actually lives.
>
> Companion to the `views-frames` README (the design bible). Where they disagree,
> the README wins on the contract; this document wins on "what the orchestration
> repo actually does today and what it must give up / keep." Reconcile before building.

---

## 0. TL;DR for a hurried reader

- `views-pipeline-core` is the **orchestration layer**: it fetches data, runs
  train/eval/forecast/report, and moves the **prediction containers** between
  stages, repos, and the forecasts store. Today it is *also* the de-facto home of
  the data contract — `PredictionFrame` lives here, and `_ViewsDataset` is the
  pandas↔tensor workhorse every consumer reaches into.
- It will **give `views-frames` three things it currently owns**: `PredictionFrame`
  (relocate, re-export a shim), the `SpatioTemporalIndex` + `SpatialLevel`
  vocabulary (today `domain/spatial.py` + ad-hoc index logic), and the *role* of
  "typed transport" that `_ViewsDataset` accreted by accident.
- It will **keep** what is genuinely application-shaped: orchestration, viewser
  ingest, the savers, wandb, reconciliation math, and `_ViewsDataset` itself as a
  pandas↔tensor **adapter** — stripped of its cross-repo transport role.
- The marquee reason this matters now: **#181** — a HydraNet eval run is
  **OOM-killed in the report tail** because the path round-trips dense predictions
  through **object-dtype DataFrames** over the full grid×time (pipeline-core
  **C-186**, measured ~50–160× the dense cost). That is the Data-Contract Gap
  cluster firing in production. A dense, collapsed array frame is the fix. **§5.**
- `views-frames` is also what lets pipeline-core stop *being half* of the
  `views-pipeline-core ↔ views-reporting` import cycle (**#113**): once both repos
  route their data contract through the leaf, the cycle cannot form.

---

## 1. Who `views-pipeline-core` is (so the contract serves the right producer)

Per its own governance (ADR-001 ontology; ADR-002 topology; ADR-045 stage
extraction; ADR-042 the PredictionFrame/DataFrame two-track), `views-pipeline-core`
is the **orchestration + transport** layer of VIEWS:

- It owns the **run lifecycle** — `ModelManager`/`ForecastingModelManager`
  (`managers/model/model.py`) drives data-fetch → train → evaluate → forecast →
  report, each as an ADR-045 stage with a frozen context.
- It is where models' outputs **become containers**: the engine repos implement
  `_forecast_model_artifact()` / `_evaluate_model_artifact()` and hand back a
  `PredictionFrame` (`data/prediction_frame.py`) or a DataFrame; pipeline-core
  validates, persists (`managers/prediction/savers.py`), aggregates
  (`managers/ensemble/`), and reports on them (`managers/reporting/stage.py`).
- It owns the **data structures everyone else consumes**: `PredictionFrame`,
  `PredictionFrameConverter`, and the `_ViewsDataset`/`CMDataset`/`PGMDataset`
  family (`data/handlers.py`). views-reporting and views-postprocessing import
  these — which is exactly why the contract belongs in a neutral leaf, not here.

`views-frames` matters to this repo because pipeline-core today **conflates the
data contract with the orchestration code that happens to host it.** The contract
(what a "prediction aligned to (time, unit)" *is*) should be a stable leaf every
repo depends on; the orchestration (how it is fetched, run, persisted, reported)
should depend *on* that leaf. Splitting them is what lets pipeline-core go back to
*orchestrating*, not *defining the universe's data types*.

---

## 2. The relationship in one line

```
views-frames (leaf, numpy, stable, abstract)
        ▲
        │  pipeline-core depends toward it — AND donates the types it currently owns
        │  (PredictionFrame, SpatialLevel, the "typed transport" role)
        │
views-pipeline-core (orchestration / transport; runs models, persists & moves frames)
```

`views-pipeline-core` will **import from `views-frames`; `views-frames` imports
nothing from pipeline-core, ever.** Today that arrow runs the wrong way (the
contract lives *in* pipeline-core); the migration (§8) reverses it. That single
reversal is also half of what dissolves the reporting cycle (#113) — the other
half is the reporting side routing through the same leaf.

---

## 3. What pipeline-core hands off / consumes, frame by frame

### 3.1 `PredictionFrame` — pipeline-core OWNS it today (donate it)
`data/prediction_frame.py` is the current home: `y_pred (N, S)` float32,
`REQUIRED_IDENTIFIERS = {"time", "unit"}`, construction-time validation, `collapse`,
`save`/`load` (npz). It is produced by the engine repos, persisted by
`NpzSaver`/`LocalParquetSaver` (`managers/prediction/savers.py`), converted for
disk/ensemble by `PredictionFrameConverter`, and consumed downstream. **Migration:
relocate the class to `views-frames` and re-export a shim from
`data/prediction_frame.py`** (README §10.2) so every `from
views_pipeline_core.data.prediction_frame import PredictionFrame` keeps working.
This is the single highest-leverage move — `PredictionFrame` is the #1 coupling hub
in the codebase (graphify), so the leaf owning it is what makes its interface
evolvable (C-165/C-48).

### 3.2 `FeatureFrame` — pipeline-core should CONSUME it on ingest
Today ingest returns `pd.DataFrame` (`ViewsDataLoader`), and the unwired
`DataFetchStrategy` protocol (`types.py:95-122`, C-164) was designed for pluggable
sources but never given a typed payload. `FeatureFrame` (the array twin, in
views-datafactory today) is that payload: a `DataFetchStrategy.fetch()` that returns
a `FeatureFrame` is the OCP-clean version of `_detect_data_source()`'s if/elif chain.

### 3.3 `TargetFrame` / `ActualsFrame` — fixes pipeline-core's eval boundary
`modules/validation/adapter.py` (the `EvaluationAdapter`) still takes
`actual: pd.DataFrame, predictions: List[pd.DataFrame]` — the last place pandas is
*mandated* on the internal eval path. A `TargetFrame` (`PredictionFrame` with `S=1`)
makes the adapter array-native and is the **highest-value early migration win**
(README §10.4) — it deletes a pandas dependency from the evaluation hot path.

### 3.4 `MetricFrame` — pipeline-core PRODUCES it (via the evaluation stage)
Evaluation metrics are computed in `EvaluationStage` (via views-evaluation's
`NativeEvaluator`) and today scattered to `eval_*.parquet` + wandb with no typed
output container. pipeline-core is the **producer of record** for `MetricFrame`
(views-reporting is the consumer of record — its C-48). Giving the eval *output* a
typed home here is what lets the report stop scraping wandb (and is the upstream
half of the #178 provenance work — `get_run_by_timestamp`, `configuration.py:182`
timestamp).

### 3.5 `SpatioTemporalIndex` + `SpatialLevel` — pipeline-core owns the scattered originals
`SpatialLevel` lives in `domain/spatial.py` today (cm→`country_id`,
pgm→`priogrid_id`); the cm/pgm strings and per-level index logic are smeared across
`model.py:824` (`{"cm": CMDataset, "pgm": PGMDataset}`), the `_ViewsDataset`
subclass hierarchy, and `_prediction_to_tensor`'s `from_product` index build
(`handlers.py:451-454`). **Relocate `SpatialLevel` to `views-frames`** (README
§10.5) and consume `index.level.entity_column` instead of the bare strings and the
private `_entity_id` reads (C-135, C-38, D-33).

---

## 4. The concrete pains `views-frames` untangles (with what it *does* and *does not* fix)

> Register IDs here are **views-pipeline-core's** own register unless noted.

| Pain (this repo) | Where | What `views-frames` does |
|---|---|---|
| **C-186 / #181 — report-stage OOM (object-dtype over full grid×time)** | `managers/reporting/stage.py` (`_load_historical_data`), `prediction_frame_converter.py:73` (list-in-cell), `handlers.py:_init_dataframe:136-152` (per-cell `np.array`), `_prediction_to_tensor:457-486` (float64) | **Solves the class.** A dense, collapsed array frame as the report's input removes the list-in-cell + per-cell-object representation that is ~50–160× dense. See **§5**. |
| **C-40 / C-66 — list-in-cell memory blow-up** (persistence + ensemble agg) | `prediction_frame_converter.to_prediction_df`, `aggregation/aggregator.py` (Polars list-in-cell) | **Solves.** Dense numpy aggregation + flat-columnar (`to_arrow_table`) on-disk; list-in-cell banned (README §7). |
| **C-36 — `_ViewsDataset` god class (~950 LOC, 3-repo private leakage)** | `data/handlers.py` | **Repays.** The leaf takes the *transport/contract* role; `_ViewsDataset` keeps only the pandas↔tensor adapter job (§6). Decompose behind the published protocol, not before (the C-135 ~56-site trap). |
| **C-135 — private-internal reads across repos** | `_time_id`/`_entity_id`/`_get_*_index`/`.dataframe`/`.to_tensor`, ~56 sites | **Replaced by protocols.** Consumers type against `Frame`/`SpatioTemporalIndexed`/`SpatialLevel`. |
| **C-182 — cross-repo mutation of a core object** | views-reporting writes `pg_dataset.reconciled_dataframe` (`dataset_export.py:103,122`) | **Forbidden by construction.** Frames are immutable; reconciliation returns a *new* frame. |
| **C-48 / C-165 — concrete deps, stable pkg with zero abstractions** | `data/` package; 6 concrete collaborators | **Is the abstraction.** Protocols-first leaf; `ModelPathProtocol` (`types.py`) already proves the pattern works here. |
| **C-164 — unwired `DataFetchStrategy`** | `types.py:95-122` | **Gives it a payload.** `FeatureFrame` is the typed `fetch()` return that makes the strategy worth wiring. |
| **C-167 — reconciliation I/O has no typed contract** | `ensemble.py:747`, `dataframe_ensemble.py:921` | **Enables.** Frame types are the typed reconciliation boundary (and the precondition for the D-28 relocation to views-postprocessing). |
| **#113 — pipeline-core ↔ reporting import cycle** | one direction declared, the other behind `try/except ImportError` | **Broken.** Both repos route the contract through the leaf (ADP). |
| **D-33 — collapse `CMDataset`/`PGMDataset` hierarchy** | `data/handlers.py` | **Enables.** cm/pgm becomes a `SpatialLevel` *value* on the index, not a class axis. |

**The honest line:** `views-frames` *solves* the representation sins (object-dtype
blow-up, mutation, private leakage, the cycle) outright, and *enables* the
structural cleanups (C-36 decomposition, C-164 wiring, C-167/D-28 relocation) by
giving the data a typed home — but those cleanups are still pipeline-core's to
execute, in order, behind the published interface.

---

## 5. The worked failure mode: #181 (report-stage host-RAM OOM)

**This is the concrete, measured use-case that makes the contract urgent.**

**Symptom.** `python main.py -r calibration -t -e -re` (HydraNet `violet_visitor`,
32 GB box) is **OOM-killed (exit 137, ~16–20 GB)** in the post-eval report/publish
tail. Drop `-re` → 2.4 GB, exit 0 (~7× less). Peak **scales with
`n_posterior_samples`** (S=3 completes, S=8 OOMs). The model side is ruled out
(the inverse-transform on the real volume is ~0.4 GB).

**Measured root cause** (synthetic micro-benchmark
`reports/investigations/report_stage_oom_181.py`; full write-up
`documentation/post_mortems/2026-06-19_report_stage_oom_181.md`): the report path
materializes prediction *and* historical data as **pandas object-dtype**
DataFrames — list-in-cell `pred_{target}` cells
(`prediction_frame_converter.py:73`) and per-cell `np.array` scalars
(`handlers.py:_init_dataframe:136-152`) — over the **full grid × full timeline**.
Object dtype is **~50–160× per row** the equivalent dense `float32`
(~200–650 B/row vs 4). The two-part signature maps cleanly:

- **~9 GB S-independent base** = historical scalar→per-cell-`np.array`
  object-ification over the full calibration span (~324 months × 32 400 cells ≈
  10.5M cells).
- **Doubling 9 → 18 GB** = the MAP step's `np.sort` over the full-**S** float64
  tensor (`handlers.py:_prediction_to_tensor:457-486` + views-reporting
  `calculate_map`). The collapse is *what first materializes the full-S tensor* —
  which is why it scales with `n_posterior_samples` despite being "post-collapse."

The **dense numpy compute is small** (~0.03 GB forecast / ~0.3 GB historical); the
cost is entirely the **object representation**. The float64 hardcode
(`handlers.py:465`) is a *secondary* contributor, not the driver.

**Why `views-frames` is the durable fix.** The report needs a point/MAP estimate
plus a few quantiles for a *sample* of entities — not all S, not every cell, not
pandas. If the report **receives a dense, collapsed array frame** (a collapsed
`PredictionFrame` / a `MetricFrame`) instead of round-tripping through object-dtype
DataFrames over the full grid, the entire amplification chain disappears at the
source. That is precisely the leaf's contract: dense arrays + identifiers, immutable,
no list-in-cell (README §7). Standalone quick wins (float32, collapse-before-MAP,
entity-sampling, lazy densification, `-re` decoupling) can land first without the
leaf, but the **class** of bug is only closed when the report stops consuming
object-dtype tables — i.e. when it consumes frames.

**Why this is the canonical pipeline-core example.** The failure *manifests* in the
report, but every bloating structure is a pipeline-core type — the converter, the
`_ViewsDataset` densification/object-ification, the float64 tensor. pipeline-core
owns the mechanism; the leaf is where the mechanism is replaced.

---

## 6. What stays in `views-pipeline-core` (explicitly NOT `views-frames`)

Per README §11 and SRP/CRP, the leaf takes the *contract*; this repo keeps
everything application-shaped:

- **Orchestration** — the run lifecycle, stages, WandB lifecycle, CLI. The leaf
  has no concept of a "run."
- **Acquisition** — `ViewsDataLoader`, viewser/datafactory/synthetic dispatch. The
  leaf never fetches (its §3 forbids `viewser`).
- **Persistence & delivery adapters** — `NpzSaver`/`LocalParquetSaver`/
  `ViewsForecastsSaver`/`AppwriteSaver`, and **`PredictionFrameConverter`** (the
  PF↔list-in-cell-parquet boundary format) stay here as *consumer adapters* that
  import the leaf. The `PredictionSaver` protocol (`savers.py`) is already the
  right shape — an injected adapter over a frame.
- **`_ViewsDataset` (pandas↔tensor handler, densification)** — stays, but loses its
  *transport/contract* role to the leaf. It becomes an adapter: "given a frame,
  produce the pandas/tensor view some legacy path still needs," decomposed behind
  the published protocol (C-36, D-33).
- **Reconciliation math, ensemble aggregation, model dispatch** — application
  logic; the leaf gives them typed payloads, not the algorithms.

---

## 7. How pipeline-core's existing patterns already point at frames

- **`PredictionFrame` already exists here** and is already a clean array+identifiers
  value object with construction-time validation and `collapse` — relocating it is
  continuity, not invention.
- **`ModelPathProtocol` / `BaseStageContext` / `DataFetchStrategy`** (`types.py`)
  are *already* the "type against a protocol, inject the concrete" pattern the leaf
  formalizes — `ModelPathProtocol` proves it works in this repo (ADR-045). The leaf
  extends the same idea to the data containers.
- **The `PredictionSaver` protocol** (`savers.py`) is already "an injected adapter
  over a frame" — exactly the adapter-consumes-frame shape the leaf expects.
- **ADR-042's two-track (PredictionFrame vs DataFrame)** is the half-finished
  version of this: the PF track is the array path the leaf makes canonical; the DF
  track is the boundary format that becomes a thin edge adapter.

---

## 8. Migration implications for pipeline-core (Strangler, aligned with README §10)

pipeline-core does most of the README §10 work, each step shippable behind a shim:

1. **Relocate `PredictionFrame`** to the leaf; re-export from
   `data/prediction_frame.py` (§10.2). Every existing import keeps working.
2. **Add `TargetFrame`** and migrate `modules/validation/adapter.py` off pandas
   actuals (§10.4) — highest-value early win.
3. **Relocate `SpatialLevel`** (`domain/spatial.py` → leaf); replace `model.py:824`
   string dispatch, the `_ViewsDataset` subclass axis, and private `_entity_id`
   reads with `index.level` (§10.5, D-33).
4. **Add the flat-columnar `io/arrow`** path; point savers at it; retire
   list-in-cell on the internal path (keep `PredictionFrameConverter` only as the
   external-store boundary adapter) (§10.6) — this is the durable #181/C-186 fix.
5. **Decompose `_ViewsDataset`** (C-36) *behind* the published protocol, after the
   ~56 cross-repo private-internal sites (C-135) are migrated to it — never before.
6. **Wire `DataFetchStrategy`** to return a `FeatureFrame` (C-164).

> Sequencing note carried from the risk register: the C-36 decomposition is gated
> on the leaf existing and on migrating the C-135 sites first; doing it blind is the
> trap the register's C-36 DANGER note guards against.

---

## 9. What pipeline-core needs the contract to guarantee (asks / open questions)

1. **A cheap `collapse` + quantile reduction on the frame** so the report/eval
   paths can reduce S *before* any dense materialization — the direct #181/C-186
   lever. Confirm `collapse` (exists) plus a quantile/HDI summary is in the `Sampled`
   protocol surface.
2. **A dense, flat on-disk format the savers can target** (`io/arrow`, README §7)
   that `pd.read_parquet` can still read back — so `LocalParquetSaver` and the
   forecasts-store path migrate without breaking the cross-repo disk contract.
3. **`SpatialLevel` owns cm/pgm + cross-level (country↔grid) alignment** in the
   `SpatioTemporalIndex` — pipeline-core's reconciliation and ensemble aggregation
   both need the cm↔pgm join, not just same-level intersection (C-167, D-28).
4. **Provenance in frame `metadata`** (model, run_type, timestamp, seed) — the
   `configuration.py:182` timestamp is the join key the #178 work exposed; a stamped
   identity in the frame is the durable home for run↔artifact provenance (README §13.5).
5. **A typed contract for the engine extension points** — `_train/_evaluate/
   _forecast_model_artifact` return `-> any` today (C-48); a frame return type gives
   the producer/consumer boundary a checkable shape.

---

## 10. Cross-references

- `views-frames` README: §1 (problems — incl. the #181 bullet), §2 (DAG position),
  §4 (frame family), §5 (protocols), §7 (serialization — where "doesn't scale" is
  decided), §10 (migration — pipeline-core does most of it), §11 (scope — what is
  NOT here), §12 (risk register), §13 (open decisions — esp. §13.5 provenance).
- `views-pipeline-core` investigation: `documentation/post_mortems/2026-06-19_report_stage_oom_181.md`
  (root cause + durable fix), `reports/investigations/report_stage_oom_181.py`
  (the micro-benchmark), `tests/test_managers/test_report_stage_memory.py` (guard).
- `views-pipeline-core` register: **C-186** (#181, observed-in-prod), C-36, C-40,
  C-66, C-135, C-182, C-48, C-165, C-164, C-167; D-28, D-33; the Causal Clusters
  "Data-Contract Gap" (Cluster A, keystone = views-frames). Governing: ADR-042
  (two-track), ADR-045 (stages), ADR-054 (extraction).
- Companion: `perspectives/from_views-reporting_perspective.md` (the presentation
  consumer — same leaf, opposite end of the #181/C-48 story).
