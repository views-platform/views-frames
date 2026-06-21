# views-frames — Review (round 01)

> **Reviewer:** Claude (Opus 4.8), as an AI-agent developer who would *consume and
> extend* this package.
> **Date:** 2026-06-21. **Reviewed at:** v0.2.0 (two-package release), branch `main`
> @ `07beefb`.
> **Method:** **read-only static inspection.** I read every source module under
> `src/` (both `views_frames` and `views_frames_summarize`), the
> README/CLAUDE.md/GOVERNANCE/CHANGELOG, the ADR set and risk register, the CIC set,
> the prior falsification critiques, and the test suite — and traced the construct →
> reduce → save/load → conformance path by reading, not running. I did **not** execute
> `pytest`/`mypy`/`ruff` in this pass (doing so writes cache directories, outside the
> single permitted write); where this report discusses those gates it does so from
> *static reading of the code and config*, and treats **CI as the authority** on
> pass/fail. Read-only: **no source modified, nothing staged, no commit, no branch.**
> The only file written is this report.
>
> **One-line verdict:** A genuinely strong first version — clear purpose, disciplined
> code, executable architecture guarantees, and visible evidence that the earlier
> falsification finding (`critiqus/critique_02.md`) was *actually fixed* in code + ADR +
> README. It is held back from "ship-ready for consumers" by a small number of concrete
> gaps: a missing `py.typed`, no runnable usage examples, a type-annotation pattern
> worth confirming against the declared numpy floor, and three sample-/scale-sensitive
> Python loops in code whose whole purpose is scale (two of the statistics paths, by
> contrast, *are* properly vectorized — so the issue is specific, not pervasive).

---

## 1. Does the repository do what I need it to do?

**Largely yes.** As an agent that would build a consumer adapter (e.g. a saver that
turns model output into a `PredictionFrame`, ships it, and reloads it), I can do that
today from the public API alone.

- **Purpose — exceptionally clear.** The README §0 thesis ("DataFrames are a
  boundary format, not internal transport; the canonical transport is array +
  spatiotemporal identifiers") is one paragraph and unambiguous. Every design choice
  in §1 is tied to a *named, observed* defect (the #181 OOM, the 22/25 wrong-run
  C-48, the `_ViewsDataset` god class). I rarely see a data-contract package whose
  motivation is this concretely grounded.
- **Structure — understandable at a glance.** Two packages under `src/`:
  `views_frames` (the leaf — `index`, `spatial_level`, `protocols`, `_validation`,
  three sibling frames, `io/`, `conformance/`) and `views_frames_summarize` (sample-
  axis statistics over frames). One concept per file; the file tree alone tells you
  the responsibilities, which is the stated goal of README §6 and it is met.
- **I can see how I'd use it.** Construct a `SpatioTemporalIndex(time, unit, level)`,
  wrap values in `PredictionFrame/FeatureFrame/TargetFrame`, `save`/`load` (npz or
  arrow), reduce samples with `views_frames_summarize.collapse/map_estimate/hdi`, and
  self-verify with `views_frames.conformance.assert_frame_contract`. The path is
  legible from source — though there is no runnable example to copy (see §3).
- **Abstractions — useful from an agent-dev perspective.** The combination of
  *fail-loud construction* + *typed `FrameMetadata`* + a *published, pytest-free
  conformance suite* is exactly what makes this safe for an agent to target: I can
  generate an adapter and have a deterministic, importable oracle
  (`assert_frame_contract(my_output())`) tell me whether I got the contract right.
  That is a first-class agentic affordance, not an afterthought.

**The one caveat:** the headline *consumer* win that motivates much of the README —
a typed evaluation output (`MetricFrame`) that fixes reporting's C-48 — is correctly
**deferred** (README §13a.6 / §4.2), so "what I need" as a *reporting* consumer is not
yet here. As a *producer/transport* consumer, everything I need is present. The
`FrameMetadata` fields are `model / run_type / timestamp / seed` — note for the
downstream reporting work that this does **not** yet carry `run_id` / `data_version` /
`code_revision`, which the views-reporting provenance footer (C-34) and the durable
C-48 fix will eventually want; that is a deliberate scope line here, not an oversight,
but it is worth naming because the README front-loads C-48 as motivation.

---

## 2. Does it do things the way I would want?

**Mostly yes, and in several places better than I'd expect.**

- **Interfaces are sensible and small.** `SpatioTemporalIndex` exposes exactly the
  alignment surface a reconciler needs (`intersect`, `searchsorted`/`reindex`,
  `is_superset_of`, `argsort`, `cross_level_align`). Frames expose `values`, `index`,
  `identifiers`, `n_rows`, `sample_count`, `is_sample`, `with_metadata`, `save`/`load`
  — nothing extraneous.
- **The immutability model is done right, including the hard part.** `with_metadata`
  returns a new frame that **shares** the values buffer, and the test suite asserts
  `np.shares_memory(...)`. The index stores read-only views (`index.py:43–44`,
  `setflags(write=False)`), and `coerce_values` uses `asanyarray` to preserve
  `np.memmap` on load. This is precisely the copy-vs-view discipline README §3.3
  promises and the antidote to the #181 blow-up — and it is *tested*, not just asserted
  in prose.
- **Architecture rules are executable, not decorative.** `tests/test_import_enforcement.py`
  walks the AST of every module and fails the build if the leaf imports
  `pandas/torch/viewser/...`, if `pyarrow` appears outside `io/`, if a foreign
  `views_*` is imported, or if a file declares >1 public class. This converts the
  README's "hard constraints" into CI-enforced invariants. This is the single most
  agent-friendly thing in the repo: the guardrails are machine-checked, so an agent
  contributor cannot silently violate the topology.
- **`CLAUDE.md` is excellent for an agent.** Exact `uv` commands, the hard
  constraints, the two-package map, and the "build against the README; if code and
  README disagree, reconcile" rule. This is the right shape for autonomous work.
- **Naming/modularity/docs are clear.** Module docstrings cite the ADR and register
  ID behind each decision, so the *why* travels with the code. Public re-exports are
  explicit (`__init__.py`), so the API is statically analyzable.

Where it diverges from what I'd want: the **protocol surface is thinner than the
README claims** (see §4/§6), the **typed contract isn't shipped to consumers** (no
`py.typed`, §6), and **three hot-path operations are Python-loop-bound** (§6) in a
package whose entire reason for existing is scale.

---

## 3. What is missing?

- **Runnable usage examples / a Quickstart (highest-value gap).** The README is a
  superb *design bible* (the "why") but contains **no runnable "how"** — no
  `examples/` directory, no Quickstart snippet, no usage in the package docstring.
  Today the fastest path to "how do I actually make a frame" is reading
  `tests/test_frames.py`. For a package meant to be adopted by N repos (and by
  agents), a ~15-line construct→reduce→save→load→conformance example in the README and
  an `examples/` script is the missing on-ramp.
- **`py.typed` marker (PEP 561) — absent (verified).** Neither
  `src/views_frames/py.typed` nor `src/views_frames_summarize/py.typed` exists. The
  package is fully annotated and `pyproject.toml` sets `mypy` `strict = true`, but with
  no marker, downstream consumers get **no types** from the package they depend on —
  defeating a major point of a typed contract. (Small fix, real impact; also needs the
  hatchling include so the marker ships in the wheel.)
- **A real consumer exercising the contract.** The conformance suite is run only
  against the *built-in* frames (`tests/test_conformance.py`), never yet against an
  external adapter. The cross-repo value proposition (one contract, N consumers) is
  **unproven** until at least one consumer (the Epic-3 pipeline-core/datafactory
  shims) runs `assert_frame_contract` against its own output. This is acknowledged as
  Epic 3, but it means the keystone's central claim is currently untested end-to-end.
- **An explicit `(time, unit)` uniqueness stance.** `validate_identifiers` checks
  integer dtype / length-N / completeness, but **not** that rows are unique per level.
  Same-level alignment (`searchsorted`, `intersect`) implicitly assumes uniqueness;
  duplicates would misalign **silently**. And `cross_level_align` *deliberately*
  produces duplicate `(time, country)` rows, later resolved by `aggregate_distributions`
  (`np.unique` + `np.add.at`) — so uniqueness can't be a global hard invariant. The
  package needs a documented position: either an optional uniqueness check on the
  same-level join inputs, or an explicit "frames may contain duplicate rows; these
  ops assume uniqueness" note. Right now it is an unstated assumption.
- **`MetricFrame` / index-protocol generalization.** Correctly deferred (§4.2 /
  §13a.6), but it is the piece that closes the reporting C-48 story the README leans
  on; nothing in code addresses it yet, and `FrameMetadata` does not yet carry the
  provenance fields (`run_id`/`data_version`/`code_revision`) the downstream report
  contract will need.
- **No benchmark / scale guard.** pipeline-core has a `test_report_stage_memory.py`
  guard for the very OOM this package targets; views-frames has no analogous
  memory/throughput guard for `io/arrow` round-trips or `cross_level_align` /
  `map_estimate` / `hdi` at full-grid size. For a package sold on scale, a guard test
  (even a coarse one) would protect the central claim — especially around the three
  Python-loop paths in §6.

---

## 4. What surprised me?

**Good surprises**
- **The falsification loop actually closed.** `critiqus/critique_02.md` proved the
  "domain-free leaf can do cross-level cm↔pgm alignment" claim *false*. The repo did
  not paper over it — it adopted exactly the salvage the audit proposed: leaf owns the
  *operation* (`SpatioTemporalIndex.cross_level_align`, `index.py:157`), consumer
  *injects the mapping*, ratified as ADR-014 and README §4.3/§13a.4, with the
  fail-loud "the leaf never guesses a mapping" raise (`index.py:181–193`). An audit
  finding landing this cleanly in code + ADR + README is rare and is the strongest
  signal the governance process here is real, not ceremonial.
- **Architecture invariants are AST-tested.** I expected prose; I found a build that
  fails on a forbidden import or a second public class in a file.
- **The conformance suite is pytest-free plain asserts.** That makes it genuinely
  portable into any consumer's CI — a thoughtful, consumer-first design.
- **The summarize split (ADR-017, v0.2.0).** Pulling volatile statistics
  (MAP/HDI/quantiles/aggregation) out of the stable leaf into a sibling, with the
  one-way dependency *enforced*, is a mature call most teams wouldn't make until
  forced. And the aggregation that matters most for scale —
  `aggregate_distributions` — **is** vectorized (`np.unique` + `np.add.at`,
  `aggregate.py:40–44`), which is the right instinct.

**Bad / unexpected surprises**
- **No `py.typed`** in a package whose entire value is a typed contract (§3) — the most
  surprising omission given how much else here is typed and strict.
- **A doc/code mismatch in the protocol surface.** README §5 states
  `SpatioTemporalIndexed` exposes `index: SpatioTemporalIndex`, but `protocols.py`
  exposes only `identifiers` + `n_rows` — **no protocol exposes `.index`** (verified
  by reading `protocols.py`). So a consumer typing against `Frame`/`SpatioTemporalIndexed`
  cannot statically reach `.index` (and thus `cross_level_align`), even though every
  concrete frame has it. The protocols are slightly under-powered relative to the
  alignment use-case they exist to serve.
- **A type-annotation pattern worth confirming against the numpy floor.** The
  identifier arrays are annotated as bare `NDArray[np.integer]` (e.g. `index.py:29,30,
  50,55,70`; the three frames; `_validation.py`). `pyproject.toml` declares `numpy>=1.26,
  <3` and `mypy` `strict = true` (which implies `disallow_any_generics`). Under strict,
  a bare generic like `np.integer` *can* trigger "Missing type parameters for generic
  type"; whether it does depends on the resolved numpy-stub version. **CI is green on
  its matrix, so this is not a live failure there** — but CI green on one resolved numpy
  does not guarantee the **declared 1.26 floor** is clean. This is worth an explicit
  check on numpy 1.26 (and, if it flags, a parameterized form such as
  `NDArray[np.integer[Any]]` or a project `IntArray` `TypeAlias`). *(I did not run mypy
  in this pass — this is a static observation, not a confirmed error count.)*

**Mildly unclear / harder than expected**
- The package isn't importable without `uv sync` / an editable install (or
  `PYTHONPATH=src`); a first-time `pytest` in a fresh shell would error with
  `ModuleNotFoundError: views_frames`. `CLAUDE.md` does say `uv sync` first, so this is
  documented — but a one-line "tests require `uv sync` / editable install" note near
  the test instructions would save a confused first run.
- Minor naming drift: README §4.3 mentions `align`/`reindex`, but only `reindex`
  exists (`index.py:133`, itself an alias of `searchsorted`) — there is no `align`
  method. Small doc-vs-code drift to reconcile.

---

## 5. Strongest parts

1. **The motivation-to-decision-to-code-to-test chain is intact and traceable.** Each
   constraint → an ADR → a code invariant → a test. The cross-level fix is the
   exemplar (critique → ADR-014 → `cross_level_align` → injected-mapping fail-loud
   raise + tests).
2. **Executable architecture.** Import-DAG and one-concept-per-file enforced by AST
   tests; immutability/zero-copy enforced by `np.shares_memory` assertions. The
   "hard constraints" are not honor-system.
3. **The published conformance suite** — importable, dependency-light, governed by a
   `CONFORMANCE_FLOOR` with a documented cross-repo bump process (`GOVERNANCE.md`).
   This is the right mechanism for the cross-repo contract-test gap.
4. **Agent-readiness of the docs.** `CLAUDE.md` + the design-bible README + ADRs +
   risk register give an agent everything needed to make a correct, in-bounds change,
   and a machine-checkable way to know it stayed in bounds.
5. **Disciplined scope.** The leaf refuses domain data, pandas, app logic, and even
   sample-axis statistics; `views_frames_summarize` and the (deferred) `MetricFrame`
   live outside. The boundary that the whole platform's de-duplication depends on is
   drawn precisely and defended in code.

---

## 6. Weakest parts

1. **No `py.typed`** — the typed contract isn't delivered to consumers despite full
   annotations and a strict mypy config. *(small fix, high priority)*
2. **Three sample-/scale-sensitive Python loops in a scale package** (all verified by
   reading source):
   - `cross_level_align` builds the remapped units with a Python comprehension of
     per-element dict lookups: `[mapping[int(u)] for u in self._unit]`
     (`index.py:187`). At full-grid scale (~10.5M rows, the #181 regime) this is an
     O(N) Python loop.
   - `map_estimate` (`point.py:25`) and `hdi` (`interval.py:22`) use
     `np.apply_along_axis` — a Python-level per-row loop — for the exact report-stage
     reduction that #181 runs over the full grid.
   - **Credit where due:** `quantiles` (`interval.py:28`, `np.quantile(..., axis=-1)`)
     and `aggregate_distributions` (`aggregate.py`, `np.unique` + `np.add.at`) **are**
     vectorized. So this is a *specific* throughput risk on three named paths, not a
     pervasive one. Memory (the stated win) looks fine; **throughput** is the risk, and
     no benchmark currently guards it. *(medium / architectural)*
3. **Type-annotation pattern unconfirmed on the numpy floor** (bare
   `NDArray[np.integer]` under `mypy --strict` / `disallow_any_generics`). Not a CI
   failure today; an unverified risk on the declared 1.26 lower bound. *(small, verify
   first)*
4. **Unstated `(time, unit)` uniqueness invariant.** Same-level joins assume it;
   nothing enforces or documents it; `cross_level_align` deliberately violates it
   pre-aggregation. A silent-misalignment hazard until the stance is written down.
   *(medium)*
5. **Protocol surface under-specified vs README §5 (no `.index` on any protocol).**
   Consumers typing to the abstractions can't statically reach the index/alignment
   they're meant to. *(small-medium)*
6. **Central claim untested end-to-end** — no real consumer runs the conformance suite
   yet (Epic 3). *(tracked, but it is the gap between "looks right" and "proven")*

---

## 7. What should be improved next (prioritized)

### Small fixes (hours; do these before any consumer adopts)

1. **Add `src/views_frames/py.typed` and `src/views_frames_summarize/py.typed`** and
   ensure hatchling ships them, so downstream `mypy` sees the types.
2. **Confirm `mypy --strict` on the numpy floor (1.26), then fix if needed.** Run the
   gate in a numpy-1.26 environment; if the bare `NDArray[np.integer]` annotations flag
   under `disallow_any_generics`, replace with a parameterized form
   (`NDArray[np.integer[Any]]` or a project `IntArray`/`Float32Array` `TypeAlias` in
   one module) across `index.py`, `protocols.py`, `_validation.py`, and the three
   frames. This closes the "CI-green-on-matrix ≠ floor-is-clean" gap.
3. **Add a Quickstart to the README and an `examples/` script** — construct an index +
   each frame, `collapse`/`map_estimate`/`hdi`, `save`/`load` (npz and arrow), and
   `assert_frame_contract`. ~15 lines; it is the missing on-ramp for humans and agents.
4. **Reconcile the protocol surface with README §5** — either add `index` (and the
   members consumers actually need for `cross_level_align`) to the protocols, or
   correct §5 to match `protocols.py`. Pick one and make doc==code.
5. **Documentation hygiene:** drop the `align` reference from §4.3 (only `reindex`
   exists); add a one-line "tests need `uv sync`" note by the test commands.

### Larger / architectural (sequence deliberately)

6. **Vectorize the three scale paths and add a guard.** Replace the `cross_level_align`
   comprehension with a vectorized remap (build a max-keyed lookup array, or
   `np.unique` + `searchsorted` on the mapping keys); evaluate vectorizing
   `map_estimate`/`hdi` (or document the per-row cost as accepted). Add a coarse
   throughput/memory guard test for `io/arrow` round-trip and `cross_level_align` /
   `map_estimate` at representative grid size — the analogue of pipeline-core's
   `test_report_stage_memory.py`. The package is sold on scale; prove it.
7. **Decide and document the `(time, unit)` uniqueness invariant.** Recommended:
   frames permit duplicates (needed for pre-aggregation), but same-level join methods
   gain an optional `assume_unique`/validated path, and the stance is stated in the
   `SpatioTemporalIndex` docstring and the conformance suite.
8. **Prove the contract with one real consumer (Epic 3).** Land the pipeline-core
   `PredictionFrame` re-export shim and have pipeline-core's CI run
   `views_frames.conformance.assert_frame_contract` against its own adapter output.
   Until one consumer does this, the keystone's cross-repo value is asserted, not
   demonstrated. This is the highest-value *next* milestone after the small fixes.
9. **Schedule `MetricFrame` / the key-protocol generalization** (the reporting C-48
   cure) as an explicit, dated item rather than "exploratory," since the README
   front-loads C-48 as motivation. Decide where the provenance fields
   (`run_id`/`data_version`/`code_revision`) live — extend `FrameMetadata`, or carry
   them on the eventual `MetricFrame` in views-evaluation — and say so plainly, because
   the downstream views-reporting provenance footer (C-34) depends on the answer.

---

## Appendix — what I inspected

- **Source (all read):** `src/views_frames/{__init__,index,spatial_level,protocols,
  _validation,metadata,prediction_frame,feature_frame,target_frame}.py`,
  `io/{npz,arrow}.py`, `conformance/__init__.py`; `src/views_frames_summarize/
  {__init__,_common,collapse,point,interval,aggregate}.py`.
- **Docs:** README, CLAUDE.md, GOVERNANCE.md, CHANGELOG.md, the ADR set (incl.
  011–017), `reports/technical_risk_register.md`, the CIC set, and
  `critiqus/critique_02.md` (the falsification this version answers).
- **Tests (read, not run):** `tests/` — `test_frames`, `test_conformance`,
  `test_import_enforcement`, `test_index`, `test_io`, `test_properties`,
  `test_summarize_*`, and the `test_falsification_*` suite.
- **Method honesty:** This was a **static** review. I did **not** execute
  `pytest`/`mypy`/`ruff` (that writes cache directories, outside the one permitted
  write); CI is the authority on the green/red status of those gates. Findings about
  the type gate (§4/§6.3) are static observations to verify, not a measured error
  count. The verified-by-reading findings are: missing `py.typed`; the three
  Python-loop paths and the two vectorized ones; the protocol `.index` gap; the
  `align`-vs-`reindex` doc drift; the unguarded uniqueness assumption.
- **Not changed:** no source files, no staging, no commit, no branch. The working-tree
  changes visible in `git status` (the `perspectives/round00/` reorganization) were
  **pre-existing** and not made by this review; the only file this review wrote is this
  report.
