# views-frames

> The VIEWS platform's **data-contract layer**: small, stable, abstract array
> containers (`FeatureFrame`, `PredictionFrame`, and their anticipated siblings)
> that every other repo depends on and that depends on nothing internal.
>
> **Status:** scaffolding. This README is the design bible. No code yet — it is
> written so the package can be built *against* it. Read it fully before adding a
> single class.

---

## 0. One-paragraph thesis

DataFrames (pandas/geopandas/polars) are a **boundary/interop and analysis**
format, not an internal data-handling representation. They do not belong as the
canonical transport type inside the VIEWS pipeline. The canonical transport is an
**array + spatiotemporal identifiers** value object — what we call a *frame*.
Two frames already exist, **duplicated and diverging** across repos
(`PredictionFrame` in views-pipeline-core, `FeatureFrame` in views-datafactory).
`views-frames` unifies them into one **leaf package** at the root of the
dependency graph: maximally stable, maximally abstract, numpy-only, depended on
by everyone, depending on nothing internal. It is the keystone that
de-duplicates the frames, breaks cross-repo dependency cycles, removes pandas
from internal transport, and gives arrays the label-alignment that today forces
pandas back into the hot path.

---

## 1. Why this package exists (the problems it kills)

Concrete, current pain — each item is a real, observed defect this package is
designed to resolve (register IDs are from views-pipeline-core's technical risk
register):

- **Duplicated, diverging twins.** `PredictionFrame`
  (`views-pipeline-core/views_pipeline_core/data/prediction_frame.py`) and
  `FeatureFrame`
  (`views-datafactory/src/datafactory_adapters/feature_frame.py`) are near-1:1
  (`values: ndarray` + `identifiers: {time, unit}` + `metadata` + `save/load`)
  but have two owners, two release cadences, and **no shared base**. They will
  drift. (REP violation — reused together, released apart.)
- **Circular package dependency.** views-pipeline-core ↔ views-reporting form a
  cycle (one direction declared, the other hidden behind `try/except ImportError`).
  See views-reporting issue #113. A neutral leaf package both sides route their
  data contract *through* breaks the cycle (ADP).
- **pandas leaks into internal transport.** The evaluation boundary still takes
  `actual: pd.DataFrame, predictions: List[pd.DataFrame]`
  (`modules/validation/adapter.py`); ingest returns `pd.DataFrame`; the
  list-in-cell parquet encoding causes a measured ~33× memory blow-up (C-40,
  C-66). The frame + a flat columnar disk format fix the scaling; a `TargetFrame`
  fixes the eval boundary.
- **God-class data handler with leaked internals.** `_ViewsDataset`
  (`data/handlers.py`, ~950 LOC, C-36) is consumed across three repos by reaching
  into its **private** members (`_time_id`, `_entity_id`, `_get_entity_index`,
  `.dataframe`, `.to_tensor`) at ~56 sites (C-135), and views-reporting even
  **mutates** a core object across the repo boundary
  (`pg_dataset.reconciled_dataframe = ...`, C-184). Frames are immutable value
  objects with a *published* interface — the opposite of this.
- **Stable package, zero abstractions.** views-pipeline-core's `data/` is its
  most depended-on (most stable) package yet contains no protocols/ABCs (C-165,
  C-48). A stable component must be abstract (SAP). This package *is* the
  abstraction.

**The product is not "a numpy wrapper." The product is the identifier/alignment
contract** — the shared, versioned definition of "an array aligned to (time,
unit)" that every model, evaluator, reconciler, and report agrees on.

---

## 2. Position in the dependency graph (the whole point)

```
                        ┌───────────────────────┐
                        │     views-frames      │  ← leaf / root of the DAG
                        │  (numpy only, stable, │     stable + abstract (SDP+SAP)
                        │   abstract protocols)  │     depends on NOTHING internal
                        └───────────▲───────────┘
            ┌───────────────┬───────┴────────┬────────────────┐
            │               │                │                │
   views-pipeline-core  views-datafactory  views-evaluation  model repos
   (orchestration)      (data production)  (metrics)         (hydranet, bayesian,
            │               │                                  stepshifter, r2darts2,
            ▼               ▼                                  baseline, lab00)
   views-reporting / views-postprocessing (consumers, downstream)
```

**Rule:** every internal arrow points *toward* `views-frames`. `views-frames`
imports **no** `views_*` package, ever. If it ever needs to, the boundary is
wrong. This is what makes it impossible to participate in a cycle (ADP) and what
makes it safe to depend on from everywhere (SDP).

---

## 3. Hard constraints (non-negotiable; reject PRs that break these)

1. **Dependencies:** `numpy` only, in the core. Optional extras may add
   serialization deps **behind `io/` submodules** (`pyarrow` for the columnar
   format), never in the core frame classes. **Never** import `pandas`,
   `geopandas`, `polars`, `wandb`, `viewser`, `torch`, or any `views_*` package
   from the core. (CRP: a model that wants a `PredictionFrame` must not
   transitively install the pandas/reporting world.)
2. **No application logic.** No fetching, no model code, no report rendering, no
   reconciliation math, no wandb, no disk-path conventions beyond `save/load` of
   the frame itself. Those are *adapters* and live in the consumer repos.
3. **Immutable value objects.** A frame is validated at construction and then
   treated as read-only. Operations (`collapse`, `select`, `with_metadata`)
   **return new frames**; they never mutate in place. (Directly forbids the
   C-184 cross-repo-mutation anti-pattern.)
4. **Fail loud at construction.** All invariants are checked in `__init__` and
   raise `ValueError`/`TypeError` immediately — never return a half-valid object,
   never log-and-continue. (Matches the platform's "Fail Loud and Proud" rule.)
5. **dtype discipline.** `values` are `float32` (contiguous); identifier arrays
   are integer dtype; **no `object` dtype, ever** (object/list-in-cell is the
   thing that doesn't scale). Identifiers are complete (no NaN).
6. **One concept per file.** See §6. Multiple classes in one file is the
   exception, justified only by genuine tight coupling.

---

## 4. The frame family

A *frame* = a numeric array whose first axis is **N rows**, each row carrying a
complete set of **spatiotemporal identifiers** `{time, unit}`, optionally with a
trailing **sample axis S** (posterior draws / ensemble members) and, for
multi-channel frames, a **feature/channel axis**.

### 4.1 Existing (unify these first)

| Frame | Array shape | Extra fields | Semantics | Lives today in |
|---|---|---|---|---|
| **`FeatureFrame`** | `y_features: (N, F)` or `(N, F, S)` | `feature_names: list[str]` | model **inputs** (X) | views-datafactory |
| **`PredictionFrame`** | `y_pred: (N, S)` | — | model **outputs** (ŷ samples) | views-pipeline-core |

Existing `PredictionFrame` contract (preserve on migration): `float32`;
`REQUIRED_IDENTIFIERS = {"time", "unit"}`; validates 2D, `n_rows > 0`,
`sample_count >= 1`, identifiers present + length-N + no NaN; properties
`n_rows`, `sample_count`, `identifier_keys`; `collapse(method="arithmetic_mean")`
→ new `(N, 1)` frame; `save(dir)` → `y_pred.npy` + `identifiers.npz`;
`load(dir, mmap=False)`. Existing `FeatureFrame` adds `feature_names`,
`metadata`, `n_features`, `is_sample`.

### 4.2 Anticipated (design the base so these drop in via OCP, don't build all now)

| Frame | Array shape | Why we already know we need it | Priority |
|---|---|---|---|
| **`TargetFrame`** (a.k.a. `ActualsFrame`) | `y_true: (N, 1)` | The **evaluation boundary** still takes pandas actuals (`adapter.py`). A target frame makes eval array-native and kills that pandas dependency. Structurally `PredictionFrame` with `S=1`. | **next** |
| **`WeightFrame`** | `w: (N,)` or `(N, S)` | Weighted losses / weighted metrics. Same identifiers, different `values` meaning. | when weighting lands |
| **`MaskFrame`** | `mask: (N,)` bool | Partial-data / sparse-actuals evaluation (C-26 silent truncation). Marks which (time, unit) cells are present. | when partial eval lands |
| **`MetricFrame`** (a.k.a. `ScoreFrame`) | `(K, …)` keyed by `(target, step, unit)` | Evaluation **outputs** are currently scattered into wandb summaries + parquet. First-class array form. | exploratory |

**Already exists externally — do NOT rebuild:** `EvaluationFrame` lives in
`views-evaluation` (aligned pred×actual×(origin, step)). `views-frames` should
define the **identifier/index protocol it conforms to**, and views-evaluation
should adopt that protocol — not have its frame re-implemented here.

### 4.3 The real shared primitive: `SpatioTemporalIndex`

Every frame is **array + identifiers**. The identifiers — `{time, unit}` (plus
the cm/pgm `SpatialLevel`) — and the **alignment/join logic over them** are the
genuinely reused core. Build this once:

- Fields: `time: int[N]`, `unit: int[N]`, `level: SpatialLevel` (cm/pgm), all
  numpy, integer dtype, no NaN, length N.
- Pure-numpy operations (no pandas): `intersect`, `align`/`reindex`,
  `is_superset_of`, `argsort`, `searchsorted`-based joins. **This is what gives
  arrays the label-alignment that today drags pandas back in** (cm↔pgm
  reconciliation, pred↔actual join, partial-overlap evaluation).
- `SpatialLevel` (currently `views-pipeline-core/domain/spatial.py`) should move
  here — it is a tiny, stable value object that *is* part of the identifier
  vocabulary (it defines `index_names` and `entity_column`: cm→`country_id`,
  pgm→`priogrid_id`). Owning it here ends the bare-string `"cm"`/`"pgm"` sprawl
  (C-38) and the `_ViewsDataset` private `_entity_id` reads (C-135).

> Design heuristic: if two consumers disagree about how `(time, unit)` align,
> that disagreement belongs **here**, resolved once, not re-implemented per repo.

---

## 5. Abstractions / Protocols (DIP, ISP, SAP, LSP)

The package exports **Protocols first, concretes second.** Consumers type against
the protocols (DIP); a concrete frame is an implementation detail.

Segregate the surface so no consumer depends on methods it does not use (ISP):

- **`SpatioTemporalIndexed`** — `identifiers`, `n_rows`, `index: SpatioTemporalIndex`.
  (What a reconciler/aligner needs.)
- **`Sampled`** — `sample_count`, `is_sample`, `collapse(method) -> Self`.
  (What an ensemble/aggregator needs.)
- **`Persistable`** — `save(dir)`, `load(dir, mmap)`.
  (What I/O needs — and *only* I/O.)
- **`Frame`** = the small composition the math layer needs: `values`, `index`,
  `n_rows`. Nothing else.

**LSP + composition over inheritance:** `FeatureFrame`, `PredictionFrame`,
`TargetFrame`, … are **siblings, not a subtype chain.** Do **not** make one
inherit another. They share behavior by (a) satisfying the same Protocols and
(b) composing a `SpatioTemporalIndex` and a small internal validation helper —
**not** by extending a fat base class. A subtype must be substitutable wherever
its protocol is expected; that holds for protocol conformance, and it is exactly
what a `CMDataset`-style inheritance tree gets wrong. The cm/pgm distinction is a
**value** (`SpatialLevel`) carried by the index, never a class axis.

> Anti-pattern, explicitly banned: a `_BaseFrame` god-class that
> `FeatureFrame`/`PredictionFrame` extend and that accretes everyone's methods.
> That recreates `_ViewsDataset` (C-36). Keep the base a **Protocol**; share code
> by composition.

---

## 6. Physical layout (the repo must scream "data contracts")

```
views-frames/
├── README.md                      # this file (the design bible)
├── pyproject.toml                 # numpy core; [arrow] optional extra for io/arrow
├── LICENSE
├── src/views_frames/
│   ├── __init__.py                # EXPLICIT re-exports only (no `import *`)
│   ├── index.py                   # SpatioTemporalIndex value object + alignment
│   ├── spatial_level.py           # SpatialLevel enum (cm/pgm) — relocated here
│   ├── protocols.py               # Frame / SpatioTemporalIndexed / Sampled / Persistable
│   ├── _validation.py             # shared construction-time invariants (private helper)
│   ├── feature_frame.py           # FeatureFrame              ── one concept per file
│   ├── prediction_frame.py        # PredictionFrame
│   ├── target_frame.py            # TargetFrame  (anticipated)
│   ├── weight_frame.py            # WeightFrame  (anticipated)
│   ├── mask_frame.py              # MaskFrame    (anticipated)
│   └── io/                        # serialization adapters — SEPARATE from frames (SRP)
│       ├── __init__.py
│       ├── npz.py                 # native save()/load() (.npy + .npz)
│       └── arrow.py               # flat columnar (.parquet) — the scalable disk format
└── tests/
    ├── conformance/               # the published contract suite consumers re-run (see §9)
    └── unit/
```

Layout rules (these *are* the screaming-architecture requirements):

- **One main class/concept per file.** Multiple classes in a file is the
  exception, allowed only for genuinely inseparable units.
- **Serialization is not the frame's job.** I/O adapters live under `io/`, import
  the frame, and change for *their own* reasons (a new store format) — not when
  the frame's schema changes (SRP + CCP). `PredictionFrameConverter`
  (PF↔list-in-cell DataFrame, a pipeline-core boundary format) **stays in
  pipeline-core**; it is an adapter, not a frame concern.
- **No dumping grounds.** A file accumulating loose helpers/types/constants/
  classes means a boundary is wrong — split it. (`handlers.py`/`file.py`-style
  13-class files are the failure mode we are escaping.)
- **Explicit `__init__.py` re-exports** (named, not `import *`) so the public API
  is statically analyzable.
- A new developer should infer every responsibility from the file tree without
  reading bodies.

---

## 7. On-disk / serialization contract (where "doesn't scale" is actually decided)

The scaling failure in the platform today is the **list-in-cell `object`-dtype
DataFrame** (a cell holds a Python list of S samples) — measured ~33× blow-up
(C-40/C-66). `views-frames` standardizes two scalable formats and **bans
list-in-cell**:

- **Native (`io/npz.py`):** `values.npy` (contiguous float32) + `identifiers.npz`.
  Supports `mmap` load so peak RAM = working set, not full array. (This is the
  existing `PredictionFrame.save/load`; keep it.)
- **Interchange (`io/arrow.py`):** **flat columnar** parquet — one row per
  `(time, unit[, sample])`, scalar cells only, zero-copy Arrow write. This is the
  scalable replacement for the list-in-cell format and is what crosses to the
  forecasts store / delivery. (Mirrors the existing `to_arrow_table()` path.)

The **boundary adapters** that convert a frame to a *pandas/views-forecasts*
representation (because those external stores mandate pandas) live in the
**consumer** repo, depend on `views-frames`, and are explicitly out of scope
here (CRP). `views-frames` makes the array authoritative; pandas becomes a thin
edge adapter, never the internal type.

---

## 8. Contract evolution & versioning (SemVer for a thing N repos import)

Because everyone depends on this, breakage is expensive — version it as a
**published contract**, not as app code:

- **MAJOR** (breaking): removing/renaming a field, changing a dtype or axis
  meaning, adding a **required** identifier, tightening an invariant.
- **MINOR** (additive, back-compatible): a new frame type, a new **optional**
  metadata key, a new method, a new `io/` format.
- **PATCH:** bug/doc fixes with identical contract.
- Adding a required identifier is the canonical breaking change — prefer optional
  + a deprecation window. Provide a `from_legacy_*` shim path when a consumer
  format changes.
- **SAP in practice:** if this package needs frequent MAJOR bumps, it is not
  abstract/stable enough — push volatility *out* into consumer adapters.

---

## 9. Testing strategy (closes the cross-repo contract-test gap, C-30)

- **Conformance suite (`tests/conformance/`):** a *published*, importable set of
  contract tests asserting the invariants of each Protocol (round-trip
  save/load, identifier completeness, collapse semantics, alignment laws). Every
  consumer repo runs it in CI against its own adapters. This is the missing
  cross-repo contract test (C-30) and the safety net that lets the frames evolve
  without silently breaking N repos.
- **Property tests** for `SpatioTemporalIndex` alignment (intersection is
  commutative; align then collapse == collapse then align; etc.).
- **No mocks needed** — frames are pure value objects over numpy. If a test needs
  a mock, the thing under test probably doesn't belong in this package.

---

## 10. Migration / adoption plan (Strangler, not big-bang)

1. **Stand up the package** with `SpatioTemporalIndex`, `protocols.py`,
   `_validation.py`, and `io/npz.py`.
2. **Move `PredictionFrame` here verbatim** (preserve its contract from §4.1),
   re-export from `views-pipeline-core/data/prediction_frame.py` as a thin shim
   (`from views_frames import PredictionFrame`) so existing imports keep working.
3. **Unify `FeatureFrame`:** move datafactory's implementation here; datafactory
   re-exports a shim. The twins now share `SpatioTemporalIndex` + validation.
4. **Add `TargetFrame`** and migrate the evaluation adapter
   (`modules/validation/adapter.py`) off pandas actuals — the highest-value early
   win.
5. **Relocate `SpatialLevel`** here; replace bare `"cm"`/`"pgm"` strings and
   `_ViewsDataset._entity_id` reads with `index.level.entity_column`.
6. **Add `io/arrow.py`**; point savers at the flat columnar format; retire
   list-in-cell on the internal path (keep a boundary adapter only where an
   external store mandates pandas).
7. Consumers drop their direct `_ViewsDataset` private-internal access in favor
   of the published frame/index protocols.

Each step is independently shippable and back-compatible via shims (REP/CCP: the
twins now release together; nothing changes that doesn't change together).

---

## 11. Scope boundaries — what does NOT live here

- **Adapters to pandas / views-forecasts / appwrite / parquet-store** → consumer
  repos (pipeline-core, datafactory). External stores mandate pandas; that is an
  *edge*, not the core.
- **`_ViewsDataset` (pandas↔tensor handler, densification)** → stays in
  pipeline-core; it is heavy, pandas-bound, and a different stability tier.
- **Reconciliation math, model code, report rendering, wandb, viewser** → their
  owning repos.
- **`EvaluationFrame`** → stays in views-evaluation; conform it to our index
  protocol instead.

If something here starts needing pandas, a `views_*` import, or app logic, it is
in the wrong package — extract it to a consumer adapter.

---

## 12. Risk-register & decisions this resolves / informs

Resolves or directly addresses (views-pipeline-core register): **C-36**
(`_ViewsDataset` god class — frames replace its transport role with a published
interface), **C-40 / C-66** (list-in-cell memory blow-up — flat columnar +
arrays), **C-48** (concrete dependencies → protocols), **C-135** (private-internal
cross-repo leakage → published interface), **C-164** (unwired `DataFetchStrategy`
— frames give the strategy a typed payload), **C-165** (stable package, zero
abstractions — this *is* the abstraction), **C-167** (reconciliation I/O has no
typed contract → frame I/O contract), **C-184** (cross-repo mutation of
`reconciled_dataframe` → immutable frames). Keystone for views-reporting **#113**
(circular dependency) and informs **D-28** (relocate reconciliation) and **D-33**
(collapse the `CMDataset/PGMDataset` hierarchy into a `SpatialLevel` value).

---

## 13. Open decisions (resolve before/at first code)

1. **Separate repo (this) vs. interim `views_pipeline_core/frames/` sub-package.**
   Separate repo is the principled SDP/SAP/REP end state and the only thing that
   de-duplicates datafactory's `FeatureFrame`; the sub-package is a lower-overhead
   stopgap that leaves the duplication and the stability problem. This scaffold
   assumes the separate repo.
2. **`TargetFrame` vs `ActualsFrame` naming** (and whether targets/actuals are one
   type with a role flag).
3. **Does `SpatialLevel` move here or get imported from a shared `views-domain`?**
   (Recommendation: here — it is identifier vocabulary.)
4. **Minimum numpy version / typed-array (nptyping vs bare) policy.**
5. **`metadata` schema:** free-form dict vs. a typed, validated header (provenance:
   model name, run_type, timestamp — note the #178 provenance work suggests a
   stamped run identity belongs in frame metadata).
6. **Sample-axis convention:** is `S=1` an explicit axis or absent? (Affects
   `collapse`, `is_sample`, and every shape check — decide once.)

---

## 14. Glossary

- **Frame:** an immutable value object = numeric array (first axis = N rows) +
  complete spatiotemporal identifiers, optionally with a sample axis S.
- **Identifier:** a length-N integer array locating each row in space/time
  (`time`, `unit`).
- **`SpatioTemporalIndex`:** the `{time, unit, level}` triple + pure-numpy
  alignment logic; the genuinely reused primitive.
- **`SpatialLevel`:** cm (country-month) | pgm (PRIO-GRID-month); defines the unit
  column.
- **Sample axis (S):** posterior draws / ensemble members; `collapse` reduces it.
- **list-in-cell:** the banned `object`-dtype encoding (a DataFrame cell holding a
  Python list of samples); the actual non-scaler.

---

*Build against this document. If the code and this README disagree, that is a bug
in one of them — reconcile before merging.*
