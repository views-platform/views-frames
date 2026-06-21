# views-frames — Review (round 01)

> **Reviewer:** Claude (Opus 4.8), as an AI-agent developer who would *consume and
> extend* this package.
> **Date:** 2026-06-21. **Reviewed at:** v0.2.0 (two-package release).
> **Method:** read every source module under `src/`, the README/CLAUDE.md/GOVERNANCE/
> CHANGELOG, the ADR set and risk register, and the test suite; ran the suite
> (`PYTHONPATH=src pytest` → **83 passed**), `ruff check .` (**clean**), `mypy
> --strict src/` (**14 errors — see §6/§7**), and a construct→collapse→save/load
> smoke test (works). Read-only: **no source modified, nothing staged, no commit,
> no branch.** The only file written is this report.
>
> **One-line verdict:** A genuinely strong first version — clear purpose, disciplined
> code, executable architecture guarantees, and visible evidence that the earlier
> falsification finding (`critiqus/critique_02.md`) was *actually fixed*. It is held
> back from "ship-ready for consumers" by a small number of concrete gaps: a failing
> strict-type gate on the supported numpy floor, a missing `py.typed`, no runnable
> usage examples, and two scale-sensitive Python loops in code whose whole purpose is
> scale.

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
  self-verify with `views_frames.conformance.assert_frame_contract`. The smoke path
  worked first try.
- **Abstractions — useful from an agent-dev perspective.** The combination of
  *fail-loud construction* + *typed `FrameMetadata`* + a *published, pytest-free
  conformance suite* is exactly what makes this safe for an agent to target: I can
  generate an adapter and have a deterministic, importable oracle
  (`assert_frame_contract(my_output())`) tell me whether I got the contract right.
  That is a first-class agentic affordance, not an afterthought.

**The one caveat:** the headline *consumer* win that motivates much of the README —
a typed evaluation output (`MetricFrame`) that fixes reporting's C-48 — is correctly
**deferred** (§13a.6), so "what I need" as a *reporting* consumer is not yet here. As
a *producer/transport* consumer, everything I need is present.

---

## 2. Does it do things the way I would want?

**Mostly yes, and in several places better than I'd expect.**

- **Interfaces are sensible and small.** `SpatioTemporalIndex` exposes exactly the
  alignment surface a reconciler needs (`intersect`, `searchsorted`/`reindex`,
  `is_superset_of`, `argsort`, `cross_level_align`). Frames expose `values`, `index`,
  `identifiers`, `n_rows`, `sample_count`, `is_sample`, `with_metadata`, `save`/`load`
  — nothing extraneous.
- **The immutability model is done right, including the hard part.** `with_metadata`
  returns a new frame that **shares** the values buffer (`prediction_frame.py:86`),
  and `test_frames.py:103` asserts `np.shares_memory(...)`. mmap survives load
  (`io/npz.py:45`, `_validation.coerce_values` uses `asanyarray` to preserve
  `np.memmap`). This is precisely the copy-vs-view discipline README §3.3 promises and
  the antidote to the #181 blow-up — and it is *tested*, not just asserted in prose.
- **Architecture rules are executable, not decorative.** `tests/test_import_enforcement.py`
  walks the AST of every module and fails the build if the leaf imports
  `pandas/torch/viewser/...`, if `pyarrow` appears outside `io/`, if a foreign
  `views_*` is imported, or if a file declares >1 public class. This converts the
  README's "hard constraints" into CI-enforced invariants. This is the single most
  agent-friendly thing in the repo: the guardrails are machine-checked, so an agent
  contributor cannot silently violate the topology.
- **`CLAUDE.md` is excellent for an agent.** Exact `uv` commands, the six hard
  constraints, the two-package map, and the "build against the README; if code and
  README disagree, reconcile" rule. This is the right shape for autonomous work.
- **Naming/modularity/docs are clear.** Module docstrings cite the ADR and register
  ID behind each decision, so the *why* travels with the code. Public re-exports are
  explicit (`__init__.py`), so the API is statically analyzable.

Where it diverges from what I'd want: the **protocol surface is thinner than the
README claims** (see §6), the **typed contract isn't shipped to consumers** (no
`py.typed`, §6), and **two hot-path operations are Python-loop-bound** (§6) in a
package whose entire reason for existing is scale.

---

## 3. What is missing?

- **Runnable usage examples / a Quickstart (highest-value gap).** The README is a
  superb *design bible* (the "why") but contains **no runnable "how"** — no
  `examples/` directory, no Quickstart snippet, no usage in the package docstring.
  Today the fastest path to "how do I actually make a frame" is reading
  `tests/test_frames.py`. For a package meant to be adopted by N repos (and by
  agents), a 15-line construct→reduce→save→load→conformance example in the README and
  an `examples/` script is the missing on-ramp.
- **`py.typed` marker (PEP 561) — absent (verified).** The package is fully annotated
  and claims `mypy --strict`, but ships no `src/views_frames/py.typed`. Without it,
  downstream consumers get **no types** from the package they depend on — defeating a
  major point of a typed contract. (Small fix, real impact.)
- **A real consumer exercising the contract.** The conformance suite is run only
  against the *built-in* frames (`tests/test_conformance.py`), never yet against an
  external adapter. The cross-repo value proposition (one contract, N consumers) is
  **unproven** until at least one consumer (the Epic-3 pipeline-core/datafactory
  shims) runs `assert_frame_contract` against its own output. This is acknowledged as
  Epic 3, but it means the keystone's central claim is currently untested end-to-end.
- **An explicit `(time, unit)` uniqueness stance.** `validate_identifiers` checks
  integer dtype / length-N / completeness, but **not** that rows are unique per level.
  Same-level alignment (`searchsorted`, `intersect`) implicitly assumes uniqueness;
  duplicates would misalign **silently**. (And `cross_level_align` *deliberately*
  produces duplicate `(time, country)` rows, later resolved by
  `aggregate_distributions` — so uniqueness can't be a global hard invariant.) The
  package needs a documented position: either an optional uniqueness check on the
  same-level join inputs, or an explicit "frames may contain duplicate rows; these
  ops assume uniqueness" note. Right now it is an unstated assumption.
- **`MetricFrame` / index-protocol generalization.** Correctly deferred (§13a.6), but
  it is the piece that closes the reporting C-48 story the README leans on; nothing in
  code addresses it yet.
- **No benchmark / scale guard.** pipeline-core has a `test_report_stage_memory.py`
  guard for the very OOM this package targets; views-frames has no analogous
  memory/throughput guard for `io/arrow` round-trips or `cross_level_align` at
  full-grid size. For a package sold on scale, a guard test (even a coarse one) would
  protect the central claim.

---

## 4. What surprised me?

**Good surprises**
- **The falsification loop actually closed.** `critiqus/critique_02.md` proved the
  "domain-free leaf can do cross-level cm↔pgm alignment" claim *false*. The repo did
  not paper over it — it adopted exactly the salvage the audit proposed: leaf owns the
  *operation* (`SpatioTemporalIndex.cross_level_align`, `index.py:157`), consumer
  *injects the mapping*, ratified as ADR-014 and README §4.3/§13a.4, with the
  fail-loud "the leaf never guesses a mapping" raise. An audit finding landing this
  cleanly in code + ADR + README is rare and is the strongest signal the governance
  process here is real, not ceremonial.
- **Architecture invariants are AST-tested.** I expected prose; I found a build that
  fails on a forbidden import or a second public class in a file.
- **The conformance suite is pytest-free plain asserts.** That makes it genuinely
  portable into any consumer's CI — a thoughtful, consumer-first design.
- **The summarize split (ADR-017, v0.2.0).** Pulling volatile statistics
  (MAP/HDI/quantiles/aggregation) out of the stable leaf into a sibling, with the
  one-way dependency *enforced*, is a mature call most teams wouldn't make until
  forced.

**Bad / unexpected surprises**
- **`mypy --strict src/` fails on the supported numpy floor.** With numpy 1.26.4 (the
  declared floor, `pyproject.toml` `numpy>=1.26,<3`) and mypy 1.19, I get **14 errors**,
  all `Missing type parameters for generic type "integer"` (e.g. `index.py:30,50,55,70`,
  `prediction_frame.py:70`, `feature_frame.py:103`, `target_frame.py:69`). The
  annotations use bare `NDArray[np.integer]`; under `--strict` (`disallow_any_generics`)
  that needs a parameter. `CLAUDE.md` lists `uv run mypy src/` as a gate, so either CI
  resolves to a numpy whose stubs hide this or the strict gate is currently red on the
  lower bound of the supported range. Either way it should be verified and fixed.
- **No `py.typed`** in a package whose entire value is a typed contract (§3).
- **A doc/code mismatch in the protocol surface.** README §5 line 266 says
  `SpatioTemporalIndexed` exposes `index: SpatioTemporalIndex`, but `protocols.py`
  exposes only `identifiers` + `n_rows` — **no protocol exposes `.index`** (verified).
  So a consumer typing against `Frame`/`SpatioTemporalIndexed` cannot reach `.index`
  (and thus `cross_level_align`), even though every concrete frame has it. The
  protocols are slightly under-powered relative to the alignment use-case they exist to
  serve.

**Mildly unclear / harder than expected**
- The package isn't importable without `PYTHONPATH=src` or an editable install; a
  first-time `pytest` in a fresh shell errors with `ModuleNotFoundError: views_frames`.
  `CLAUDE.md` does say `uv sync` first, so this is documented — but a one-line "tests
  require `uv sync` / editable install" note near the test instructions would save a
  confused first run.
- Minor naming drift: README §4.3 mentions `align`/`reindex`, but only `reindex`
  exists (`index.py:133`); the glossary §14 still says "`collapse` reduces it" though
  collapse moved to the sibling (§13a.7 already flags this stale prose).

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
   This is the right mechanism for the cross-repo contract-test gap (C-30).
4. **Agent-readiness of the docs.** `CLAUDE.md` + the design-bible README + ADRs +
   risk register give an agent everything needed to make a correct, in-bounds change,
   and a machine-checkable way to know it stayed in bounds.
5. **Disciplined scope.** The leaf refuses domain data, pandas, app logic, and even
   sample-axis statistics; `views_frames_summarize` and the (deferred) `MetricFrame`
   live outside. The boundary that the whole platform's de-duplication depends on is
   drawn precisely and defended in code.

---

## 6. Weakest parts

1. **Strict-type gate red on the numpy floor** (`np.integer` missing type params, 14
   errors). A named quality gate that doesn't pass on a supported configuration is the
   most concrete weakness. *(small fix, high priority)*
2. **No `py.typed`** — the typed contract isn't delivered to consumers. *(small fix)*
3. **Two scale-sensitive Python loops in a scale package.**
   - `cross_level_align` builds the remapped units with a Python comprehension of
     per-element dict lookups: `[mapping[int(u)] for u in self._unit]`
     (`index.py:187`). At full-grid scale (~10.5M rows, the #181 regime) this is an
     O(N) Python loop.
   - `map_estimate` (`point.py:25`) and `hdi` (`interval.py:22`) use
     `np.apply_along_axis` — a Python-level per-row loop — for the exact report-stage
     reduction that #181 runs over the full grid.
   Memory (the stated win) is fine; **throughput** is the risk, and the package's
   credibility rests on the scale path. No benchmark currently guards it.
   *(medium / architectural)*
4. **Unstated `(time, unit)` uniqueness invariant.** Same-level joins assume it;
   nothing enforces or documents it; `cross_level_align` deliberately violates it
   pre-aggregation. A silent-misalignment hazard until the stance is written down.
   *(medium)*
5. **Protocol surface under-specified vs README §5 (no `.index` on any protocol).**
   Consumers typing to the abstractions can't reach the index/alignment they're meant
   to. *(small-medium)*
6. **Central claim untested end-to-end** — no real consumer runs the conformance suite
   yet (Epic 3). *(tracked, but it is the gap between "looks right" and "proven")*

---

## 7. What should be improved next (prioritized)

### Small fixes (hours; do these before any consumer adopts)

1. **Make `mypy --strict` green on the numpy floor.** Replace bare `NDArray[np.integer]`
   with a parameterized form (e.g. `NDArray[np.integer[Any]]` or a project
   `IntArray`/`Float32Array` `TypeAlias` in one module) across `index.py`,
   `protocols.py`, `_validation.py`, and the three frames. Then run the gate in a
   numpy-1.26 environment to confirm. *(Verifies the CI matrix's lower bound actually
   passes.)*
2. **Add `src/views_frames/py.typed`** (and `views_frames_summarize/py.typed`) and
   ensure hatchling includes them, so downstream `mypy` sees the types.
3. **Add a Quickstart to the README and an `examples/` script** — construct an index +
   each frame, `collapse`/`map_estimate`/`hdi`, `save`/`load` (npz and arrow), and
   `assert_frame_contract`. ~15 lines; it is the missing on-ramp for humans and agents.
4. **Reconcile the protocol surface with README §5** — either add `index` (and the
   `Sampled`/`Frame` members consumers actually need for `cross_level_align`) to the
   protocols, or correct §5 to match `protocols.py`. Pick one and make doc==code.
5. **Documentation hygiene:** add the `align` alias (or drop it from §4.3); fix the
   §14 glossary "`collapse` reduces it" line; add a one-line "tests need `uv sync`"
   note by the test commands.

### Larger / architectural (sequence deliberately)

6. **Vectorize the scale path and add a guard.** Replace the `cross_level_align`
   comprehension with a vectorized remap (build a max-keyed lookup array or use
   `np.unique`+searchsorted on the mapping keys); evaluate vectorizing `map_estimate`/
   `hdi` (or document the per-row cost). Add a coarse throughput/memory guard test for
   `io/arrow` round-trip and `cross_level_align` at representative grid size — the
   analogue of pipeline-core's `test_report_stage_memory.py`. The package is sold on
   scale; prove it.
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
   cure) as an explicit, dated item rather than "exploratory," since the README front-
   loads C-48 as motivation. Either generalize the index protocol to a non-spatiotemporal
   key (a v2 decision per §13a.6) or move `MetricFrame` ownership to views-evaluation and
   say so plainly.

---

## Appendix — what I inspected

- **Source (all read):** `src/views_frames/{__init__,index,spatial_level,protocols,
  _validation,metadata,prediction_frame,feature_frame,target_frame}.py`,
  `io/{npz,arrow}.py`, `conformance/__init__.py`; `src/views_frames_summarize/
  {__init__,_common,collapse,point,interval,aggregate}.py`.
- **Docs:** README, CLAUDE.md, GOVERNANCE.md, CHANGELOG.md, ADR index + ADRs
  011–017 references, `reports/technical_risk_register.md` (present), the CIC set,
  `critiqus/critique_02.md` (the falsification this version answers).
- **Tests (read + run):** all of `tests/` (`test_frames`, `test_conformance`,
  `test_import_enforcement`, `test_index`, `test_io`, `test_properties`,
  `test_summarize_*`, the `test_falsification_*` stubs).
- **Executed (read-only):** `pytest` → 83 passed; `ruff check .` → clean;
  `mypy --strict src/` → 14 errors (§6.1); `validate_docs.sh` → passed; a
  construct→collapse→hdi→smoke check → OK.
- **Not changed:** no source files, no staging, no commit, no branch. The working-tree
  changes visible in `git status` (the `perspectives/` reorganization) are
  **pre-existing / concurrent** and not made by this review.
