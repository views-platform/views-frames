# views-frames -- Review (round 01, from the views-datafactory agent)

> **Reviewer:** Claude (Opus 4.6), operating from the `views-datafactory` working
> context -- an AI agent that *produces* the data grids the platform consumes, owns
> `FeatureFrame` today, and would adopt `views-frames` as the shared data-contract
> layer beneath the adapter/query edge.
> **Date:** 2026-06-21. **Reviewed at:** v0.2.0 (two-package release).
> **Method (read-only + executed):** read every source module under `src/` in full
> (both packages), the README/CLAUDE.md/GOVERNANCE/CHANGELOG, all 18 ADRs, the CIC
> set, the risk register, all four critiques, all round00 perspectives, all existing
> round01 reviews, and all 13 test files; ran `uv run pytest` (83 passed, 0.22s),
> `uv run ruff check .` (clean), `uv run mypy --strict src/` (clean, 0 errors); ran
> a custom datafactory-perspective smoke test exercising `FeatureFrame` construction,
> `from_2d`, `PredictionFrame`, all summarizers, cross-level alignment, same-level
> alignment, NPZ and Arrow round-trips, and `aggregate_distributions`. **No source
> modified, nothing staged, no commit, no branch.** The only file written is this
> report.
>
> **One-line verdict:** A strong, clean, well-governed first version that solves the
> real problem it was built for. From the datafactory seat -- the repo that produces
> the grids and currently owns one of the twin `FeatureFrame` implementations -- the
> library is *close to adoptable*. The contract is correct, the architecture is
> disciplined, and the governance loop (critique -> falsification -> ADR -> code ->
> test) visibly closed. It is held back from adoption-ready by three gaps that matter
> to a producer: the absence of a `[T, H, W, C]` grid-to-frame bridging example, a
> missing ergonomic for `FeatureFrame` construction from the 2D arrays datafactory
> actually produces, and the lack of any real consumer proving the cross-repo contract.

---

## 1. Does the repository do what I need it to do?

**As a data producer that emits `FeatureFrame` -- yes, with caveats.**

### 1.1 Purpose is exceptionally clear

The README section 0 thesis ("DataFrames are a boundary format, not internal
transport; the canonical transport is array + spatiotemporal identifiers") is one
paragraph and unambiguous. Every design choice in section 1 is tied to a named,
observed defect (the #181 OOM, the list-in-cell blow-up, the `_ViewsDataset` god
class). I have never seen a data-contract library whose motivation is this
concretely grounded. From the datafactory side, the "diverging twins" problem
(section 1, bullet 1) is real -- our `FeatureFrame` at
`src/datafactory_adapters/feature_frame.py` and pipeline-core's `PredictionFrame`
share a concept but diverge on at least six axes (sample-axis position,
feature_names/metadata, NaN-check, collapse/mmap, save footprint, pandas import).
This library fixes that.

### 1.2 Structure is understandable at a glance

Two packages under `src/`: `views_frames` (the leaf: index, spatial_level,
protocols, validation, three sibling frames, io/, conformance/) and
`views_frames_summarize` (sample-axis statistics over frames). One concept per
file. The file tree alone tells me the responsibilities, which is the stated goal
of README section 6 -- and it is met.

### 1.3 I can see how I would use it

Constructing a `SpatioTemporalIndex(time, unit, level)`, wrapping values in
`FeatureFrame`, saving/loading (npz or arrow), and verifying with
`assert_frame_contract` all work. My smoke test exercised exactly the path
datafactory would follow:

1. Flatten the `[T, H, W, C]` grid to `(N, F)` arrays + `time`/`unit` vectors
2. Build a `SpatioTemporalIndex(time, unit, SpatialLevel.PGM)`
3. Construct `FeatureFrame(values_3d, index, feature_names)`
4. Save and load via `io/npz`

This works today. The `from_2d` shim handles the `(N, F)` -> `(N, F, 1)` lift
that our `_flatten_grid()` would need.

### 1.4 Abstractions are useful from the producer side

- **`SpatioTemporalIndex`** is the genuinely reused core. Today our
  `_flatten_grid()` manually constructs `{"time": all_month_ids, "unit":
  all_pgids}` as a plain dict. Wrapping that in a `SpatioTemporalIndex` adds
  type safety, immutability, and alignment ops at zero cost.
- **`SpatialLevel`** formalizes what is currently implicit in function names
  (`grid_to_country_month()` vs `grid_to_feature_frame()`). The time-first
  `index_names` and the `priogrid_gid` -> `priogrid_id` fix (ADR-015) are
  important: our codebase consistently uses `priogrid_id`, and having the leaf
  match avoids a naming inconsistency at the contract boundary.
- **The conformance suite** (`assert_frame_contract`) is the right affordance for
  a producer: I can call it in CI against `grid_to_feature_frame()` output and get
  a deterministic pass/fail on contract compliance.
- **`FrameMetadata`** gives our provenance data a typed home. Today our
  `FeatureFrame` carries `metadata: dict[str, Any]` -- a free-form dict. The
  frozen dataclass with named fields (`model`, `run_type`, `timestamp`, `seed`) is
  a strict improvement.

---

## 2. Does it do things the way I would want?

**Mostly yes, and in several places better than expected.**

### 2.1 The immutability model is done right, including the hard part

`with_metadata` returns a new frame that shares the values buffer
(`np.shares_memory` is asserted in `test_properties.py`). The `coerce_values`
function uses `np.asanyarray` to preserve `np.memmap` subclasses, so mmap-backed
frames stay zero-copy. This is precisely the discipline README section 3 promises,
and it matches how datafactory handles large grids (mmap is our standard for
multi-GB arrays).

### 2.2 Architecture rules are executable, not decorative

`tests/test_import_enforcement.py` walks the AST of every module and fails the
build if the leaf imports pandas/torch/viewser, if pyarrow appears outside `io/`,
if a foreign `views_*` is imported, or if a file declares more than one public
class. This is the single most reassuring thing in the repo for a prospective
dependency: the guardrails are machine-checked, so adopting this dependency means
adopting a library that enforces its own boundary rules.

### 2.3 The sibling-frames model (Option C) is the right call

ADR-011 (Option C: separate siblings, shared index only) is exactly what our
round00 perspective endorsed. Our `FeatureFrame` carries `feature_names` (required)
+ `metadata` + a feature axis `(N, F, S)`. `PredictionFrame` has none of these. A
shared base that holds everything would be the `_ViewsDataset` anti-pattern reborn.
Separate classes behind shared protocols avoids that.

### 2.4 The sample-axis convention is resolved correctly

ADR-012 closes the blocking decision: the sample axis is always an explicit
trailing axis (`S >= 1`). `FeatureFrame` is `(N, F, S)`, `PredictionFrame` is
`(N, S)`, `TargetFrame` is `(N, 1)`. This matches our existing `FeatureFrame`
contract (optional axis-2, now made explicit). The `from_2d` shim is the right
bridge for legacy 2D arrays.

### 2.5 Cross-level alignment is correctly scoped

ADR-014 resolves the hardest design question: the leaf owns the `cross_level_align`
*operation*, the consumer injects the *mapping*. This matches our architecture
perfectly -- our area-majority GAUL work (ADR-044) produces the `pgid -> country`
mapping, and we would inject it. The fail-loud "the leaf never guesses a mapping"
raise is exactly right.

### 2.6 The io layer is clean

`io/npz` operates on a generic state dict (values + identifiers + JSON header),
not a per-frame schema. `io/arrow` produces flat-columnar parquet (one scalar cell
per row) -- exactly the format we would want for downstream interchange. Both
round-trip correctly in my smoke test.

### Where it diverges from what I would want

- **No guidance on the grid-to-frame conversion pattern.** The README and docs
  extensively discuss what frames *are* but never show how a producer like
  datafactory should construct them from dense grids. An `examples/` snippet
  showing `[T, H, W, C]` flatten -> `SpatioTemporalIndex` -> `FeatureFrame` would
  save every producer from reverse-engineering the contract from test files.
- **`FeatureFrame.from_2d` is a classmethod shim, but the ergonomic gap is in the
  other direction.** Our `_flatten_grid()` already produces `(N, F)` arrays.
  `from_2d` does the right thing (lifts to `(N, F, 1)`), but having to know about
  the `from_2d` path at all is a minor friction. The main constructor's error
  message ("Use FeatureFrame.from_2d to lift a legacy (N, F) array") is excellent
  -- it tells you exactly what to do. But calling it "legacy" is misleading: for a
  producer that does not deal in posterior samples, 2D input is the *normal* path,
  not a legacy one.
- **`FrameMetadata` fields are too narrow for our use.** The four fields (`model`,
  `run_type`, `timestamp`, `seed`) are model-output provenance. A data-production
  `FeatureFrame` carries different provenance: source name, version, harvest
  timestamp, compilation config. Today we use `metadata: dict[str, Any]` for this.
  `FrameMetadata.from_dict` ignores unknown keys (forward-compatible), but that
  means our provenance fields silently vanish on round-trip through the typed
  header. We would need to either extend `FrameMetadata` with production-relevant
  fields (a MINOR change per section 8) or keep a separate sidecar. The
  forward-compatibility is good design, but the field set reveals a model-centric
  rather than producer-centric perspective.

---

## 3. What is missing?

### 3.1 Runnable usage examples (highest-value gap)

The README is a superb design bible (the "why") but contains no runnable "how." No
`examples/` directory, no Quickstart snippet, no usage in the package docstring.
The fastest path to "how do I make a frame" today is reading `test_frames.py`. For
a package meant to be adopted by N repos (and by agents), a 15-line
construct-reduce-save-load-conformance example is the missing on-ramp. From the
datafactory perspective, a grid-producer example would be especially valuable.

### 3.2 No real consumer proving the contract

The conformance suite runs only against the built-in frames
(`tests/test_conformance.py`), never against an external adapter. The cross-repo
value proposition (one contract, N consumers) is unproven until at least one
consumer runs `assert_frame_contract` against its own output. This is acknowledged
as Epic 3, but it means the keystone's central claim is currently untested
end-to-end.

### 3.3 `(time, unit)` uniqueness stance is unstated

`validate_identifiers` checks integer dtype, length-N, and completeness, but not
that rows are unique within a level. Same-level alignment operations
(`searchsorted`, `intersect`) implicitly assume uniqueness; duplicates would
misalign silently. Meanwhile, `cross_level_align` deliberately produces duplicate
`(time, country)` rows (pre-aggregation), so uniqueness cannot be a global hard
invariant. The package needs a documented position. From the datafactory side,
our grids are always unique per `(time, unit)` (each cell appears once per month),
so we would not trigger this -- but the absence of a documented stance is a
contract gap.

### 3.4 No benchmark or scale guard

The package is motivated by the #181 OOM at 9-18 GB scale. There is no throughput
or memory guard test for `io/arrow` round-trips, `cross_level_align`, or the
summarizers at representative grid size. Our assembled grid today is
`[T=553, H=360, W=720, C=79]` -- roughly 10.5 million rows when flattened to
`(N, F)`. A coarse benchmark would protect the central scaling claim.

### 3.5 Missing `py.typed` marker (PEP 561)

The package is fully annotated and claims `mypy --strict`, but ships no
`src/views_frames/py.typed` (or `views_frames_summarize/py.typed`). Without it,
downstream consumers get no types from the package they depend on. Small fix, real
impact.

### 3.6 Protocol surface is thinner than the README claims

README section 5 says `SpatioTemporalIndexed` exposes `index:
SpatioTemporalIndex`, but `protocols.py` exposes only `identifiers` + `n_rows` --
no protocol exposes `.index`. A consumer typing against `Frame` or
`SpatioTemporalIndexed` cannot reach `.index` (and thus `cross_level_align`), even
though every concrete frame has it. The protocols are slightly under-powered
relative to the alignment use-case they exist to serve. Previous reviews have
flagged this; it remains unresolved.

### 3.7 No `select` / subsetting operation

The README section 3 mentions `select` as an anticipated operation, but no frame
type implements it. From the datafactory/query perspective, subsetting a
`FeatureFrame` by time range, geographic region, or feature subset is a core
operation (`load_dataset()` supports all three). Today this subsetting happens in
our adapter layer, which is fine -- but the absence of a frame-level `select` means
every consumer must implement its own subsetting, duplicating logic that belongs
in the contract.

---

## 4. What surprised me?

### Good surprises

- **The falsification loop actually closed.** `critiqus/critique_02.md` proved the
  "domain-free leaf can do cross-level cm<->pgm alignment" claim false. The repo
  adopted exactly the salvage the audit proposed: leaf owns the operation, consumer
  injects the mapping, ratified as ADR-014, with the fail-loud raise. An audit
  finding landing this cleanly in code + ADR + README is rare and is the strongest
  signal the governance process is real, not ceremonial.

- **`mypy --strict` now passes clean.** The pipeline-core review (round01) reported
  14 errors from `NDArray[np.integer]` missing type parameters. These have been
  fixed. The strict-type gate is green.

- **The conformance suite is pytest-free.** Plain assertion functions, no testing
  framework dependency. Genuinely portable into any consumer's CI. This is
  consumer-first design.

- **The summarize split (ADR-017) is a mature call.** Pulling volatile statistics
  (MAP/HDI/quantiles/aggregation) out of the stable leaf into a sibling, with the
  one-way dependency enforced by AST, is a discipline most teams would not apply
  until forced. The result is a leaf that is genuinely a pure data contract.

- **`coerce_values` preserves `np.memmap`.** Using `np.asanyarray` (not
  `np.asarray`) to keep memmap subclasses alive is a detail that matters at our
  scale and is easy to get wrong. The fact that this is tested
  (`test_frames.py:99`) makes it trustworthy.

### Bad / unexpected surprises

- **No adapter guidance for producers.** The README is 560 lines of dense design
  prose, but a producer reading it learns what frames *forbid* (pandas, domain
  data, app logic) more readily than what they *afford*. The "how to build a
  frame from your data" story is missing -- you learn it from the tests.

- **`FrameMetadata` is model-output-centric.** The four fields (`model`,
  `run_type`, `timestamp`, `seed`) are all about model runs. A data-production
  `FeatureFrame` carries source/version/compilation provenance that has no home in
  this header. The `from_dict`/`to_dict` forward-compatibility is good, but the
  round-trip silently drops unknown keys. A producer's provenance either requires
  extending the header (a cross-repo coordination act) or maintaining a sidecar
  (which re-introduces the fragmentation the package exists to fix).

- **The `from_2d` shim is called "deprecated."** The docstring says "deprecated
  shim", but for datafactory, 2D `(N, F)` is the standard production output. If
  every grid-to-frame conversion goes through a method labeled "deprecated", that
  sends the wrong signal. The shim itself is correct -- the labeling is misleading.

- **Arrow IO at the frame level returns a state dict, not a frame.** `io/arrow.load`
  returns `dict[str, Any]`, not a `FeatureFrame` or `PredictionFrame`. The caller
  must reconstruct the frame manually (build a `SpatioTemporalIndex`, look up the
  level, pass `FrameMetadata.from_dict`). This is a leaky abstraction: the npz
  path is hidden behind `FeatureFrame.load()`, but the arrow path requires manual
  assembly. Granted, arrow is positioned as "interchange format," but from a
  producer perspective, I would want `FeatureFrame.load_parquet(path)`.

### Mildly unclear

- The README section 4.3 mentions `align`/`reindex` as operations, but only
  `reindex` exists in code (`index.py:133`); `reindex` is an alias for
  `searchsorted`. Minor naming drift.
- The glossary (section 14) still says "`collapse` reduces" the sample axis, but
  `collapse` has moved to `views_frames_summarize` (section 13a.7 flags this stale
  prose but it remains in the document).

---

## 5. Strongest parts

1. **The motivation-to-decision-to-code-to-test chain is intact and traceable.**
   Each constraint has an ADR, each ADR has code, each code module has tests, and
   the risk register ties them together with explicit IDs. The cross-level fix is
   the exemplar: critique -> ADR-014 -> `cross_level_align` -> injected-mapping
   fail-loud raise + tests. This is the most disciplined design-to-implementation
   loop I have seen in the platform.

2. **Executable architecture.** Import-DAG enforcement and one-concept-per-file
   are AST-tested. Immutability and zero-copy are asserted with
   `np.shares_memory`. The hard constraints are not honor-system -- they are CI.

3. **The published conformance suite.** Importable, pytest-free, governed by a
   `CONFORMANCE_FLOOR` with a documented cross-repo bump process. This is the
   right mechanism for the cross-repo contract-test gap, and it is the primary
   affordance that makes adoption safe for a producer.

4. **Agent-readiness of the docs.** `CLAUDE.md` gives an agent exact commands,
   six hard constraints, the two-package map, and the "build against the README;
   reconcile before merging" rule. The ADRs + risk register give enough context
   to make judgment calls. This is the right shape for autonomous work.

5. **Disciplined scope.** The leaf refuses domain data, pandas, app logic, and
   even statistics (now in the sibling). The boundary the platform's
   de-duplication depends on is drawn precisely and defended in code.

6. **The `from_2d` shim and the `coerce_values` float64 acceptance.** These two
   affordances mean a producer can hand the leaf what it has (a 2D float64 array
   from grid flattening) and get back what it needs (a valid 3D float32
   `FeatureFrame`). The fail-loud error messages are excellent -- they tell you
   exactly what to do when construction fails. This is good API design.

---

## 6. Weakest parts

1. **No producer-facing examples or construction guidance.** The README is a
   design bible for architects, not an on-ramp for producers. A 15-line
   "grid-to-frame" example would save every producer from reverse-engineering
   the contract from tests. *(small fix, high impact)*

2. **`FrameMetadata` is model-centric, not producer-centric.** The four fields
   serve model-output provenance. A data-production `FeatureFrame` carries
   different provenance (source, version, compilation config) that either requires
   extending the header or maintaining a sidecar. The forward-compatibility is
   good, but the field set reveals a model-output perspective that does not fully
   serve producers. *(medium -- requires a MINOR version bump to extend, which is
   by design, but the initial field set should have been producer-informed)*

3. **Arrow IO is half-integrated.** `io/npz` is fully integrated into frame
   `save`/`load` methods. `io/arrow` is a standalone state-dict API. A producer
   wanting parquet interchange must manually reconstruct frames from the state
   dict. *(medium -- architectural)*

4. **`from_2d` labeled "deprecated" when it is the normal producer path.** The
   docstring reads "Lift a legacy 2D (N, F) array to (N, F, 1) (deprecated
   shim)." For datafactory, 2D is not legacy -- it is the standard output. The
   label discourages the correct path. *(small fix)*

5. **No `select` / subsetting operation on frames.** Every consumer must
   implement its own subsetting logic (time range, geographic region, feature
   subset). Today this is acceptable because subsetting happens in the adapter
   layer, but it will become a duplicated concern as more consumers adopt.
   *(medium -- defer, but track as a v1.x candidate)*

6. **Central claim untested end-to-end.** No real consumer runs the conformance
   suite yet (Epic 3). The cross-repo contract-test gap the package exists to
   close is currently still open. *(tracked, but it is the gap between "looks
   right" and "proven")*

---

## 7. What should be improved next (prioritized)

### Small fixes (hours; do these before any consumer adopts)

1. **Add `py.typed` markers** to both `src/views_frames/` and
   `src/views_frames_summarize/`, and ensure hatchling includes them in the wheel.
   Without PEP 561 markers, the typed contract is invisible to downstream mypy.

2. **Add a Quickstart to the README and an `examples/` script.** Show a
   grid-producer constructing an index + `FeatureFrame`, a model-consumer
   constructing a `PredictionFrame`, sample-axis summarization, save/load, and
   `assert_frame_contract`. 15-20 lines, targeting both producers and consumers.

3. **Rename `from_2d` from "deprecated shim" to "construction helper."** The
   method is correct and necessary; the label is wrong. Producers that emit 2D
   arrays (which is the standard grid-flattening output) should not feel they
   are using a deprecated path.

4. **Reconcile the protocol surface with README section 5.** Either add `.index`
   to the `SpatioTemporalIndexed` protocol (so consumers can reach alignment
   ops through the abstract surface), or correct section 5 to match the actual
   protocol definition. Pick one and make doc equal code.

5. **Documentation hygiene:** fix the section 14 glossary "collapse reduces it"
   stale prose; add a one-line "tests need `uv sync`" note by the test commands;
   drop or alias the "align" operation mentioned in section 4.3.

### Medium fixes (days; before broad adoption)

6. **Extend `FrameMetadata` with producer-relevant fields.** Add at least
   `source: str | None = None` and `version: str | None = None` to
   `FrameMetadata`. These are the minimal provenance fields a data producer
   needs. All-optional, all-defaulting-to-None, so this is a MINOR change per
   section 8 versioning rules. Without these, producers must maintain a sidecar
   or lose provenance on round-trip -- which re-introduces the fragmentation
   the package exists to fix.

7. **Integrate arrow IO into frame save/load.** Add `save_parquet(path)` and
   `load_parquet(path)` classmethods (or a `format` parameter to `save`/`load`)
   so that the arrow path has the same ergonomics as the npz path. Currently the
   arrow API is a low-level state-dict interface that breaks the abstraction the
   frame provides. (This could be a classmethod or a standalone function in
   `io/arrow` -- either works, as long as the caller does not need to manually
   reconstruct `SpatioTemporalIndex` + `FrameMetadata`.)

8. **Document the `(time, unit)` uniqueness stance.** Recommended: frames permit
   duplicate rows (needed for pre-aggregation), but same-level join methods gain
   an optional `assume_unique` parameter or a validation path, and the stance is
   stated in the `SpatioTemporalIndex` docstring and CIC.

### Larger / architectural (sequence deliberately)

9. **Prove the contract with one real consumer (Epic 3).** Land the datafactory
   `FeatureFrame` re-export shim and have datafactory's CI run
   `assert_frame_contract` against `grid_to_feature_frame()` output. Until one
   consumer does this, the keystone's cross-repo value is asserted, not
   demonstrated. This is the highest-value next milestone after the small fixes.

10. **Add a `select` / subsetting operation.** At minimum, `select(time_range,
    unit_set)` on `SpatioTemporalIndex` (returning a boolean mask or a new index)
    and frame-level `select` that applies the mask and returns a new frame sharing
    the values buffer (via numpy advanced indexing). This would de-duplicate the
    subsetting logic that `load_dataset()`, reporting, and model repos each
    implement independently. Track as a v1.x candidate (MINOR change).

11. **Add a coarse scale guard test.** A benchmark test that constructs a
    representative-size frame (~10M rows, ~80 features), round-trips through npz
    and arrow, and asserts memory/throughput within bounds. The package is sold on
    scale; prove it.

12. **Consider a `from_grid` protocol or recipe.** Not a method on `FeatureFrame`
    (that would couple the leaf to grid internals), but a documented recipe or
    an `examples/grid_to_frame.py` showing the `[T, H, W, C]` -> `(N, F, 1)` ->
    `FeatureFrame` path. This is the standard producer on-ramp and it is missing.

---

## 8. Datafactory-specific adoption assessment

### What would change in views-datafactory

| File | Change | Risk |
|---|---|---|
| `pyproject.toml` | Add `views-frames>=0.2,<1` to dependencies | First internal dependency. Touches only the adapter/query edge (2 of 9 packages). Low risk. |
| `src/datafactory_adapters/feature_frame.py` | Replace 221 LOC with `from views_frames import FeatureFrame` shim | Zero behavior change. `from_grid()` becomes a standalone function. |
| `src/datafactory_adapters/__init__.py` | Re-export from `views_frames` instead of local | One-line change. |
| `src/datafactory_adapters/grid_to_feature_frame.py` | Construct `SpatioTemporalIndex` + leaf `FeatureFrame` | Signature unchanged. Internal arrays map directly to index constructor. |
| `src/datafactory_query/dataset.py` | Return type annotation updates | Cosmetic. |
| CI | Add `assert_frame_contract(grid_to_feature_frame(...))` | New test. The conformance suite is the safety net. |
| 39 test files | Import path changes via shim | Most require zero changes. |

### What would NOT change

The entire production pipeline (Layers 0-4: provenance, http, priogrid,
harvester, consolidation, viewpoint, compilation, assembly) has zero involvement.
All adapter functions (`grid_to_feature_frame`, `grid_to_dataframe`,
`grid_to_country_month`, `feature_frame_to_grid`) stay. The
`SpatioTemporalGrid` (our production backbone) is complementary, not replaced.
Pandas at the adapter edge stays -- the leaf bans pandas; we use it at the
boundary, which is exactly the adapter pattern the leaf expects.

### Blocking dependencies for adoption

1. The three items under "small fixes" (py.typed, from_2d labeling, protocol/doc
   reconciliation) should land before we adopt. They are small but affect
   correctness of the integration (types, naming, protocol surface).
2. `FrameMetadata` extension (item 6 above) should land before or concurrently
   with our adoption. Without producer-relevant provenance fields, our metadata
   silently vanishes on round-trip.
3. Our own readiness gate stories (#211, #212, #213) must close first --
   `development` is ahead of `main`, and adoption should happen from a stable
   baseline.

### Non-blocking but valuable

- Arrow IO integration (item 7) would simplify our parquet interchange story but
  is not blocking -- we can call `io/arrow` at the state-dict level in the interim.
- The `select` operation (item 10) would let us push subsetting into the frame
  contract, but today our `load_dataset()` handles it and that is fine.

---

## 9. Relationship to the round00 perspective

The round00 `from_views-datafactory_perspective.md` (ratified by Simon, 2026-06-21)
stated three positions:

1. **Option C for twin unification** -- endorsed. ADR-011 ratifies this. The code
   implements separate sibling classes with a shared `SpatioTemporalIndex`. Correct.
2. **Cross-level alignment: leaf protocol, consumer-injected mapping** -- endorsed.
   ADR-014 ratifies this. `cross_level_align` is implemented exactly as proposed.
   Correct.
3. **MetricFrame out of the leaf** -- endorsed. ADR-016 / README section 13a.6
   keeps it out. Correct.

All three blocking positions from round00 are resolved in code. The round00
perspective's section 8 asks (seven items) are addressed:

- Ask 1 (`feature_names` + `metadata` first-class): yes, both are in `FeatureFrame`.
- Ask 2 (save/load preserves them): yes, `io/npz` handles both via the JSON header.
- Ask 3 (`from_grid` as adapter, not frame method): yes, `FeatureFrame` has no
  `from_grid` (confirmed by `test_feature_frame_has_no_from_grid`).
- Ask 4 (`SpatioTemporalGrid` vs `SpatioTemporalIndex` naming): the naming
  collision remains (register C-12, tier 4). Not urgent.
- Ask 5 (conformance suite runnable against adapter output): yes, it is importable.
  Not yet exercised by any consumer.
- Ask 6 (month_id epoch-agnostic): yes, `time` is an opaque integer; no
  epoch/range/monotonicity check.
- Ask 7 (copy-vs-view semantics): yes, resolved (C-07). `with_metadata` shares the
  buffer; mmap propagates. Pinned in tests.

---

## 10. Summary

**What the package gets right (and these are substantial):**

- A clear, well-motivated, concretely grounded purpose
- Disciplined scope with machine-enforced boundaries
- An intact governance loop (critique -> falsification -> ADR -> code -> test)
- Correct resolution of all three blocking design decisions
- A published, portable conformance suite
- Agent-ready documentation

**What a producer needs before adopting:**

- `py.typed` markers
- `from_2d` renamed from "deprecated" to "construction helper"
- `FrameMetadata` extended with producer-relevant provenance fields
- Protocol/doc reconciliation (`.index` on the abstract surface)

**What would make it excellent:**

- Runnable producer-focused examples
- Arrow IO integrated into frame save/load methods
- A frame-level `select` operation
- A scale guard test at representative grid size
- One real consumer proving the cross-repo contract

The package is close. The code is correct, the architecture is sound, the
governance is real. The remaining gaps are mostly ergonomic and documentation-level
-- the kind of thing that gets fixed in a week of focused work. From the
datafactory seat, this is a library I would adopt with the small fixes above, and
I look forward to being its first consumer.

---

## Appendix -- what I inspected

- **Source (all read in full):** `src/views_frames/{__init__,index,spatial_level,
  protocols,_validation,metadata,prediction_frame,feature_frame,target_frame}.py`,
  `io/{__init__,npz,arrow}.py`, `conformance/__init__.py`;
  `src/views_frames_summarize/{__init__,_common,collapse,point,interval,
  aggregate,conformance}.py`.
- **Tests (all read in full + executed):** `test_conformance`, `test_frames`,
  `test_import_enforcement`, `test_index`, `test_io`, `test_properties`,
  `test_summarize_aggregate`, `test_summarize_collapse`,
  `test_summarize_estimators`, and all four `test_falsification_*` stubs.
- **Docs (all read in full):** README.md, CLAUDE.md, GOVERNANCE.md, CHANGELOG.md,
  all 18 ADRs (000-017 + template + index), all 7 CICs (6 + template), 2
  contributor protocols, 2 standards, INSTANTIATION_CHECKLIST.md, validate_docs.sh.
- **Perspectives/critiques (all read in full):** 5 round00 perspectives, 5 round01
  reviews, 4 critiques, the technical risk register.
- **Executed (read-only):** `uv run pytest` (83 passed, 0.22s), `uv run ruff
  check .` (clean), `uv run mypy --strict src/` (clean, 0 errors), custom
  datafactory-perspective smoke test (all passed).
- **Not changed:** no source files, no staging, no commit, no branch. The only
  file written is this report.
