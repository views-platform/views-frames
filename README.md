# views-frames

> The VIEWS platform's **data-contract layer**: small, stable, abstract array
> containers (`FeatureFrame`, `PredictionFrame`, and their anticipated siblings)
> that every other repo depends on and that depends on nothing internal.
>
> **Status:** **v1.5.0 — frozen API** (frozen since v1.0.0, ADR-018; the v1.1 surface is
> purely additive — the coherent posterior summary, ADR-019; v1.2.0 rebuilt the tower
> `outside-in`, C-44; v1.3.0 makes the tower summary distribution-agnostic — no magnitude
> zeroing by default, register C-45; v1.4.0 adds generic provenance to `FrameMetadata`
> (`run_id`/`data_version`) and publishes the shared `assert_frame_envelope` checker,
> ADR-020; v1.5.0 adds the threshold **exceedance** estimator `P(Y > c)`, ADR-021). This
> README is the design
> bible; the contract it specifies is realised in `src/views_frames/` (index, frames,
> io, conformance suite) plus the `src/views_frames_summarize/` sibling package
> (sample-axis summarization — `collapse`/MAP/HDI/quantiles, the coherent-tower estimators
> `hdi_tower`/`tower_point`/`bimodality`/`summarize_tower`, + cross-level
> aggregation; ADR-017, ADR-019). The blocking design decisions are resolved (§13a) and
> ratified as ADRs 011–018; two rounds of consumer review validated
> the design. Consumer adoption (re-export shims, pandas migration) is the owner's
> migration, not this repo's.
> If the code and this README disagree, that is a bug — reconcile before merging.

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

## 0a. Quickstart

Build a frame, summarize its sample axis, serialize it, and run the published
contract check. The full runnable script is [`examples/quickstart.py`](examples/quickstart.py)
(`uv run examples/quickstart.py`):

```python
import numpy as np
from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames.conformance import assert_frame_contract
from views_frames_summarize import collapse, hdi, map_estimate

index = SpatioTemporalIndex(
    time=np.array([1, 1, 2], dtype=np.int64),
    unit=np.array([10, 11, 10], dtype=np.int32),
    level=SpatialLevel.PGM,
)
pf = PredictionFrame(np.random.default_rng(0).gamma(2.0, 1.0, (3, 500)).astype("f4"), index)

mean = collapse(pf, np.mean)      # (N, S) -> (N, 1) frame, statistic injected
mode = map_estimate(pf)           # per-row MAP -> (N, 1) frame
band = hdi(pf, mass=0.9)          # per-row 90% HDI -> (N, 2) index-aligned array

pf.save("/tmp/pf"); reloaded = PredictionFrame.load("/tmp/pf")
assert_frame_contract(pf)         # the check a consumer runs in its own CI
```

The leaf (`views_frames`) owns the immutable array+identifier contract and
alignment; the sibling (`views_frames_summarize`) owns the sample-axis statistics.
Both are numpy-only. For the subtler cm↔pgm surface — a time-varying
`(time, unit)→country` mapping, `cross_level_align`, and conservation-correct
`aggregate_distributions` (`HDI(sum) ≠ sum(HDI)`) — see
[`examples/cross_level.py`](examples/cross_level.py).

**Which estimator? (two coherent paths, v1.3.0).** Each frozen estimator has a
coherent-tower sibling (ADR-019): `map_estimate` ↔ `tower_point` (an unbinned
median-of-the-`tip_mass`-floor point — the "shorth", free of `map_estimate`'s histogram
tie-break bias **and** robust to minority duplicated draws, register C-44), and
`hdi`/`quantiles` ↔ `hdi_tower(masses=…)` (HDIs built **outside-in**, nested **by
construction** and reproducible — a mass's interval is identical regardless of which others
you request), with `summarize_tower` returning all three in one pass. The tower path is
**distribution-agnostic** — it works for counts, continuous, normal, and `[0,1]`
(rate/probability) targets, with **no magnitude zeroing by default** (zero-inflation is read
off the floor's density, register C-45); a count consumer that wants "sub-1 ⇒ 0" opts in via
`config['zero_cutoff']`. The tower's tunables live in `views_frames_summarize.config`
(fail-loud, no silent defaults). Use the **frozen** estimators for parity with existing
pipelines; use the **tower** path when you need coherent, reproducible bands plus a matching,
duplicate-robust point.

**Reading the `bimodality` flag.** It is a *deliberately conservative* heuristic, **not** a
formal multimodality test — tuned for **zero false positives** at the cost of recall on
overlapping / unequal mixtures. A `1` means "clearly-separated modes detected"; a `0` means
**"no clear bimodality detected," not "proven unimodal."** (Full caveat: the `bimodality`
module docstring; register C-34.)

---

## 1. Why this package exists (the problems it kills)

Concrete, current pain — each item is a real, observed defect this package is
designed to resolve (register IDs are from views-pipeline-core's technical risk
register):

- **Duplicated, diverging twins.** `PredictionFrame`
  (`views-pipeline-core/views_pipeline_core/data/prediction_frame.py`) and
  `FeatureFrame`
  (`views-datafactory/src/datafactory_adapters/feature_frame.py`) share a core
  (`values: ndarray` + `identifiers: {time, unit}` + `save/load`) but are **not
  near-1:1**: they diverge on ≥6 axes — sample-axis position, `feature_names` /
  `metadata`, identifier NaN-check, `collapse` / `mmap`, save footprint, and
  `PredictionFrame` still imports pandas. They have two owners, two release
  cadences, and **no shared base**. They will drift. (REP violation — reused
  together, released apart.) The fix unifies the *shared index + protocols*, not
  the classes — see §5 (Option C) and §13a.
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
- **Observed in production (#181) — the thesis, measured.** A HydraNet eval run
  (`main.py -r calibration -t -e -re`) is **OOM-killed (exit 137, ~16–18 GB)** in
  the report tail; dropping the report flag → 2.4 GB (~7× less). A synthetic
  micro-benchmark line-isolated it: the report builds **object-dtype** DataFrames
  (list-in-cell `pred_{target}` + per-cell `np.array` actuals) over the **full
  grid × full timeline** — **~50–160×** the dense float32 cost (~200–650 B/row vs
  4). The dense numpy compute is *small* (~0.3 GB); the cost is the object
  representation. It scales with `n_posterior_samples` (the collapse step is what
  first materializes the full-sample tensor). This is C-40/C-66 firing for real —
  pipeline-core **C-186**, the **first observed-in-production member** of the
  Data-Contract Gap cluster, and the live use-case that motivates this package.
  A dense, collapsed array frame is the fix.
- **God-class data handler with leaked internals.** `_ViewsDataset`
  (`data/handlers.py`, ~950 LOC, C-36) is consumed across three repos by reaching
  into its **private** members (`_time_id`, `_entity_id`, `_get_entity_index`,
  `.dataframe`, `.to_tensor`) at ~56 sites (C-135), and views-reporting even
  **mutates** a core object across the repo boundary
  (`pg_dataset.reconciled_dataframe = ...`,
  `views-reporting/reconciliation/dataset_export.py:103,122`; C-184). Frames are
  immutable value objects with a *published* interface — the opposite of this.
- **Evaluation outputs scattered, then mis-read.** A model's evaluation metrics
  are written to a local `eval_*.parquet` *and* logged to wandb, with no typed
  output container. views-reporting's evaluation report scrapes them back out of
  wandb (`get_latest_run().summary`) and — because that returns the latest
  *created* run, not the latest run *with* metrics — renders the wrong run:
  **22/25 constituents showed "not calculated"** in a real ensemble report while
  the scores sat in an earlier run (views-reporting's own register, C-48). A
  first-class **`MetricFrame`** (§4.2) is the typed output form the report *could
  adopt* instead of re-deriving from a mutable mirror — but `MetricFrame` is
  **out of this leaf** (it is keyed `(target, step, unit)`, not a `(time, unit)`
  frame; views-evaluation owns eval-output vocab). What this package provides is
  the **substrate** for that cure (the typed, conformance-checked frame contract +
  the extensible `FrameMetadata` header), not the cure itself. *(Exploratory; §4.2,
  §13a.6.)*
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

> **Consumer views.** Each downstream repo has a detailed view of how it uses
> these frames. The first is **views-reporting** — the presentation layer that
> *consumes* `PredictionFrame`, `TargetFrame`, and `MetricFrame` and routes its
> data contract through this leaf (which is what breaks the
> views-pipeline-core ↔ views-reporting cycle, reporting issue **#113**).
>
> **views-pipeline-core** is the **origin/orchestration**
> repo's view — not a pure downstream consumer but the repo that *owns these types
> today* (`PredictionFrame`, `_ViewsDataset`, the converter) and hands the contract
> off to this leaf. It carries the worked failure mode (#181 report-stage OOM,
> C-186) and the migration mechanics (it does most of README §10).

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
   C-184 cross-repo-mutation anti-pattern.) **Copy-vs-view:** structural and
   metadata-only operations (`with_metadata`, contiguous `select`) return frames
   that **share** the underlying `values` buffer (numpy view / zero-copy), and a
   `mmap`-backed frame stays `mmap`-backed — a new frame must never copy a
   multi-GB `values` buffer (that would reintroduce the §7 blow-up). Only a
   reducing op (`collapse`) allocates, and only the reduced array. Pinned in the
   conformance suite.
4. **Fail loud at construction.** All invariants are checked in `__init__` and
   raise `ValueError`/`TypeError` immediately — never return a half-valid object,
   never log-and-continue. (Matches the platform's "Fail Loud and Proud" rule.)
5. **dtype discipline.** `values` are `float32` (contiguous); identifier arrays
   are integer dtype; **no `object` dtype, ever** (object/list-in-cell is the
   thing that doesn't scale). Identifiers are complete (no NaN). The guarantee is
   **structural, not temporal**: the leaf validates integer / length-N / no-NaN,
   but `time` is an **opaque integer** — month_id epoch, range, and monotonicity
   are a producer-adapter concern, never the leaf's (the leaf is epoch-agnostic).
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

**Sample axis convention (decided, §13a).** The sample axis **S** is **always an
explicit trailing axis** (`S ≥ 1`): `PredictionFrame` is `(N, S)`, `FeatureFrame`
is `(N, F, S)`, `TargetFrame` is `(N, 1)`. `is_sample` is `S > 1`; `collapse`
reduces the trailing axis. One shape contract across the family — no `ndim`
branching. A corollary: relocating `PredictionFrame` is a **numpy-only rewrite of
its identifier validation, not a verbatim move** — today it imports pandas and
uses `pd.isna` for the NaN-check (§10.2).

### 4.2 Anticipated (design the base so these drop in via OCP, don't build all now)

| Frame | Array shape | Why we already know we need it | Priority |
|---|---|---|---|
| **`TargetFrame`** (a.k.a. `ActualsFrame`) | `y_true: (N, 1)` | The **evaluation boundary** still takes pandas actuals (`adapter.py`). A target frame makes eval array-native and kills that pandas dependency. Structurally `PredictionFrame` with `S=1`. | **next** |
| **`WeightFrame`** | `w: (N,)` or `(N, S)` | Weighted losses / weighted metrics. Same identifiers, different `values` meaning. | when weighting lands |
| **`MaskFrame`** | `mask: (N,)` bool | Partial-data / sparse-actuals evaluation (C-26 silent truncation). Marks which (time, unit) cells are present. | when partial eval lands |
| **`MetricFrame`** (a.k.a. `ScoreFrame`) | `(K, …)` keyed by `(target, step, unit)` | Evaluation **outputs** are currently scattered into wandb summaries + parquet. First-class array form. **views-reporting's eval report is the consumer of record** — today it scrapes wandb and renders the wrong run (its run-selection bug, C-48). | exploratory |

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
- **Same-level operations (owned here, pure-numpy, no pandas):** `intersect`,
  `reindex`, `is_superset_of`, `argsort`, `searchsorted`-based joins over
  `(time, unit)` **at a single `SpatialLevel`**. **This is the label-alignment
  that today drags pandas back in** — pred↔actual join, partial-overlap
  evaluation, same-level reindex. This alignment logic lives in the leaf
  unconditionally.
- **Cross-level operations (`cross_level_align`) — protocol here, data injected.**
  The cm↔pgm **cross-level join** (country↔grid) is **not** a same-axis set op; it
  is a one-to-many lookup against a `priogrid→country` mapping that is **injected**
  by the consumer and **not embedded in the leaf** — the mapping is external,
  viewser-sourced, and **time-varying** (a cell's country assignment changes by
  month). The leaf owns only the operation signature `cross_level_align(index,
  mapping)`. The alignment logic stays in the leaf; the alignment data (the
  mapping) is supplied by the consumer (or a separate reference package the leaf
  does not depend on), never fetched or versioned here — embedding versioned domain
  data would make the leaf change for data reasons and break §8 maximal stability.
  This resolves the falsified "domain-free cross-level" claim
  (a falsification audit, 5 hard falsifications); faoapi's producer-materialised
  metadata is the existence proof.
- `SpatialLevel` (currently `views-pipeline-core/domain/spatial.py`) should move
  here — it is a tiny, stable value object that *is* part of the identifier
  vocabulary (it defines `index_names` and `entity_column`: cm→`country_id`,
  pgm→`priogrid_id`). It carries the *labels*, never the cross-level *mapping*.
  Owning it here ends the bare-string `"cm"`/`"pgm"` sprawl (C-38) and the
  `_ViewsDataset` private `_entity_id` reads (C-135). Relocate it with the C-65
  reversed index-tuple (must be time-first `(month_id, entity)`) and the
  `priogrid_gid`/`priogrid_id` inconsistency **fixed, not ported**.

> Design heuristic: if two consumers disagree about how `(time, unit)` align **at
> the same level**, that disagreement belongs **here**, resolved once. If they
> disagree about *which country a cell belongs to*, that is domain reference data
> — it belongs to the consumer / producer, never the leaf.

---

## 5. Abstractions / Protocols (DIP, ISP, SAP, LSP)

The package exports **Protocols first, concretes second.** Consumers type against
the protocols (DIP); a concrete frame is an implementation detail.

Segregate the surface so no consumer depends on methods it does not use (ISP):

- **`SpatioTemporalIndexed`** — `identifiers`, `n_rows`, `index: SpatioTemporalIndex`.
  (What a reconciler/aligner needs.)
- **`Sampled`** — `sample_count`, `is_sample` (the *structural* sample-axis facts).
  Reduction over the sample axis lives in `views_frames_summarize`, not here (ADR-017).
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
>
> **Unification model — Option C (decided, §13a).** v1 unifies **only** the shared
> `SpatioTemporalIndex` + `_validation` + protocols + `io/`; the frame classes are
> relocated as **separate sibling classes**, not merged. This captures the real
> reused core (the index) at the lowest churn and zero god-class risk. A composed,
> shared metadata header across frames (Option B) is a later upgrade *only if* a
> third frame proves the header is genuinely reused. A shared concrete base
> (Option A) is **rejected in writing**.

---

## 6. Physical layout (the repo must scream "data contracts")

```
views-frames/
├── README.md                      # this file (the design bible)
├── pyproject.toml                 # numpy core; [arrow] optional extra for io/arrow
├── LICENSE
├── src/views_frames/              # the pure data contract (numpy only, depends on nothing)
│   ├── __init__.py                # EXPLICIT re-exports only (no `import *`)
│   ├── index.py                   # SpatioTemporalIndex value object + alignment
│   ├── spatial_level.py           # SpatialLevel enum (cm/pgm) — relocated here
│   ├── protocols.py               # Frame / SpatioTemporalIndexed / Sampled / Persistable
│   ├── _validation.py             # shared construction-time invariants (private helper)
│   ├── feature_frame.py           # FeatureFrame              ── one concept per file
│   ├── prediction_frame.py        # PredictionFrame
│   ├── target_frame.py            # TargetFrame
│   ├── conformance/               # the published contract suite consumers re-run (§9)
│   └── io/                        # serialization adapters — SEPARATE from frames (SRP)
│       ├── __init__.py
│       ├── npz.py                 # native save()/load() (.npy + .npz)
│       └── arrow.py               # flat columnar (.parquet) — the scalable disk format
├── src/views_frames_summarize/    # sample-axis summarization OVER frames (ADR-017)
│   ├── __init__.py                #   depends on views_frames + numpy only; never the reverse
│   ├── collapse.py                # collapse(frame, reducer) — generic point fold
│   ├── point.py                   # map_estimate (histogram MAP)
│   ├── interval.py                # hdi, quantiles  → arrays aligned to the frame index
│   └── aggregate.py               # conservation-correct cross-level aggregation
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
(C-40/C-66), and ~50–160× per-row over dense float32 in the #181 report-stage
investigation (C-186).
`views-frames` standardizes two scalable formats and **bans list-in-cell**:

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
2. **Relocate `PredictionFrame` here (contract-preserving, but _not_ verbatim).**
   `PredictionFrame` today **imports pandas** and uses `pd.isna` for its identifier
   NaN-check (`prediction_frame.py:5,68`); §3.1 forbids pandas in the core, so the
   move is **not a verbatim copy — its identifier validation is rewritten
   numpy-only** (the observable contract from §4.1 is preserved; the implementation
   is not). Re-export from `views-pipeline-core/data/prediction_frame.py` as a thin
   shim (`from views_frames import PredictionFrame`) so existing imports keep
   working.
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
arrays) and **C-186** (the #181 report-stage OOM — the first observed-in-production
instance of that blow-up), **C-48** (concrete dependencies → protocols), **C-135** (private-internal
cross-repo leakage → published interface), **C-164** (unwired `DataFetchStrategy`
— frames give the strategy a typed payload), **C-165** (stable package, zero
abstractions — this *is* the abstraction), **C-167** (reconciliation I/O has no
typed contract → frame I/O contract), **C-184** (cross-repo mutation of
`reconciled_dataframe` → immutable frames). Keystone for views-reporting **#113**
(circular dependency) and informs **D-28** (relocate reconciliation) and **D-33**
(collapse the `CMDataset/PGMDataset` hierarchy into a `SpatialLevel` value).

From the **views-reporting** consumer (its own register) this package *forbids* its
**C-184** (the `reconciled_dataframe` mutation) and the reporting side of
**C-135** (private `_entity_id`/`_time_id` reads → published index protocol), and
*enables* fixing **C-48** (wandb eval scrape → a typed `MetricFrame`) and **C-44**
(undeclared wandb → isolated to one consumer adapter). It does **not** by itself
resolve **C-22** (viewser metadata fetch) or **C-27** (wandb runtime dependency) —
those remain consumer-side acquisition concerns; `views-frames` only gives their
output a typed home. (Note: reporting's **C-48** is distinct from the
pipeline-core **C-48** listed above — two registers, same number.)

---

## 13. Design decisions

### 13a. Resolved (ratified 2026-06-21 — these were the blocking pre-code decisions)

1. **Twin-unification model — Option C.** Unify only the shared
   `SpatioTemporalIndex` + `_validation` + protocols + `io/`; relocate
   `FeatureFrame`/`PredictionFrame` as **separate sibling classes**. Reject the
   shared `_BaseFrame` (Option A); defer the composed header (Option B) until a
   third frame proves it. See §5.
2. **Sample axis — decided: always an explicit trailing axis (`S ≥ 1`).**
   `PredictionFrame (N, S)`, `FeatureFrame (N, F, S)`, `TargetFrame (N, 1)`;
   `is_sample` is `S > 1`; sample-axis reduction lives in
   `views_frames_summarize` (point 7), not the leaf. One shape contract, no
   `ndim` branching. See §4.1.
3. **Metadata / identifier model — typed header + fixed identifiers.** `metadata`
   is a **typed, optional-extensible header** (not a free-form dict — that re-opens
   C-48 store-side and cannot be validated), carrying provenance (model, run_type,
   timestamp, seed) and `feature_names`. Identifiers stay a fixed required
   `{time, unit}` for v1; any future identifier (`step`, `origin`, `scenario`) is
   added as **optional only** (MINOR), never required (a required identifier is the
   §8 MAJOR break). This is the typed home for the C-48 / #178 run-identity cure.
4. **Cross-level (cm↔pgm) alignment — leaf owns the protocol, consumer injects the
   mapping.** Same-level alignment lives in the leaf; the cross-level country↔grid
   join needs a viewser-sourced, time-varying `priogrid→country` **mapping** that
   is **injected by the consumer and never embedded in the leaf**. The leaf owns
   only `cross_level_align(index, mapping)`. See §4.3; resolves the
   falsified "domain-free cross-level" claim (a falsification audit, 5 hard falsifications).
5. **`SpatialLevel` lives here, as identifier vocabulary only** — relocated with
   the C-65 reversed index-tuple and the `priogrid_gid`/`priogrid_id`
   inconsistency **fixed, not ported** (§4.3). It carries the level labels, never
   the cross-level mapping or any unit values/ranges.
6. **`MetricFrame` / `EvaluationFrame` — out of the leaf.** `EvaluationFrame` stays
   in views-evaluation; `MetricFrame` is keyed `(target, step, unit)` and does not
   satisfy the §4 frame definition, so it stays **out of (the) leaf** for v1 (it
   may re-enter only if the index protocol is *deliberately* generalised to a
   non-spatiotemporal key — a v2 decision). The leaf may define the *key/index
   protocol* they conform to.
7. **Sample-axis summarization is a sibling package, not the leaf (ADR-017, v0.2.0).**
   `collapse`/MAP/HDI/quantiles and conservation-correct cross-level aggregation move
   to `views_frames_summarize` (numpy-only, depends on `views_frames`, import-DAG
   enforced). The leaf keeps only the *structural* `sample_count`/`is_sample`. This
   de-duplicates the HDI/MAP logic faoapi and reporting each re-derive, and keeps the
   leaf free of volatile statistics. (The older prose in §4.1/§5/§7/§9/§14 that lists
   `collapse` as a frame method predates this and is superseded by ADR-017.)

### 13b. Still open (lower-stakes, resolve at/around first code)

1. **Separate repo (this) vs. interim `views_pipeline_core/frames/` sub-package.**
   This scaffold assumes the separate repo (the SDP/SAP/REP end state, and the only
   thing that de-duplicates datafactory's `FeatureFrame`).
2. **`TargetFrame` vs `ActualsFrame` naming** (and whether targets/actuals are one
   type with a role flag).
3. **Minimum numpy version / typed-array (nptyping vs bare) policy.**
4. **Conformance-suite packaging** — it must ship as an importable artifact
   (installable subpackage / pytest plugin) with a governed **conformance-floor**
   version every consumer runs in CI regardless of its runtime pin (closes C-30
   without the version-coordination paradox).
5. **Owner + release cadence** — name the keystone's owner and the process for a
   MAJOR bump that must land across N repos at once (governance is otherwise the
   largest unaddressed cost for a leaf this many repos import).

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
- **Sample axis (S):** posterior draws / ensemble members; reduced by
  `views_frames_summarize` (e.g. `collapse(frame, reducer)`), not the leaf.
- **list-in-cell:** the banned `object`-dtype encoding (a DataFrame cell holding a
  Python list of samples); the actual non-scaler.

---

*Build against this document. If the code and this README disagree, that is a bug
in one of them — reconcile before merging.*
