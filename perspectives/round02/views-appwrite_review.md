# views-frames — Review (round 02)

> **Reviewer:** Claude (Opus 4.8), as an AI-agent developer who would *consume and
> extend* this package. Companion to `perspectives/round01/views-appwrite_review.md`.
> **Date:** 2026-06-21. **Reviewed at:** **v0.3.0** (was v0.2.0 in round 01).
> **Method:** read the v0.3.0 diff surface (`git log`), every source module under
> `src/` (incl. the new `_typing.py`), README/CLAUDE.md/GOVERNANCE/CHANGELOG, the new
> `examples/quickstart.py`, the new `tests/test_proxy_adapter.py` and
> `tests/test_summarize_scale.py`, and `.github/workflows/ci.yml` + `uv.lock`. Ran
> the gates: `ruff check .` → **clean**; `mypy --strict src/` at **numpy 1.26.4** →
> **green** (was 14 errors); `pytest` → **111 passed, 15 failed** on the numpy floor
> (all one test — see §5/§7). Read-only: **no source modified, nothing staged, no
> commit, no branch.** The only file written is this report.
>
> **One-line verdict:** A strong, disciplined hardening round. Essentially every
> round-01 finding was addressed *in code* — and `cross_level_align` was made
> time-aware, which is a correctness upgrade beyond what I asked for. The package is
> now genuinely pleasant to target as an agent. It is held back from "clean" by a
> single, ironic regression: the new scale test that was added to *prove* the
> vectorization asserts **bit-for-bit** float32 equality, which holds on the locked
> numpy 2.x but **fails on the package's own declared numpy floor (1.26.4)** — the
> exact "green in default env, red on the supported floor" shape round 01 flagged for
> mypy, now recurring for pytest.

---

## 1. Does the repository now do what I need it to do?

**Yes — more so than round 01.** As an agent building a consumer adapter, the path
is now obvious and self-demonstrating.

- **Purpose — still crystal clear**, and now the README opens with a **Quickstart
  (§0a)** pointing at a runnable `examples/quickstart.py`. In round 01 the only way
  to learn "how do I make a frame" was to read the tests; that gap is closed.
- **Structure — understandable and now slightly larger in the right way.** The new
  `_typing.py` (private alias module) and `examples/` are exactly where you'd expect
  them; the two-package split (`views_frames` leaf + `views_frames_summarize`) is
  unchanged and still legible from the file tree alone.
- **I can see how I'd use it, end to end.** `examples/quickstart.py` walks
  construct → `collapse`/`map_estimate`/`hdi` → `save`/`load` → `assert_frame_contract`
  in 50 numpy-only lines. It ran in my smoke check. This is the artifact I asked for.
- **Abstractions are now complete for the alignment use-case.** Round 01's gap —
  the `Frame`/`SpatioTemporalIndexed` protocol didn't expose `.index`, so a consumer
  typing to the abstraction couldn't reach `cross_level_align` — is fixed
  (`protocols.py:36`). The abstraction a reconciler depends on now actually carries
  the alignment handle.

The only "what I need" still pending is the *reporting* consumer's win
(`MetricFrame` / the C-48 cure), which remains deliberately deferred (§4, §8).

---

## 2. Does it do things the way I would want?

**Mostly yes, and the new work is high quality.**

- **The time-aware `cross_level_align` is the standout.** It is now keyed by
  `(time, unit)` rather than `unit` alone (`index.py:180`), which is *correct* —
  a cell's country assignment is time-varying, and the old `unit`-only signature
  literally could not express that. It is also vectorized (void-viewed keys +
  `searchsorted`, no Python loop) and fails loud both on a missing key and on the
  old unit-only mapping shape. This is the rare case of a reviewer's perf note being
  answered with a perf fix *and* a latent correctness bug being caught in passing.
- **The uniqueness stance is exactly right.** `SpatioTemporalIndex` now documents
  (class docstring, `index.py:28-37`) that duplicate `(time, unit)` rows are
  *allowed* (cross-level produces them), that same-level joins *assume* uniqueness,
  and offers an opt-in `has_unique_rows()` (`index.py:167`) with the default path
  kept allocation-free. That is the precise resolution round 01 recommended.
- **The vectorized `map_estimate` is careful, not careless.** It is row-blocked
  (`_ROW_BLOCK = 65536`, `point.py:27`) so peak memory is `O(block × bins)`, with a
  `tracemalloc` guard test asserting memory does not scale with `rows × bins`
  (`test_summarize_scale.py:109`). The implementer clearly understood that a naive
  whole-grid `rows × bins` counts matrix would *re-introduce* the #181 OOM. This is
  the right instinct for a scale package.
- **Naming/docs/modularity** remain clear; module docstrings still cite the ADR +
  register ID behind each decision, and the CHANGELOG maps every v0.3.0 change to a
  `C-xx` finding. `CLAUDE.md` is unchanged and still an excellent agent brief.

Where it diverges from what I'd want: the scale test asserts more than the
implementation can deliver across the supported numpy range (§5), and the
`cross_level_align` API takes a Python `dict` keyed by tuples, which is itself a
scale liability at full grid (§7, minor).

---

## 3. What has improved since round 01?

Round 01 raised 6 weaknesses + 9 prioritized recommendations. The resolution rate is
high; the CHANGELOG (`[0.3.0]`) and commits map them explicitly to registered
findings C-19..C-23.

| Round-01 finding | Status in v0.3.0 | Evidence |
|---|---|---|
| #1 `mypy --strict` red on numpy floor | **Resolved** | `_typing.py` `IntArray = NDArray[np.integer[Any]]`; mypy green at 1.26.4; new CI `type-floor` job pins 1.26.4 (C-19) |
| #2 no `py.typed` | **Resolved** | `py.typed` in both packages (C-23) |
| #3 no runnable examples | **Resolved** | `examples/quickstart.py` + README §0a |
| #3 Python-loop estimators (scale) | **Resolved (impl)** | `map_estimate` block-batched; `hdi`/`quantiles` vectorized; memory guard test (C-22) |
| #4 unstated `(time,unit)` uniqueness | **Resolved** | documented stance + `has_unique_rows()` (C-21) |
| #5 protocol surface missing `.index` | **Resolved** | `index` on `SpatioTemporalIndexed` (C-23/F4) |
| #6 contract unproven by a real consumer | **Partially** | in-repo synthetic grid-adapter proxy (`test_proxy_adapter.py`); real cross-repo proof still Epic 3 |
| round-01 cross_level perf note | **Resolved + upgraded** | vectorized **and** made time-aware `(time,unit)`-keyed (C-20) |
| round-01 doc drift (`align`, glossary) | **Resolved (doc-sync)** | commit `8dfc8a4` "doc-sync"; README §5 now matches the protocol |

The two changes that most improve the design: **(a)** the time-aware cross-level key
(a correctness fix that prevents silently wrong country aggregation across months),
and **(b)** the protocol now carrying `.index`, which makes the published
abstraction actually sufficient for the reconciler/aligner it was written for.

The process signal is also strong: round-01 findings were registered (C-19..C-23),
ratified where they touched the contract (the `(time,unit)` key is a documented
**breaking** pre-1.0 change with a fail-loud guard on the old shape), and a new
conformance law (`assert_cross_level_alignment_law`) was added. The audit→register→
ADR→code→conformance loop is working, same as it did for `critique_02` last cycle.

---

## 4. What is still missing?

- **A test gate that actually covers the declared numpy floor.** The new
  `type-floor` CI job runs `mypy` at numpy 1.26.4 but **not** `pytest`
  (`ci.yml:31-39`). The `check` job runs pytest on the **locked numpy 2.2.6**. So no
  CI job runs the test suite at the floor — which is exactly where the bit-for-bit
  MAP test breaks (§5). The floor is type-checked but not behaviour-checked.
- **A real consumer running the conformance suite (Epic 3).** The proxy
  (`test_proxy_adapter.py`) is a good interim de-risk — it fabricates a
  datafactory-style `[T,H,W,C]` grid, frames it, and drives it through
  `assert_frame_contract` + `assert_summarizer_contract` — but it is *in-repo*. The
  cross-repo claim (one contract, N consumers) is still asserted, not demonstrated.
  The test itself says so: "the real proof is the owner's migration; this is the
  interim de-risk."
- **`MetricFrame` / the reporting C-48 cure.** Still deferred (round-01 rec #9
  unactioned, correctly per §13a.6). The README/perspectives still front-load C-48 as
  motivation; the typed eval-output that would close it does not exist yet. Fine as a
  decision — but it remains the largest *unbuilt* piece of the original pitch.
- **A runnable example of the subtle API.** `examples/quickstart.py` covers the easy
  path (construct/collapse/save). The operation most likely to be *misused* —
  `cross_level_align` / `aggregate_distributions` with a consumer-injected
  `(time,unit)→target` mapping — has no runnable example. That is the one place a
  consumer needs hand-holding (build the mapping, conservation semantics,
  `HDI(sum) ≠ sum(HDI)`), and it is examples-free.
- **A documented accuracy caveat.** The CHANGELOG and `point.py:14` assert
  `map_estimate` is "bit-for-bit identical to v0.2.0 … proven by
  `test_summarize_scale.py`." That proof holds on numpy 2.x only; on numpy 1.26.4 it
  is off by ~1 ulp (§5). The claim should be scoped ("to float32 precision," or
  "bit-for-bit on numpy ≥ 2.0") or the floor should be raised.

---

## 5. What surprised me this round?

**Good surprises**
- **The cross-level key became time-aware unprompted.** I flagged the vectorization;
  the team also recognised the mapping is time-varying and changed the key shape to
  `(time, unit)` with a fail-loud guard on the old shape. That is deeper than the
  finding asked for and prevents a silent cross-month aggregation error.
- **The memory guard test.** `test_map_estimate_memory_is_bounded_at_grid_scale`
  builds a 1,000,000-row frame and asserts (via `tracemalloc`) that peak stays under
  half of a whole-grid `rows × bins` matrix. A package sold on scale now *proves* its
  hottest reduction doesn't reintroduce the OOM it exists to kill. Excellent.
- **The proxy adapter asserts `has_unique_rows()`** on its constructed grid — the new
  affordance is already exercised by the interim consumer proof.

**Bad / unexpected surprise (the headline)**
- **`pytest` is red on the declared numpy floor: 15 failed, 111 passed at numpy
  1.26.4.** All 15 are `test_map_estimate_matches_per_row_reference` (3 shapes × 5
  seeds), and all are the *same* cause: the test asserts `np.array_equal` (bit-for-bit)
  between the batched `map_estimate` and the v0.2.0 per-row reference, but the two
  arithmetic paths differ by one float32 ulp (max abs diff **1.86e-7**;
  `np.allclose(rtol=1e-5)` passes). The library is **correct** — the *test* over-
  asserts. This passes in CI only because CI's `check` job runs on the locked numpy
  **2.2.6**, where the float paths happen to coincide; the floor job runs only mypy.
  So a consumer who pins numpy 1.26 (squarely inside the declared `numpy>=1.26` range)
  and runs the suite — or the published conformance suite, if a similar assertion ever
  lands there — sees 15 failures. **This is round-01's mypy finding recurring for
  pytest:** the fix added a floor job for *types* but the same floor gap now exists for
  *behaviour*, and the new test introduced it.

**Mildly unclear**
- The doc claim "bit-for-bit identical … proven by `test_summarize_scale.py`" is
  self-contradicted by that test failing bit-for-bit on the floor; "to float32
  precision" would be the honest and still-strong claim.

---

## 6. Strongest parts now

1. **The cross-level alignment design** — time-aware `(time,unit)` key, vectorized,
   fail-loud, mapping injected (never embedded), with a conformance law
   (`assert_cross_level_alignment_law`). This is the piece the whole package was
   most at risk on (it was the falsified claim in `critique_02`), and it is now the
   most robust.
2. **Executable, layered guarantees** — import-DAG AST test, one-concept-per-file
   test, zero-copy `np.shares_memory` assertions, *and now* a `tracemalloc` memory
   guard and a numpy-floor type job. The invariants that matter are machine-checked.
3. **Round-trip from finding to fix is demonstrably fast and faithful.** Six round-01
   findings closed in one release, registered and ADR-ratified, with breaking changes
   handled fail-loud. The governance loop is real.
4. **Agent-readiness** — `CLAUDE.md` + Quickstart + a self-verifying conformance
   suite + typed (`py.typed`, strict-green) surface. An agent can generate an adapter
   and get a deterministic yes/no on contract conformance.

---

## 7. Weakest parts now

1. **The suite fails on the declared numpy floor (15 tests).** A named gate (pytest,
   per `CLAUDE.md`) is red on a supported configuration; CI hides it by only running
   pytest on the locked 2.x and only mypy at the floor. *(small fix, high priority —
   it is a one-assertion change plus a CI line.)*
2. **Over-strict equivalence testing as a pattern.** `test_summarize_scale.py` and
   `test_hdi_matches_per_row_reference` assert `np.array_equal` against a floating
   reference. HDI survives (sort+gather is exact) but MAP does not (it recomputes bin
   edges via `linspace`/division). Bit-for-bit equality across two float paths and
   across a numpy major version is the wrong contract; the right one is "same selected
   bin, centre equal to float32 tolerance." *(small fix)*
3. **The cross-repo value is still proven only in-repo.** The proxy is good, but until
   a real consumer (pipeline-core / datafactory shim) runs the conformance floor in
   *its* CI, the keystone's central claim is undemonstrated. *(architectural / Epic 3)*
4. **`cross_level_align` accepts a Python `dict` keyed by tuples.** At full-grid,
   time-varying scale (~10.5M `(time,unit)` entries) the injected mapping is itself a
   large Python object, and the leaf rebuilds it into arrays via
   `list(mapping.keys())` (`index.py:217`) — an O(M) Python materialisation in the one
   API meant for grid scale. Correct, but the injected *shape* may not scale; a
   columnar mapping (two arrays) would. *(forward-looking, medium)*
5. **`MetricFrame` / C-48** remains unbuilt while still being used as motivation
   (doc-vs-delivery gap, well-disclosed but persistent). *(architectural)*

---

## 8. What should be improved next (prioritized)

### Small fixes (hours; do before any consumer pins this)

1. **Make the MAP equivalence test tolerance-based, and test the floor.** Replace the
   bit-for-bit `np.array_equal` in `test_map_estimate_matches_per_row_reference` (and
   the degenerate-rows variant) with "same densest-bin index + centre within float32
   tolerance" (e.g. `np.testing.assert_allclose(..., rtol=1e-5, atol=1e-6)` on the
   centre, plus an exact check on the selected bin index). Then **add `uv run pytest`
   (or at least the summarize tests) to the `type-floor` job** so the declared floor
   is behaviour-checked, not just type-checked. This closes the recurring "green in
   default env, red on the floor" gap permanently.
2. **Scope the accuracy claim.** Change `point.py:14` and the CHANGELOG from
   "bit-for-bit identical to v0.2.0" to "identical to float32 precision (bit-for-bit
   on numpy ≥ 2.0)" — or raise the numpy floor to `>=2.0` if 1.26 support isn't
   actually needed (and update `pyproject.toml` accordingly). Pick one; today the
   declared floor and the claimed behaviour disagree.
3. **Add a `cross_level_align` / `aggregate_distributions` example.** Extend
   `examples/` (or add `examples/cross_level.py`) showing a consumer building a
   `(time,unit)→country` mapping, aligning, and aggregating with the
   `HDI(sum) ≠ sum(HDI)` conservation point. This is the API most likely to be
   misused and the one with no runnable demo.

### Larger / architectural (sequence deliberately)

4. **Land one real consumer on the conformance floor (Epic 3).** Ship the
   pipeline-core `PredictionFrame` re-export shim and have pipeline-core CI run
   `views_frames.conformance.assert_frame_contract` against its own adapter output at
   the governed floor. The proxy de-risks this; it does not replace it. Highest-value
   next milestone after the small fixes.
5. **Evaluate a columnar injected-mapping shape for cross-level at grid scale.** If
   the cm↔pgm mapping is genuinely ~10M time-varying entries, accept the mapping as
   two parallel arrays (`map_keys (M,2)`, `map_vals (M,)`) in addition to / instead of
   a `dict`, so neither the consumer nor the leaf materialises a giant Python dict on
   the hot path. Benchmark before committing.
6. **Decide `MetricFrame` explicitly.** Either schedule the index-protocol
   generalization to a non-spatiotemporal key (the v2 path in §13a.6) or move
   `MetricFrame` ownership to views-evaluation and stop citing C-48 as a views-frames
   deliverable. The motivation and the roadmap should agree.

---

## Appendix — what I inspected

- **Diff surface:** `git log` (v0.1.0 → v0.3.0); the four hardening commits
  (`8dfc8a4` types/py.typed/protocol, `371a605` vectorize/uniqueness, `de487ef`
  time-aware cross_level_align, `f38e14a` quickstart/proxy/release) and the
  register commit `827e6d2` (C-19..C-23).
- **Source (all read):** the leaf (`__init__`, `index`, `spatial_level`,
  `protocols`, `_validation`, `_typing`, `metadata`, the three frames, `io/npz`,
  `io/arrow`, `conformance`) and `views_frames_summarize` (`collapse`, `point`,
  `interval`, `aggregate`, `_common`, `conformance`).
- **Docs:** README (Quickstart §0a, §13a), CLAUDE.md, GOVERNANCE.md, CHANGELOG
  `[0.3.0]`, `ci.yml`, `uv.lock` (numpy pin), `critiqus/critique_02.md` context.
- **New tests:** `examples/quickstart.py`, `tests/test_proxy_adapter.py`,
  `tests/test_summarize_scale.py`; re-read `test_frames`, `test_conformance`,
  `test_import_enforcement`.
- **Executed (read-only):** `ruff check .` → clean; `mypy --strict src/` @ numpy
  1.26.4 → **green** (was 14 errors); `pytest` @ numpy 1.26.4 → **111 passed, 15
  failed** (all `test_map_estimate_matches_per_row_reference`, ~1 ulp); `allclose`
  confirmation that the failure is float32 precision, not logic; CI inspection
  confirming `check` runs pytest on locked numpy 2.2.6 and `type-floor` runs mypy
  only.
- **Not changed:** no source files, no staging, no commit, no branch. Working-tree
  changes visible in `git status` (the `perspectives/round00|round01/` reorganization)
  are **pre-existing**, not from this review.
