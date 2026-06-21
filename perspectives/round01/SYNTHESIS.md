# Round-01 reviews — synthesis, fact-check, and reflection

> **What this is:** an investigation → review → reflection over the six round-01
> reviews in `perspectives/round01/` (views-datafactory, views-pipeline-core,
> views-faoapi, views-reporting, views-postprocessing, views-appwrite), all of
> `views-frames` **v0.2.0** (`main` @ `07beefb`).
>
> **What this is *not*:** a change. Every finding below was fact-checked by reading
> the actual code or running the toolchain — **not** by trusting the reviewers. No
> code, register entry, ADR, or sibling repo was modified. Fixes are *recommended*
> here as a proposed **Epic 4**; nothing is applied.
>
> Reviewer: Claude (Opus 4.8), 2026-06-21.

---

## 1. Verdict

**The design is validated; the gaps are real but bounded.** Six independent agent
reviews, from six different consumer/sibling vantage points, **unanimously affirm the
ratified design** — ADRs 011–017, the scope rule (transport-not-analysis), the
two-package split (ADR-017), the conformance suite, and the immutability/zero-copy
model. **Not one review challenges a resolved decision.** That convergence is the
single highest-signal result: the contested scoping calls (Option C, the cross-level
boundary, pulling statistics into `views_frames_summarize`) landed correctly under
adversarial inspection.

The value is in the *gaps*. Fifteen distinct findings were raised; **all fifteen were
confirmed** against the code (zero refuted). They fall into five buckets: **type
delivery** (a real `mypy --strict` failure at the numpy floor + missing `py.typed`),
**doc↔code drift** (protocol surface, stale README), **one substantive implementation
gap** (`cross_level_align` under-delivers its own ADR), **scale-proof** (three per-row
loops, no guard), and **deferred decisions** (provenance, `MetricFrame`, `select`).

The two that matter most: **F2** — the package fails its *own* `mypy --strict` gate at
its *own* declared numpy floor (CI hid it); and **F6** — `cross_level_align` takes a
*static* mapping while ADR-014/critique_02 (the very falsification that produced it)
specify a *time-varying* one.

---

## 2. What the six reviews validate (the affirmations)

These were asserted by multiple reviewers and re-confirmed here. They need **no action**
— recording them so the wins are on the record:

- **Governance loop is real, not ceremonial** (6/6). The cross-level falsification
  (critique_02 → ADR-014 → `cross_level_align` injected-mapping fail-loud raise) is
  cited by every reviewer as the proof that critique→ADR→code→test actually closes.
- **Executable architecture** (6/6). `tests/test_import_enforcement.py` AST-walks both
  packages and fails the build on a forbidden import or >1 public class per file; the
  two-package DAG (`views_frames` ⇏ `views_frames_summarize`) is machine-checked.
- **Immutability done right, including the hard part** (6/6). `with_metadata` shares the
  buffer (`np.shares_memory` asserted, `test_frames.py`), `coerce_values` uses
  `np.asanyarray` so `mmap` survives load, index arrays are read-only views.
- **Disciplined, defended scope** (6/6). The leaf refuses pandas/domain/app-logic/
  statistics; ADR-017 pulling volatile statistics into the sibling with one-way
  enforcement is called "a mature move most teams wouldn't make until forced."
- **Conformance suite** (6/6): pytest-free plain-assert, genuinely portable into a
  consumer's CI; governed by `CONFORMANCE_FLOOR`.
- **`aggregate_distributions` is correct** (faoapi/reporting): `np.add.at` joint-sampling
  preserves sample alignment, and the test guards `HDI(sum) ≠ sum(HDI)` (the C-70 trap).
- **Purpose + structure legible** (6/6): README §0 thesis tied to named defects; two
  packages, one concept per file, ~1.3k LOC; `CLAUDE.md` is "agent-ready."

---

## 3. Fact-checked findings ledger

Verdict key: **CONFIRMED** (real, actionable) · **DECISION** (needs a call, not a bug) ·
**CROSS-REPO** (sibling change — the user's, not mine). No finding was refuted.

| # | Finding | Src | Verdict | Grounded note (what I actually checked) |
|---|---------|-----|---------|------------------------------------------|
| **F2** | `mypy --strict` red at the **numpy floor** | 4/6 | **CONFIRMED (bug)** | Ran `uv run --with numpy==1.26.4 mypy --no-incremental --strict src/` → **exactly 14 errors** (`Missing type arguments for generic type "integer"`) in 8 files. CI is green only because it resolves numpy **2.4.6**, whose stubs don't flag bare `NDArray[np.integer]`. The package fails its own gate at its own floor. |
| **F6** | `cross_level_align` is **static**, but ADR-014 specifies a **time-varying** mapping | 1 (sharp) | **CONFIRMED (substantive)** | `index.py:159` signature is `mapping: Mapping[int, int]`; body `:187` is `[mapping[int(u)] for u in self._unit]` — **time is ignored**. ADR-014 line 83: "The `mapping` parameter is `(time, priogrid) → country` (time-aware)"; critique_02 establishes a cell's country changes by month (`previous_country_id`). The docstring even says "time-varying" while the type can't express it. **The code contradicts its own ADR.** faoapi (the real consumer) is right to call this adoption-gating. |
| F1 | No `py.typed` marker | 6/6 | **CONFIRMED** | Absent in both `src/views_frames/` and `src/views_frames_summarize/`. Consumers' `mypy` treats the package as untyped despite full annotations + `mypy --strict` config. |
| F4 | Protocol surface ↔ README §5 mismatch | 6/6 | **CONFIRMED** | `protocols.py` `SpatioTemporalIndexed` exposes only `n_rows` + `identifiers`; **no** protocol exposes `index` or `cross_level_align`. README §5 line 266 claims `SpatioTemporalIndexed` exposes `index: SpatioTemporalIndex`. A consumer typing to the abstraction can't reach alignment. |
| F5 | Three per-row Python loops; no scale guard | 5/6 | **CONFIRMED (specific, not pervasive)** | `cross_level_align` comprehension (`index.py:187`), `map_estimate` (`point.py:25`) and `hdi` (`interval.py:22`) use `np.apply_along_axis`. **Credit:** `quantiles` (`np.quantile axis=-1`) and `aggregate_distributions` (`np.unique`+`np.add.at`) *are* vectorized. No throughput/memory guard test exists (analogue of pipeline-core's `test_report_stage_memory`). |
| F7 | `(time, unit)` uniqueness stance unstated | 5/6 | **CONFIRMED (silent-hazard)** | `validate_identifiers` checks dtype/length/completeness, **not** uniqueness (grep: no `uniqu`/`duplicate` anywhere). Same-level joins (`intersect`/`searchsorted`) assume uniqueness; `cross_level_align` deliberately produces duplicate `(time, target_unit)` rows. Duplicates would misalign silently; the stance is undocumented. |
| F8 | README version-header drift | 1 | **CONFIRMED** | README §0 line 7 still says "**implemented — v0.1.0** (Epic 2)"; the package is v0.2.0 (Epic 3). Violates the repo's own "code/README disagree = bug" rule. |
| F9 | Stale README prose | 4/6 | **CONFIRMED** | §4.3 line 225 lists "`align`/`reindex`" but only `reindex` exists (`index.py:133`); glossary §14 line 554 (and line 493) still says "`collapse` reduces it" though `collapse` moved to the summarize package in v0.2.0. |
| F3 | No examples / Quickstart | 6/6 | **CONFIRMED** | No `examples/`; README has no runnable on-ramp. The only path to "make a frame" is reading the tests. |
| F10 | `FrameMetadata` lacks durable provenance | 3/6 | **DECISION** | `metadata.py` carries `model`/`run_type`/`timestamp`/`seed` only — no `run_id`/`data_version`/`code_revision` (reporting C-34/C-48) or `source`/`version` (datafactory). This is the §13b / ADR-013 optional-extensible header working as designed; the *decision* (add now vs carry on a future `MetricFrame`) is open. |
| F11 | `MetricFrame`/key-protocol generalization "exploratory" | 3/6 | **DECISION** | README line 209 still marks it "exploratory." Schedule it explicitly: generalize the index protocol (v2) or state plainly it lives in views-evaluation. |
| F12 | No `select`/subset; no frame-level `reindex(other)->Frame` | 3/6 | **CONFIRMED (gap)** | No `select` in `src/`. Index `reindex`/`searchsorted` return position arrays, not frames; consumers hand-apply indexers to `.values`. |
| F13 | Arrow IO "half-integrated" | 2/6 | **CONFIRMED (ergonomics)** | `io/npz` is wired into frame `save`/`load`; `io/arrow` has no `save_parquet`/`load_parquet` frame methods — callers reconstruct from the state dict. |
| F14 | Minor naming/signature nits | 1 each | **CONFIRMED (minor)** | `searchsorted` (`index.py:117`) implements `get_indexer` semantics (-1 for missing), not numpy's; `Persistable.save(directory: str)` (`protocols.py:54`) is narrower than the concrete `save(directory: Path | str)`; `from_2d` docstring calls itself a "deprecated shim" though 2D is datafactory's normal producer output. |
| F15 | "Prove the contract with one real consumer" | 6/6 | **CROSS-REPO** | A re-export shim + `assert_frame_contract` in a consumer's CI. Requires changing a sibling repo — **out of bounds for me**; see §6. |

---

## 4. Deep-dive: F6 — the one place v0.2.0 under-delivers its own thesis

This is the only finding that touches correctness-of-contract rather than polish, and
it is sharp because the gap is *between the code and its own governance*:

- **ADR-014** (the decision): cross-level alignment needs a **time-varying**
  `(time, priogrid) → country` mapping "supplied by the caller" (line 83). The whole
  reason the leaf doesn't own it is that the mapping *changes by month*.
- **critique_02** (the falsification that produced ADR-014): the `priogrid→country`
  association "is time-aware … carries `previous_country_id` … the source data is
  `(time, priogrid) → country`."
- **The implementation** (`index.py:159,187`): `mapping: Mapping[int, int]`, applied as
  `[mapping[int(u)] for u in self._unit]`. **Time is dropped.** The signature cannot
  encode a cell whose country differs between months, so a caller with the real,
  month-varying mapping has no correct way to express it — and the docstring claims
  "time-varying" while the type forbids it.

So the leaf correctly *refuses to own the data* (ADR-014 honoured) but *mis-types the
operation it does own* (ADR-014 violated). faoapi — the consumer that actually performs
this join in production — flags it CRITICAL and adoption-gating; that is correct.

**The ADR does not need amending; the code does.** Recommended fix (Epic 4): widen the
parameter to a time-aware mapping — either `Mapping[tuple[int, int], int]` keyed by
`(time, unit)` (vectorizable via structured-key lookup) or an injected
`Callable[[NDArray, NDArray], NDArray]` `(time, unit) -> target_unit` — with a
conformance law and a time-varying test, and the same widening on
`aggregate_distributions`. Note this also *resolves F5's worst loop*: the vectorized
remap replaces the per-element comprehension.

---

## 5. Cross-cutting reflection

- **The reviews are an endorsement, not a redesign.** Six adversarial passes and zero
  ADR challenges means the hard scoping debates (especially the Epic-3 "is summarization
  scope creep?" reckoning) were resolved correctly. The package's *thesis* is sound; the
  work left is hardening, not rethinking.
- **The governance had exactly one hole, and it's instructive (F2).** "Executable
  architecture" was the package's proudest claim — yet the `mypy --strict` gate never
  ran at the declared numpy floor, so a 14-error type failure shipped green. The lesson
  isn't "the governance is fake" (it caught everything else); it's "a gate that doesn't
  run at the boundary it claims to cover isn't a gate there." Cheap to fix, important to
  internalize: the CI matrix should pin the floor for the type job.
- **Scale-sold vs three per-row loops (F5/F6) is the sharpest *tension*.** The package's
  motivating defect is the #181 OOM at ~10.5M rows, yet `map_estimate`/`hdi`/
  `cross_level_align` loop per row in Python with no scale guard. This isn't pervasive
  (quantiles + aggregation are vectorized), but it's exactly the report-stage reduction
  path #181 is about. Vectorize the three + add one representative-grid guard, and the
  "sold on scale" claim becomes proven rather than asserted.
- **Doc↔code drift (F4/F8/F9) is small but corrosive to an agent-targeted package.** The
  repo's own rule is "if code and README disagree, that's a bug." Three live
  disagreements (the `.index` protocol claim, the v0.1.0 header, the `align`/glossary
  prose) each cost an agent a wrong assumption. Cheapest, highest-trust fixes.
- **The deferred decisions (F10/F11/F12) are correctly deferred** — they're the
  `MetricFrame`/provenance cluster the design already parked in §13b, and the reviewers
  agree they're scope lines, not oversights. They become real when a consumer's C-34/C-48
  work forces them; schedule, don't pre-build.

---

## 6. Prioritized recommendations → proposed **Epic 4** (in-repo only)

All of the following are **inside views-frames**. None requires a sibling-repo change.

**Tier 1 — confirmed, cheap, ship first (trust + correctness of the gate):**
1. **Fix `mypy --strict` at the numpy floor (F2):** parameterize the 14 `NDArray[np.integer]`
   sites (e.g. a project `IntArray = NDArray[np.integer[Any]]` alias) **and** pin
   numpy==floor in the CI type job so the gate actually runs at the boundary.
2. **Ship `py.typed` (F1)** in both packages; confirm hatchling includes them.
3. **Doc↔code sync (F8/F9):** README §0 header → v0.2.0; drop the nonexistent `align`
   from §4.3; fix the §14/§13a glossary `collapse` lines (it lives in summarize now).
4. **Reconcile the protocol surface (F4):** either add `index` (and the members a
   consumer needs to reach `cross_level_align`) to `SpatioTemporalIndexed`/`Frame`, or
   correct README §5 to match `protocols.py`. Make doc == code.

**Tier 2 — substantive, in-repo:**
5. **Make `cross_level_align` time-aware (F6)** — widen the mapping to `(time, unit)`
   keyed (or an injected callable), vectorize the remap, add a time-varying conformance
   law + test; widen `aggregate_distributions` likewise. (Fixes F6 *and* F5's worst loop.)
6. **Vectorize `map_estimate`/`hdi` + add a scale-guard test (F5)** at a representative
   grid size (the analogue of pipeline-core's `test_report_stage_memory`).
7. **Decide + document the `(time, unit)` uniqueness stance (F7):** frames permit
   duplicates (pre-aggregation); same-level joins gain an optional `assume_unique`/
   validated path; state it in the `SpatioTemporalIndex` docstring + conformance suite.
8. **Add a Quickstart + `examples/` (F3):** ~15 lines — build an index + each frame,
   `collapse`/`map_estimate`/`hdi`, `save`/`load` (npz + arrow), `assert_frame_contract`.

**Tier 3 — decisions / deferred (Epic 5 candidates):**
9. `FrameMetadata` provenance fields (F10) — decide add-now vs carry-on-`MetricFrame`.
10. Schedule `MetricFrame`/key-protocol generalization (F11) — generalize vs hand to
    views-evaluation, explicitly.
11. `select`/subset + frame-level `reindex(other) -> Frame` (F12).
12. Arrow ergonomics: `save_parquet`/`load_parquet` frame methods (F13).
13. Minor naming/signature nits (F14): `searchsorted` → consider `get_indexer`;
    `Persistable.save` signature; `from_2d` "deprecated" wording.

**Cross-repo — F15 (handled BOTH ways, per the user's choice):**
- **Your migration (the real proof):** the highest-value next step is a consumer running
  `assert_frame_contract` in *its* CI. Concretely, in **one** consumer repo (you drive
  this — I will not touch sibling repos): add `views-frames` as a dep, re-export the
  relocated frame from a thin shim, and add a CI step calling
  `views_frames.conformance.assert_frame_contract(adapter_output())`. pipeline-core
  (`PredictionFrame`) or datafactory (`grid_to_feature_frame`) are the natural firsts.
- **In-repo proxy (interim de-risk, mine to do in Epic 4):** add a *synthetic* consumer
  test in views-frames that fabricates grid-like adapter output (a `[T,H,W,C]`→`(N,F,S)`
  flatten producing a `FeatureFrame`) and runs the conformance + summarizer contracts
  against it — proving the contract end-to-end without any sibling change.

---

## 7. Register / ADR candidates (recommendations only — **not applied**)

If you later run `register-risk`, these are the confirmed, register-ready findings:

- **C-19 (Tier 2)** — `mypy --strict` not enforced at the numpy floor; 14 `[type-arg]`
  errors at numpy 1.26.4, hidden by the CI resolving numpy 2.4. *Trigger:* when a
  consumer installs at the floor and runs its own type-check. *Location:* `index.py:29,30,50,55,70`,
  `protocols.py:26`, `_validation.py:24`, `io/npz.py:23,24`, `io/arrow.py:29,30`, frames.
- **C-20 (Tier 2)** — `cross_level_align` mapping is static `Mapping[int,int]` but
  ADR-014/critique_02 require a time-varying `(time, unit)→unit` mapping; the real
  cm↔pgm join is inexpressible. *Trigger:* when a consumer aligns a month-varying
  `priogrid→country` mapping. *Location:* `index.py:159,187`; `docs/ADRs/014…:83`.
- **C-21 (Tier 3)** — `(time, unit)` uniqueness is assumed by same-level joins but never
  validated/documented; silent misalignment on duplicates. *Location:* `_validation.py`, `index.py`.
- **C-22 (Tier 3)** — three per-row Python loops on the report-stage reduction path with
  no scale guard. *Location:* `index.py:187`, `point.py:25`, `interval.py:22`.
- **C-23 (Tier 4)** — missing `py.typed`; doc↔code drift (protocol `.index`, README
  version header, `align`/glossary). *Location:* packages, `protocols.py`, README.

No **ADR amendment** is needed for F6 — ADR-014 is correct; the *implementation* must
match it. (Optionally clarify the ADR's `cross_level_align(index, mapping)` sketch to
show the `(time, unit)` key explicitly.)

---

## 8. Scope guard

- No sibling repo was read-written or modified. No `src/`, `docs/`, register, or ADR
  file was changed. The only artifact produced is **this document** under
  `perspectives/round01/`.
- Findings were verified by reading the code and **running** `mypy` at the numpy floor —
  not by trusting the reviewers. F2 (14 errors) and F6 (static vs time-varying) are
  confirmed by direct evidence above.
- The remediation (Epic 4) is **recommended, not started**; it awaits separate approval.
