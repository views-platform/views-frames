# views-frames — Review (round 01, from the views-faoapi agent)

> **Reviewer:** Claude (Opus 4.8), operating from the `views-faoapi` working context —
> i.e. an AI agent that would *consume* `views-frames` as the downstream
> serving/delivery layer (forecast `PredictionFrame`s, historical `TargetFrame`s,
> server-side MAP/HDI, geographic aggregation).
> **Date:** 2026-06-21. **Reviewed at:** `v0.2.0` (two-package release).
> **Method (read-only):** read `src/views_frames/index.py` and
> `src/views_frames_summarize/aggregate.py` **in full**; mapped every other module
> with a read-only sweep cross-checked against the README, ADRs (011–017), CHANGELOG
> and GOVERNANCE; read the README status/contract directly. I did **not** execute the
> test suite or type-checker this session (a companion review at `../round01.md` did,
> and its tooling results — `pytest` 83 passed, `mypy --strict` 14 errors — are
> credible and complementary to this report). **No source modified, nothing staged, no
> commit, no branch; the only file written is this report.**

---

## 0. Verdict

A **strong, unusually disciplined first version**, and from the consuming-agent seat
it is *close to adoptable*. It is the rare case where a design → critique →
implementation loop actually closed: ADRs 011–017 ratify essentially every *blocking*
recommendation from the earlier critiques and falsification pass (Option-C twins, an
explicit sample axis, a typed metadata header, a fixed `SpatialLevel`, a conformance
floor, `MetricFrame` scoped out, statistics split into a sibling package). The core is
small, numpy-only, immutable, and — best of all — its architecture rules are
*executable*, not honor-system.

It is held back from "ship-ready for consumers" by a handful of concrete gaps, one of
which is substantive: **`cross_level_align` cannot express the time-varying mapping its
own docstring promises**, so the exact cm↔pgm case the platform actually needs (a grid
cell's country changing by month) is silently unsupported. The rest are ergonomic
(no `py.typed`, no runnable examples) or hygiene (a README/version drift the README's
own rule forbids).

**Bones: ship-quality. Gaps: three concrete, mostly small — with one that touches the
public contract and should gate broad adoption.**

---

## 1. Does the repository do what I need it to do?

**As a transport/serving consumer — largely yes.**

- **Purpose is exceptionally clear.** README §0's thesis ("DataFrames are a boundary
  format, not internal transport; the canonical transport is array + spatiotemporal
  identifiers") is one unambiguous paragraph, and every §1 design choice is tied to a
  *named, observed* defect (the #181 OOM, the 22/25 wrong-run C-48, the `_ViewsDataset`
  god class). I never had to guess what this is for.
- **Structure is understandable at a glance.** Two packages: `views_frames` (the leaf —
  `index`, `spatial_level`, `protocols`, `_validation`, three sibling frames, `io/`,
  `conformance/`) and `views_frames_summarize` (sample-axis statistics). One concept per
  file; the tree alone tells you the responsibilities. This is the §6 goal, met.
- **I can see how I'd use it — by reading tests, not docs.** The vocabulary is
  discoverable (`__all__` is explicit, the surface is tiny), but there is **no
  Quickstart and no `examples/`**, so to learn "construct an index → wrap a frame →
  `save`/`load(mmap=True)` → `collapse`/`hdi` → `aggregate_distributions`," I had to
  reconstruct it from `tests/`. An agent wiring this in would do the same.
- **The abstractions are genuinely useful for agentic work.** The four
  `runtime_checkable` Protocols let me type against intent and `isinstance`-check
  capability; `SpatioTemporalIndex` correctly names the *real* reused primitive (the
  alignment logic, not the array). The published `conformance` suite is the standout: I
  can call `assert_frame_contract(my_adapter_output())` and get a deterministic,
  importable oracle for "did I satisfy the contract" — a first-class agentic affordance.

**From the faoapi seat specifically:** the two frames I serve exist
(`PredictionFrame` for forecast samples, `TargetFrame` for historical actuals), the
MAP/HDI/quantile reductions I compute server-side now live in
`views_frames_summarize`, and the cross-level `pg→country/gaul` aggregation I do is
present as `aggregate_distributions` — *except* it shares the time-blind mapping
limitation (§6). The reporting-facing win (`MetricFrame`/C-48) is correctly deferred,
so a reporting consumer's headline need is not yet here.

---

## 2. Does it do things the way I would want?

**Mostly yes, and in several places better than I'd expect.**

- **Immutability is done right, including the hard part.** Index arrays are
  `setflags(write=False)` (`index.py:43-44`), and (per the implementation) `with_metadata`
  returns a new frame that *shares* the values buffer with mmap preserved — the
  copy-vs-view discipline the prior critique demanded, conformance-pinned via
  `np.shares_memory`. This answers the #181 thesis in the *semantics*, not just the prose.
- **The sample axis is always explicit and trailing** (`(N,S)`/`(N,F,S)`/`(N,1)`,
  ADR-012). One shape rule, one collapse path, no `ndim` branching — exactly the
  invariant that makes shape-reasoning (mine and an agent's) tractable.
- **Architecture rules are executable.** `tests/test_import_enforcement.py` AST-checks
  the leaf for forbidden imports (pandas/viewser/`views_*`), pyarrow outside `io/`, and
  >1 public class per file. The README's "hard constraints" become CI-enforced
  invariants — the single most agent-friendly thing here: a contributor agent *cannot*
  silently break the topology.
- **The numpy-only core is real.** `PredictionFrame` was rewritten off pandas (the
  `pd.isna` identifier check → an integer-dtype check, since integers can't be NaN). No
  pandas anywhere in the leaf.
- **The two-package cut (ADR-017)** keeps volatile statistics out of the stable leaf —
  a mature SDP/SAP call, with the one-way dependency enforced.
- **`FrameMetadata` is a frozen typed header** whose `from_dict` ignores unknown keys —
  forward-compatible, the right call for a versioned contract.

Where it diverges from what I'd want:
- `Persistable.save(self, directory: str)` in `protocols.py` vs the concretes' `Path |
  str` — a small protocol/impl type mismatch a strict-typed consumer notices.
- `searchsorted(other)` returns *positions in self for other's rows* — `pandas.Index.
  get_indexer` semantics, **not** numpy's `searchsorted` semantics. An agent that knows
  numpy will mis-predict it; the `get_indexer` mental model isn't in the name (and
  `reindex` aliases the same method, compounding it).

---

## 3. What is missing?

**Ergonomics / developer affordances (highest practical impact):**
- **No Quickstart / `examples/`.** A 15–20 line construct→reduce→save→load→
  `assert_frame_contract` snippet in the README plus a runnable `examples/` script is the
  missing on-ramp for both humans and agents. The repo is documentation-*rich* (README,
  ADRs, CICs, perspectives, critiques) but example-*poor* — an inverted ratio for a
  library whose job is to be imported.
- **No `py.typed` marker (PEP 561).** The package is fully annotated and mypy-strict
  internally, but ships no `src/views_frames/py.typed`, so **downstream consumers' type
  checkers see it as untyped** — defeating much of the "typed contract" value. Small fix,
  large payoff; this is about *distribution*, not Python version.

**Architecture:**
- **Time-aware cross-level mapping (the real one) — missing.** See §6.1. This is the one
  place v1 under-delivers on its own thesis.
- **No row/`select`/subset op and no frame-level `reindex(other) -> Frame`.** The index
  returns *positions*; there is no helper that actually reorders a frame's `values`. So
  every consumer re-implements the apply step — partially re-creating the duplication the
  leaf exists to remove. Time/unit/feature subsetting is a basic need (faoapi and
  reporting both do it) and is absent.
- **No `EvaluationFrame`/key protocol.** README §11 said the leaf should define the
  identifier protocol views-evaluation conforms to; not present.

**Tests / assumptions:**
- **No `(time, unit)` uniqueness stance.** `validate_identifiers` checks dtype/length/
  completeness but not row uniqueness, while same-level alignment (`searchsorted`,
  `intersect`, `is_superset_of`) *assumes* it — duplicates misalign **silently**. And
  `cross_level_align` *deliberately* produces duplicate `(time, country)` rows (resolved
  later by `aggregate_distributions`), so uniqueness can't be a global invariant. The
  package needs a written position (optional `assume_unique` on the join, or an explicit
  "these ops assume uniqueness" note) — right now it's an unstated assumption.
- **No scale guard.** pipeline-core ships `test_report_stage_memory.py` for the very OOM
  this package targets; views-frames has no analogous memory/throughput guard for
  `io/arrow` round-trips or `cross_level_align` at full-grid size. A package sold on scale
  should prove it.

**Hygiene:**
- **README/version drift:** the README header says **"implemented — v0.1.0 … ADRs
  011–016"** while the package is **v0.2.0** with **ADR-017** (the summarize split). The
  exact "code and README disagree = bug" the README itself forbids.

---

## 4. What surprised me?

**Good surprises**
- **The falsification loop actually closed.** The earlier audit proved the "domain-free
  leaf can do cm↔pgm alignment" claim false; the repo didn't paper over it — it adopted
  the proposed salvage (leaf owns the *operation*, consumer *injects* the mapping),
  ratified as ADR-014, with a fail-loud "the leaf never guesses a mapping" raise. An
  audit finding landing this cleanly in code + ADR + README is rare and signals the
  governance here is real, not ceremonial.
- **Executable invariants.** I expected prose; I found AST tests that fail the build on a
  forbidden import or a second public class.
- **`np.add.at` joint-sampling aggregation** (`aggregate.py:44`) preserves sample
  alignment across the cross-cell element-wise sum — it correctly implements
  `HDI(sum) != sum(HDI)` (faoapi's C-70) rather than the naive bound-sum.

**Bad / unexpected surprises**
- **`cross_level_align`'s docstring contradicts its signature.** It *says* it takes a
  "time-varying `unit -> target_unit` mapping" (`index.py:164`); it *is* a static
  `Mapping[int, int]` applied as `[mapping[int(u)] for u in self._unit]` (`:187`) with
  `time` only copied through. A docstring asserting a capability the code lacks is the
  most dangerous kind for an agent — I'd build on the promise and discover the gap at
  runtime (or, worse, ship silently-wrong country assignments in a UN-facing product).
- **No `py.typed`** in a package whose entire value is a typed contract.
- **No examples** in a package whose entire job is to be depended on.

**Harder than expected**
- Minor stale prose: README §4.3 mentions an `align` alias that doesn't exist (only
  `reindex`, `index.py:133`); the glossary still says "`collapse` reduces it" though
  collapse moved to the sibling package.

---

## 5. Strongest parts

1. **The motivation → decision → code → test chain is intact and traceable.** Each
   constraint maps to an ADR, a code invariant, and a test. The cross-level *boundary*
   fix is the exemplar (critique → ADR-014 → injected-mapping fail-loud raise + tests) —
   even though the mapping *shape* is still too narrow (§6.1).
2. **Executable architecture.** Import-DAG + one-concept-per-file enforced by AST tests;
   immutability/zero-copy enforced by `np.shares_memory`. The guardrails are machine-checked.
3. **The published conformance suite** — importable, dependency-light, governed by a
   `CONFORMANCE_FLOOR` with a documented cross-repo bump process. The right mechanism for
   the cross-repo contract-test gap (C-30).
4. **Disciplined scope.** The leaf refuses domain data, pandas, app logic, *and* sample-
   axis statistics. The boundary the whole platform's de-duplication depends on is drawn
   precisely and defended in code.
5. **Small, legible surface.** Three frames + index + level + typed metadata + four
   protocols — an agent can hold the whole API in working memory.

---

## 6. Weakest parts

1. **Cross-level alignment is the easy case wearing the hard case's docstring (most
   important).** `cross_level_align(mapping: Mapping[int, int], …)` (and
   `aggregate_distributions`, which calls it, `aggregate.py:36`) take a *static*
   `unit→target_unit` dict and never consult `time`. The platform's real cm↔pgm join is
   **time-varying** (`previous_country_id`; a grid cell's country changes across months —
   the exact fact the earlier falsification turned on). So the leaf "owns the operation"
   but only for the case that wasn't hard, while *claiming* (in the docstring) to handle
   the case that is. Both a correctness gap and a misleading contract.
2. **Adoption ergonomics:** no `py.typed`, no examples, no `select`/`reindex`-to-frame.
   *Describable* but not yet *pleasant to pick up* — which matters most for a keystone
   imported by six repos and by agents.
3. **Unstated `(time, unit)` uniqueness invariant** under joins that assume it — a
   silent-misalignment hazard until the stance is written down.
4. **Protocol surface narrower than the alignment use-case needs** — no protocol exposes
   `.index`, so a consumer typed to `Frame`/`SpatioTemporalIndexed` can't reach
   `cross_level_align` (the companion review flags this against README §5; worth
   reconciling doc↔code).
5. **README/version drift** (v0.1.0/ADR-016 header vs v0.2.0/ADR-017 package) — small,
   but the self-declared cardinal sin.
6. **Central claim untested end-to-end** — no real consumer runs the conformance suite
   yet (Epic 3); the keystone's cross-repo value is asserted, not demonstrated.

---

## 7. What should be improved next (prioritized)

### Small fixes (hours; before any consumer adopts)
1. **Fix the `cross_level_align` docstring now** to say *static* mapping, so it stops
   promising a capability it lacks (prevents silent misuse before the API is widened).
   *(Doc-only, but it removes a live trap.)*
2. **Add `src/views_frames/py.typed`** (and the summarize package's), and ensure
   hatchling ships them — so downstream `mypy` actually sees the types.
3. **Add a README Quickstart + an `examples/` script** (construct index → each frame →
   `collapse`/`hdi`/`map_estimate` → `save`/`load` npz+arrow → `assert_frame_contract`).
   The single highest-ROI usability change.
4. **Reconcile the README header to v0.2.0 / ADR-017** and mention
   `views_frames_summarize` in the one-liner.
5. **Align the `Persistable` protocol signature** to `Path | str`; fix the stale §4.3
   `align` and §14 glossary lines.

### Larger / architectural (gate broad adoption)
6. **Widen the cross-level mapping to be time-aware.** Change `cross_level_align` and
   `aggregate_distributions` to accept a `(time, unit) -> unit` mapping (or an injected
   callable / small `Protocol`) so the real `previous_country_id` join is expressible.
   Pair with a conformance law and a time-varying test. Ratify as an ADR — it changes the
   public contract, and everything cm↔pgm downstream depends on it. *(This is the one
   place v1 under-delivers on its own thesis.)*
7. **Add a `select`/subset and a frame-level `reindex(other) -> Frame`** so consumers
   stop hand-applying indexer arrays against `.values`.
8. **Decide and document the `(time, unit)` uniqueness stance** (recommend: frames may
   contain duplicates; same-level joins gain an optional validated/`assume_unique` path;
   state it in the `SpatioTemporalIndex` docstring + conformance suite).
9. **Reconcile the protocol surface** (expose `.index`, or correct README §5), so
   consumers typing to the abstractions can reach the alignment they exist to serve.
10. **Prove the contract with one real consumer (Epic 3)** — land the pipeline-core
    `PredictionFrame` re-export shim and have its CI run `assert_frame_contract` against
    its own adapter output. The highest-value milestone after the small fixes: it turns
    "looks right" into "demonstrated."
11. **Vectorize + guard the scale path.** Replace the per-element `cross_level_align`
    comprehension with a vectorized remap, evaluate the per-row `apply_along_axis` in
    `map_estimate`/`hdi`, and add a coarse throughput/memory guard at representative grid
    size — the analogue of pipeline-core's `test_report_stage_memory.py`.

---

## Appendix — what I inspected & verification

- **Read in full (this session):** `src/views_frames/index.py`;
  `src/views_frames_summarize/aggregate.py`; the README status header.
- **Mapped read-only & cross-checked against docs:** the rest of
  `src/views_frames/{__init__,spatial_level,protocols,_validation,metadata,
  prediction_frame,feature_frame,target_frame,io/*,conformance}.py`,
  `src/views_frames_summarize/{collapse,point,interval,conformance,_common}.py`,
  `pyproject.toml`, CHANGELOG, GOVERNANCE, ADRs 011–017, the test inventory (81+ tests
  incl. the `test_falsification_*` stubs).
- **Not executed this session:** the test suite and type checker (the Bash safety
  classifier was rate-limited); the companion `../round01.md` review executed them and
  its results are credible — this report is the static/contract-level complement, and its
  distinctive finding (the time-blind `cross_level_align`, §6.1) is from a full read of
  `index.py`/`aggregate.py`.
- **No changes made:** no source file altered, nothing staged, no commit, no branch
  created or switched. The only filesystem write is this report at
  `perspectives/round01/views-faoapi_review.md`.
