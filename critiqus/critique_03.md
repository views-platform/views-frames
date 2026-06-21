# Critique 03 — `views-frames`: falsification pass (evidence for 00/01)

> **What this is:** a Popperian `/falsify` audit (pass 2) against the *load-bearing
> claims* of the `views-frames` design, run 2026-06-20. Where `critique_00.md` and
> `critique_01.md` are reasoned reflections, this document is the **evidence layer**:
> each finding is grounded in the *real referenced code* in the sibling repos and is
> backed by a failing test stub in `views-frames/tests/`. Reviewer: Claude (Opus
> 4.8). The package has no code yet, so probes test (a) the design's internal
> consistency and (b) the actual implementations the design proposes to relocate.
>
> **Relationship to prior docs & to pass 1.** Pass 1 (`tests/
> test_falsification_domain_free_crosslevel.py`) falsified one claim — the
> domain-free cross-level index — with 5 hard findings. This pass widens the net to
> six claims and **confirms + extends** it. The findings here are the evidenced form
> of `critique_01.md` §2–§5 and `critique_00` §1–§6; read those for the design
> reasoning, this for the proof.

---

## 0. Verdict: **FALSIFIED** — 4 hard, 1 soft, 1 mixed

**Scope the verdict precisely — this is the important part.** The **core thesis
survives**: arrays-over-pandas as the canonical internal transport; a leaf-at-root
that breaks the pipeline-core↔reporting cycle (#113); the `SpatioTemporalIndex` as
the genuinely-reused primitive *for same-level alignment*; the #181/C-186 OOM root
cause. None of those broke under probing.

What **falsified is the as-stated specifics** — four of the design's load-bearing
claims are *not true as written*:

1. the "move `PredictionFrame` **verbatim**" migration step (§10.2) is impossible as stated;
2. the "**near-1:1** twins" characterisation oversells a structural divergence;
3. the index/alignment core cannot be **numpy-only and domain-free** *and* deliver the cm↔pgm join consumers require;
4. the design **omits ownership/release governance** for a leaf N repos import.

Plus one soft (immutability vs copy-cost is unspecified) and one mixed
(`SpatialLevel` relocates numpy-clean but ports two bugs; `MetricFrame` is not
frame-shaped). **The idea is sound; its migration mechanics and several specific
claims are disproven.**

---

## 1. Claims under test

| ID | Claim (README / perspectives) | Source |
|----|-------------------------------|--------|
| C1 | "`FeatureFrame` and `PredictionFrame` are near-1:1 twins" | §1, §4.1 |
| C2 | the `SpatioTemporalIndex` / alignment core is "numpy-only, no internal/domain dependency" (incl. cm↔pgm) | §3.1, §4.3 |
| C3 | "move `PredictionFrame` verbatim" **and** "unify the twins" **and** "defer the sample-axis decision" all hold | §10.2 vs §4.1 vs §13.6 |
| C4 | "immutable value objects (operations return new frames)" preserve the scaling thesis on the 9–18 GB tensors | §3.3 vs §7 |
| C5 | "numpy-only, imports nothing internal" survives relocating `SpatialLevel` + adding `MetricFrame` | §4.2, §4.3, §10.5 |

---

## 2. Probe results (evidence)

### P1 — C1 "near-1:1 twins" → **FALSIFIED (hard)**
The two real classes diverge on **≥6 axes**, several structural:

| Aspect | `PredictionFrame` (pipeline-core, 166 LOC) | `FeatureFrame` (datafactory, 220 LOC) |
|---|---|---|
| array | `y_pred (N, S)` — 2D only | `y_features (N, D)` or `(N, D, S)` — 2D/3D |
| **sample axis** | **axis 1, always present (S≥1)** | **axis 2, optional (absent when 2D)** |
| extra fields | none | `feature_names` (required), `metadata` |
| identifier NaN-check | **yes** (`pd.isna`, line 68) | **none** |
| reductions | `collapse()` → `(N,1)` | none |
| load | `mmap=` supported | no mmap |
| other methods | — | `from_grid()`, `is_sample`, `n_features` |
| save footprint | `y_pred.npy` + `identifiers.npz` | + `feature_names.json` + `metadata.json` |
| core dep | **imports `pandas`** | numpy + json only |

The sample-axis *position* mismatch alone makes "near-1:1" misleading: a single
unified type cannot host axis-1-always and axis-2-optional without first deciding a
convention. Evidence: `views-pipeline-core/.../data/prediction_frame.py`;
`views-datafactory/src/datafactory_adapters/feature_frame.py`.
Stub: `tests/test_falsification_twin_parity.py::test_falsify_tp_03_*`.

### P2 — C2 numpy-only / domain-free cross-level → **HARD FALSIFIED** (confirms pass 1)
The cm↔pgm (country↔grid) join the consumers explicitly ask the index for
(pipeline-core ask #3, reporting ask #2) is built from **external, viewser-sourced,
*time-varying* domain reference data** — not from `(time, unit)` integer arrays:

- `views-reporting/.../reconciliation/dataset_export.py:106-107`:
  `build_country_to_grids_cache(pg_dataset)` →
  `pg_dataset._country_to_grids_cache.get(country_id, [])`.
- `build_country_to_grids_cache` (`views_reporting.metadata`) derives
  `priogrid_gid → country_id` from a viewser `Queryset("pg_metadata",
  "priogrid_month")` and handles **`previous_country_id`** — a cell's country
  assignment changes by month (border changes).

So the join needs *temporally-versioned domain data*. A numpy-only, domain-free,
maximally-stable leaf cannot deliver it; embedding it violates §3/§11; fetching it
violates §3. The boundary (leaf vs consumer vs reference package) is undecided
(§13). Stub: `tests/test_falsification_domain_free_crosslevel.py` (pass 1, 5 hard).

### P3 — C3 verbatim + unify + defer → **HARD FALSIFIED** (smoking gun)
Two independent contradictions:

1. **`PredictionFrame` imports `pandas`** (`prediction_frame.py:5`; `pd.isna` at
   `:68`). README §3.1 forbids pandas in the core; §10.2 says "move verbatim."
   Both cannot hold — the move requires a numpy-only rewrite of the validation, so
   it is **not verbatim**.
2. The **sample-axis position differs** between the twins (P1), so "unify the
   twins" *requires* the §13.6 sample-axis decision — it **cannot be deferred**.

Stub: `tests/test_falsification_twin_parity.py::{test_falsify_tp_01,test_falsify_tp_02}`.

### P4 — C4 immutability vs scaling → **SOFT FALSIFIED** (omission)
The existing code is memory-safe where it exists: `PredictionFrame.collapse`
(`:86-116`) allocates a *reduced* `(N,1)` array and copies only the small identifier
arrays; `load(mmap=True)` (`:135-159`) returns a read-only memmap and `__init__`
preserves the `np.memmap` subclass (`:35-41`). **But** §3.3 ("operations return new
frames") is **silent on copy-vs-view** for the anticipated `select`/`with_metadata`
ops. On the 9–18 GB #181 tensors a naive new-frame-per-op that copies `values`
reintroduces the exact blow-up §7 exists to kill. Immutability (correctness; forbids
C-184) and zero-copy (scaling) must be reconciled in the contract.
Stub: `tests/test_falsification_immutability_copy.py`.

### P5 — C5 numpy-only survives `SpatialLevel` + `MetricFrame` → **MIXED**
- **`SpatialLevel` SURVIVES the numpy test** (`domain/spatial.py` is stdlib `enum`
  only) — but relocating it *verbatim* ports two defects into the keystone:
  1. **C-65 reversed tuple**: `_INDEX_NAMES[PGM] = ("priogrid_gid", "month_id")` and
     `[CM] = ("country_id", "month_id")` are **entity-first**, while all real
     DataFrames are `(month_id, entity)` — **time-first**.
  2. **Internal inconsistency**: `index_names` uses `priogrid_gid` (pre-rename)
     while `entity_column` uses `priogrid_id` (post-rename) — the same value object
     disagrees with itself across the priogrid rename boundary.
- **`MetricFrame` is HARD-falsifying**: §4 defines a frame as "an array whose first
  axis is N rows carrying `{time, unit}`." `MetricFrame` (§4.2) is `(K, …)` keyed by
  `(target, step, unit)` — a different first-axis meaning. It does **not** satisfy
  the frame definition; hosting it breaks §4 or makes the leaf a junk drawer.
  (`EvaluationFrame` already owns eval-output vocabulary in views-evaluation.)

Stub: `tests/test_falsification_spatiallevel_and_metricframe.py`.

### P6 — adequacy: governance omission → **HARD FALSIFIED (adequacy)**
§8 specifies SemVer *mechanics* but **no named owner, release cadence, or process
for a MAJOR bump that must land across 6 repos at once**. For a package whose entire
value is "a stable leaf everyone depends on," omitting the ownership/coordination
model is a topic the artifact's purpose requires — a reviewer would reject for it.
(Report-only per the hybrid stub policy; see `critique_01.md` §2.5, §3.4, §3.7.)

---

## 3. Pattern analysis (cross-cutting)

1. **The README describes the destination, then claims it as the origin.** "Verbatim
   move," "near-1:1," "defer sample-axis" all assume the real code already matches
   the contract. It doesn't — `PredictionFrame` imports pandas, `FeatureFrame` skips
   NaN-checks, the sample axes don't align. The migration is planned against an
   idealised version of the code being migrated.
2. **The leaf keeps absorbing things that aren't leaf-shaped.** Cross-level
   alignment (domain + temporal data), `MetricFrame` (different key space),
   `SpatialLevel` (carries domain-boundary bugs). Every place a consumer's *real*
   need is domain-bound, the "pure-numpy stable leaf" boundary is breached.
3. **Relocation ≠ cleanup.** "Move `SpatialLevel` here" ports C-65 + the gid/id
   inconsistency; "move `PredictionFrame` verbatim" ports pandas. The design treats
   relocation as free; each move drags latent defects into the keystone — the worst
   place for them to live.

---

## 4. Failing test stubs (the evidence as guards)

All RED (TDD): they assert against the design docs + cite the sibling-repo evidence,
and go green only when the README resolves each decision. Hybrid policy: stubs for
code-checkable findings; P3-logic and P6-adequacy are report-only (the *pandas-import*
facet of P3 is captured in the twin-parity stub).

| File | Probes | Findings encoded |
|------|--------|------------------|
| `tests/test_falsification_domain_free_crosslevel.py` *(pass 1)* | P2 | cross-level needs viewser-sourced, time-varying domain data |
| `tests/test_falsification_twin_parity.py` | P1, P3 | pandas-in-core; sample-axis-before-unify; precise twin deltas |
| `tests/test_falsification_immutability_copy.py` | P4 | copy-vs-view unspecified vs the scaling thesis |
| `tests/test_falsification_spatiallevel_and_metricframe.py` | P5 | SpatialLevel ports C-65 + gid/id mismatch; MetricFrame not frame-shaped |

---

## 5. Register-format findings (for `register-risk` — not yet registered)

> **F-01 — `PredictionFrame` "verbatim move" is self-contradictory (Tier 2).**
> *Trigger:* a developer executes README §10.2 ("move `PredictionFrame` here
> verbatim") into the numpy-only leaf. *Location:* `prediction_frame.py:5,68`
> (`import pandas`, `pd.isna`); README §3.1 vs §10.2. *Narrative:* the core type
> imports pandas; a verbatim relocation violates the leaf's own no-pandas
> constraint, so the migration's first step is internally contradictory until
> PF's identifier validation is rewritten numpy-only. Mislabels a behaviour change
> as a no-op move.

> **F-02 — cm↔pgm alignment needs temporally-versioned domain data the leaf forbids (Tier 2).**
> *Trigger:* `SpatioTemporalIndex`/`SpatialLevel` is built to deliver the cm↔pgm
> join its consumers ask for. *Location:* `views-reporting/.../reconciliation/
> dataset_export.py:106-107`; `views_reporting.metadata.build_country_to_grids_cache`
> (viewser `pg_metadata`, `previous_country_id`). *Narrative:* cross-level alignment
> requires viewser-sourced, month-varying `priogrid→country` reference data; a
> numpy-only domain-free leaf cannot provide it, so the join must live in a consumer
> or a separate reference package — an undecided boundary (README §13) that, if
> resolved by embedding the mapping, silently turns the leaf into a domain package.

> **F-03 — relocating `SpatialLevel` ports C-65 + a gid/id inconsistency (Tier 3).**
> *Trigger:* §10.5 relocates `SpatialLevel` "here." *Location:*
> `views-pipeline-core/.../domain/spatial.py` (`_INDEX_NAMES` reversed/entity-first;
> `index_names` `priogrid_gid` vs `entity_column` `priogrid_id`). *Narrative:*
> moving it as-is ships a wrong-order index contract and a self-inconsistent
> identifier name into the keystone every repo imports.

---

## 6. What this changes in the plan

The blocking recommendations in `critique_01.md` §7 now have hard evidence behind
them — promote them from "advisable" to "required before any relocation":

1. **Rewrite `PredictionFrame`'s validation numpy-only and stop calling the move
   "verbatim"** (F-01).
2. **Close the sample-axis convention before unifying** — it is structurally forced,
   not deferrable (P1/P3).
3. **Decide the cross-level boundary explicitly** and keep the domain mapping out of
   the leaf (F-02): same-level alignment in; country↔grid in a consumer/reference
   package.
4. **Specify copy-vs-view semantics** and pin them in conformance (P4).
5. **Fix-don't-port `SpatialLevel`** (F-03) and **exclude `MetricFrame`** from the
   leaf (P5).
6. **Name an owner + cross-repo release/bump process** before the second consumer
   adopts (P6).

---

*Falsification is destructive testing: surviving probes raise confidence, they do
not prove truth. The core thesis survived; four specific claims did not. No source,
config, or register was changed — only this critique and the RED test stubs under
`views-frames/tests/` were written.*
