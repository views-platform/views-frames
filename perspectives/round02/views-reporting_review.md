# views-frames — Review (round 02)

> **Reviewer:** Claude (Opus 4.8), as an AI-agent developer who would *consume and
> extend* this package.
> **Date:** 2026-06-21. **Reviewed at:** v0.3.0, branch `main` @ `f38e14a`
> (round-01 was v0.2.0 @ `07beefb`).
> **Method:** **read-only static inspection.** I diffed `07beefb..HEAD`, then read the
> changed source (`index.py`, `_typing.py`, `protocols.py`, the summarize package,
> the conformance suites), the new `examples/quickstart.py` and `tests/test_proxy_adapter.py`
> and `tests/test_summarize_scale.py`, and the README / CHANGELOG / ADR-014 / register
> diffs. I did **not** execute `pytest`/`mypy`/`ruff` (that writes cache directories,
> outside the single permitted write); **CI is the authority** on pass/fail. Read-only:
> **no source modified, nothing staged, no commit, no branch.** The only file written
> is this report.
>
> **One-line verdict:** An exemplary hardening round. Every round-01 finding I raised
> was registered (C-19–C-23) and *actually closed in code* — and in two cases the team
> went deeper than I did (they turned my "Python-loop in `cross_level_align`" perf note
> into a **correctness** fix: the mapping is now time-varying). The repo has crossed
> from "looks right" to "demonstrably disciplined." What remains is a thinner, more
> specialized set of issues: the memory discipline is **inconsistent across the
> summarizer family** (`hdi`/`quantiles` aren't blocked the way `map_estimate` is, and
> the scale guard doesn't cover them), the **injected-mapping interface is still a
> Python `dict`** — the one remaining scale liability on the alignment path — and a
> **governance loose end** (the conformance floor didn't move despite a breaking
> contract change).

---

## 1. Does the repository now do what I need it to do?

**Yes — more completely than in round 01.** The two gaps that previously stopped a
first-time consumer cold are gone:

- **There is now a runnable on-ramp.** `examples/quickstart.py` and the README §0a
  Quickstart show the whole arc — construct index → wrap a `PredictionFrame` →
  `collapse`/`map_estimate`/`hdi` → `save`/`load` → `assert_frame_contract` — in ~15
  legible lines. This was my single highest-value round-01 gap; it is closed. As an
  agent, I can now copy a known-good skeleton instead of reverse-engineering it from
  `tests/`.
- **The contract is now exercised by a consumer-shaped test.**
  `tests/test_proxy_adapter.py` fabricates a datafactory-style gridded `[T,H,W,C]`
  tensor, reshapes it into a `FeatureFrame`, and drives it through *both*
  `assert_frame_contract` and `assert_summarizer_contract`. It is honest that this is an
  *in-repo* proxy, not a real sibling-repo consumer (`test_proxy_adapter.py:9`) — but it
  closes the "does the published contract actually accept third-party-shaped output"
  question end-to-end, which round 01 could not answer at all.

Purpose, structure, and abstractions remain as clear as before (the README design-bible
thesis, one-concept-per-file layout, fail-loud construction, typed `FrameMetadata`,
pytest-free conformance suite). The two-package split (`views_frames` leaf +
`views_frames_summarize`) is now reflected accurately in the README status line and
glossary (the stale "`collapse` reduces it" prose is fixed).

**The one durable caveat is unchanged and correctly still open:** `FrameMetadata` still
carries only `model/run_type/timestamp/seed` — not `run_id`/`data_version`/`code_revision`
— and `MetricFrame` is still deferred. As a *reporting* consumer that needs provenance
for the downstream C-34 footer / durable C-48 fix, that piece is still not here. This is
the right call for the leaf; I flag it only because it remains the one thing a reporting
consumer cannot get from this repo yet (see §4).

---

## 2. Does it do things the way I would want?

**Yes, and the protocol surface is now honest.** The biggest round-01 "way I'd want it"
miss — that no protocol exposed `.index`, so a consumer typing against the abstraction
could not reach `cross_level_align` — is fixed: `SpatioTemporalIndexed` now declares
`index: SpatioTemporalIndex` (`protocols.py:35–38`), and `Frame` composes it. A
consumer can now type to the abstraction and still reach alignment. The `TYPE_CHECKING`
import of the concrete index to annotate the protocol is the right way to do it without
a runtime cycle.

- **Typing is now delivered and floor-correct.** `py.typed` ships in both packages, and
  the bare `NDArray[np.integer]` annotations are replaced by a single named alias
  (`_typing.IntArray = NDArray[np.integer[Any]]`, `_typing.py:21`). Crucially they added
  a **dedicated CI `type-floor` job** pinning `numpy==1.26.4` (`ci.yml`) — exactly the
  "CI-green-on-matrix ≠ floor-is-clean" gap I named, now machine-guarded. This is a
  better fix than I proposed; I suggested verifying the floor, they automated it.
- **The conformance surface grew sensibly.** `assert_summarizer_contract`
  (`views_frames_summarize/conformance.py`) now lets a consumer self-test the sibling's
  output shapes too, and `assert_cross_level_alignment_law` encodes the time-varying
  remap law. The contract a consumer runs in its own CI now covers leaf + summarize +
  alignment.
- **Naming/docs/modularity remain strong**, and the docstrings now carry the register
  IDs of the decisions (e.g. the C-21 uniqueness stance is written into the
  `SpatioTemporalIndex` class docstring, `index.py:28–37`), so the *why* still travels
  with the code.

Where it still diverges from what I'd want (new this round): the **injected mapping
type** for `cross_level_align` is a Python `Mapping[tuple[int,int],int]` — see §5/§7 —
which is the one interface that fights the scale thesis.

---

## 3. What has improved since the previous round?

Every round-01 finding I raised was registered as C-19–C-23 and resolved in v0.3.0
(PRs #63–#65). Verified against current source:

| Round-01 finding | Register | Status (verified in code) |
|---|---|---|
| No `py.typed` | C-23 | **Fixed** — markers in both packages; doc-sync done. |
| `mypy --strict` unverified on numpy floor | C-19 | **Fixed** — `_typing.IntArray`; CI `type-floor` job pins `numpy==1.26.4`. |
| `cross_level_align` Python-loop | C-22 | **Fixed + deepened** — vectorized *and* made time-varying (see below). |
| `map_estimate`/`hdi` `apply_along_axis` loops | C-22 | **Fixed** — vectorized; `map_estimate` row-blocked; `tracemalloc` scale guard. |
| Unstated `(time,unit)` uniqueness | C-21 | **Fixed** — documented stance + `has_unique_rows()`. |
| Protocol exposes no `.index` | C-23 | **Fixed** — `index` added to `SpatioTemporalIndexed`. |
| `align` doc-drift / `collapse` glossary | C-23 | **Fixed** — README §4.3/§13a.2/§14. |
| No runnable example | (soft) | **Fixed** — `examples/quickstart.py` + README §0a. |
| No real consumer runs the contract | (soft) | **De-risked** — in-repo grid-adapter proxy test (honest it's interim). |

The standout improvement is **C-20 / `cross_level_align`**. I had flagged only the
Python-loop *performance* issue. The team correctly recognized the deeper point: a
PRIO-GRID cell's country assignment *changes by month*, so a `unit→country` mapping is
not just slow, it is **incorrect** — it cannot express the time dimension. v0.3.0 rekeys
the mapping to `(time, unit)→target_unit` (`index.py:180–242`), vectorizes the remap
(void-viewed keys + `searchsorted`), fails loud on the old unit-only shape, and publishes
a time-varying conformance law. That is a correctness fix hiding inside a performance
ticket — the most valuable kind, and exactly the sort of thing a good governance process
is supposed to surface. The register entry (C-20) is honest that ADR-014 *already*
specified time-varying and the code had merely under-implemented it.

The memory work is also more sophisticated than a naive "vectorize it": `map_estimate`
uses a **row-blocked batched histogram** (`point.py:46–55`) that reproduces
`numpy.histogram`'s uniform-bin algorithm bit-for-bit while capping peak memory at
`O(block × bins)` — and `test_summarize_scale.py` proves both the exact-match and the
bounded-memory properties at 1e6 rows. They understood that the naive vectorization (a
full `rows × bins` counts matrix) would simply *re-introduce* the #181 OOM, and avoided
it deliberately.

---

## 4. What is still missing?

- **Memory-blocking for `hdi`/`quantiles` (the sharpest new gap).** `map_estimate` was
  carefully blocked to bound peak memory; `hdi` and `quantiles` were **not**. `hdi` does
  `np.sort(values, axis=-1)` (`interval.py:28`) — a full-grid-sized sorted copy — then
  `widths = srt[..., k:] - srt[..., :s-k]` (`interval.py:36`), another ~full-size
  temporary; `quantiles` calls `np.quantile(..., axis=-1)` (`interval.py:45`), which also
  allocates. At the #181 full-grid regime these peak at ~2–3× the input array. The
  forecast template computes HDI bands over the grid too, so this is the same OOM class
  C-22 targeted, just relocated to the interval path. **The scale guard
  (`test_summarize_scale.py:109`) only asserts bounded memory for `map_estimate`** — there
  is no analogous guard for `hdi`/`quantiles`, so a future regression here is uncaught.
- **An array-based mapping interface for `cross_level_align`.** The remap *internals* are
  vectorized, but the *injected* mapping is a Python `dict` (`index.py:182`), and the code
  materializes it with `np.array(list(mapping.keys()))` / `list(mapping.values())`
  (`index.py:217,223`). At full-grid time-varying scale (~10.5M cells × T months) that
  dict — and the transient Python lists — are the dominant allocation. The leaf vectorized
  the cheap part and left the expensive part (a giant Python-object dict the consumer must
  build and hold) in the interface. A parallel-arrays overload (`map_keys: (M,2) int`,
  `map_vals: (M,) int`) would let a producer pass the mapping without ever building a
  Python dict. (See §7.)
- **A real external consumer (still).** The in-repo proxy is a genuine de-risk, but the
  cross-repo value proposition ("one contract, N consumers") is still not proven by an
  actual sibling repo running the conformance suite in *its* CI. Correctly tracked as the
  owner's migration (Epic 3); still the #1 outstanding "prove it."
- **Provenance fields / `MetricFrame` (still).** Unchanged from round 01 and correctly
  deferred — but it remains the one thing the reporting consumer needs and cannot get here
  (`run_id`/`data_version`/`code_revision`). Worth keeping on an explicit, dated line
  rather than "exploratory," since the README still front-loads C-48 as motivation.
- **Tuning knobs as config, not constants.** `_ROW_BLOCK = 1 << 16` (`point.py:27`) is a
  hard-coded magic constant. It is well-commented, but it is the one number that governs
  the memory/throughput trade-off on the scale-critical path and a consumer cannot tune it.

---

## 5. What surprised me this round?

**Good surprises**
- **The perf ticket became a correctness fix.** I did not flag the time-varying mapping
  bug; the team found and fixed it while addressing my loop note (C-20). That is the
  governance process catching something the *reviewer* missed — the strongest possible
  signal it is real.
- **They automated the thing I only asked them to check.** I suggested verifying
  `mypy --strict` on the numpy floor; they added a permanent CI `type-floor` job that
  pins `numpy==1.26.4`. The fix outlived the finding.
- **The vectorization is numerically honest.** `map_estimate` is not "close enough" — it
  reproduces `numpy.histogram`'s binning including the float-rounding edge correction
  (`point.py:82–88`) and the `density=True` tie-break (`point.py:94–100`), and proves
  bit-for-bit equivalence against the old per-row reference (`test_summarize_scale.py:80`).
  Most teams would have shipped a faster-but-subtly-different statistic.

**Bad / unexpected surprises**
- **The memory discipline is inconsistent within one small package.** It is surprising
  that the *same file family* (`point.py` vs `interval.py`) treats the identical scale
  constraint so differently — `point.py` blocks meticulously, `interval.py` allocates
  full-grid temporaries — with no guard on the latter. The #181 lesson was applied to one
  summarizer and not its siblings.
- **`map_estimate` re-implements a chunk of numpy by hand.** The bit-for-bit histogram
  reproduction (`point.py:59–104`) is impressive and well-tested, but it is ~45 lines of
  subtle numerics coupled to numpy's *internal* uniform-bin algorithm, living in a repo
  whose whole ethos is "one small concept per file." It is correct today and guarded by
  the reference test; it is also the most fragile-to-maintain code in the repo.

**Mildly unclear**
- **The conformance floor didn't move.** `CONFORMANCE_FLOOR` is still `"0.1.0"`
  (`conformance/__init__.py:24`) even though v0.3.0 made a *breaking* change to the
  published `cross_level_align` signature and *added* a published law
  (`assert_cross_level_alignment_law`). GOVERNANCE advertises "SemVer-for-contract" and a
  cross-repo bump process; it is unclear whether the floor is meant to track only the
  structural frame contract (which genuinely did not change) or the whole published
  conformance surface (which did). Either answer is fine — but it should be stated, or the
  floor should bump. (See §7/§8.)

---

## 6. Strongest parts now

1. **Finding → register → ADR → code → test, end to end, demonstrably.** Round 01's
   findings are individually traceable through C-19–C-23 to specific PRs to current code
   to passing guards. The register's "Resolved Concerns" section now reads as evidence,
   not aspiration.
2. **Executable, now-extended guarantees.** AST import-enforcement + `np.shares_memory`
   immutability + the new `tracemalloc` memory guard + bit-for-bit equivalence tests. The
   "hard constraints" and now the *scale* constraint are machine-checked.
3. **The time-varying cross-level alignment.** Correct, vectorized, fail-loud, and
   covered by a published law — the genuinely-reused primitive is now both fast and right.
4. **Floor-correct typing delivered to consumers.** `py.typed` + `IntArray` + a CI job
   that proves strict-typing holds at the version a consumer actually pins.
5. **Honest scoping under pressure.** The proxy test, the CHANGELOG's "Changed (breaking,
   pre-1.0)" label, and the register's "ADR-014 was already correct; the code matched it"
   note all show a team that documents the truth rather than the flattering version.

---

## 7. Weakest parts now

1. **Inconsistent memory discipline across the summarizer family + a guard hole.**
   `hdi`/`quantiles` (`interval.py`) allocate full-grid temporaries while `map_estimate`
   is blocked, and the scale guard covers only `map_estimate`. This is the same OOM class
   the round just fixed, surviving in the interval path. *(medium; same risk as C-22,
   relocated)*
2. **The injected-mapping interface is a Python `dict` at grid scale.** The vectorized
   remap is fed by `Mapping[tuple[int,int],int]` (`index.py:182`), materialized via
   `list(...)` (`index.py:217,223`). At the full-grid time-varying regime the dict is the
   dominant allocation — the leaf optimized its internals but left the scale liability in
   the signature. *(medium / architectural — it's an interface decision)*
3. **Hand-rolled numpy-histogram reproduction.** `point.py:59–104` is correct and tested
   but is the repo's most maintenance-fragile code and sits oddly against the
   one-small-concept ethos. *(low-medium; well-guarded, so risk is maintainability not
   correctness)*
4. **Governance loose end: conformance floor vs the breaking change.** `CONFORMANCE_FLOOR`
   unchanged at `0.1.0` despite a breaking alignment signature + a new published law.
   *(low; a documentation/governance consistency gap, not a code defect)*
5. **Cross-repo claim still unproven by a real consumer**, and **provenance/`MetricFrame`
   still absent** — both correctly deferred, both still the gap between "internally
   demonstrated" and "externally true." *(tracked; architectural)*

Note in fairness: `map_estimate` still contains a Python `for` loop (`point.py:47`), but
it is a *block* loop (~160 iterations for 10.5M rows), each iteration fully vectorized —
the deliberate memory-bounding mechanism, **not** a regression of C-22.

---

## 8. What should be improved next (prioritized)

### Small fixes (hours)

1. **Add a memory-bounded path — or an explicit guard — for `hdi`/`quantiles`.** At
   minimum, extend `test_summarize_scale.py` with a `tracemalloc` assertion for `hdi` at
   1e6 rows so the gap is visible; better, apply the same `_ROW_BLOCK` blocking to
   `interval.py` (sort + windowed-min per block). This closes the one concrete OOM the
   round otherwise left open. *(highest-value small fix)*
2. **State the conformance-floor policy explicitly** (or bump it). Decide whether
   `CONFORMANCE_FLOOR` tracks the structural frame contract only or the whole published
   conformance surface; write the answer next to `CONFORMANCE_FLOOR` and in GOVERNANCE.
   If it tracks the alignment laws, the breaking `(time,unit)` change warranted a bump.
3. **Promote `_ROW_BLOCK` to a documented, overridable parameter** (keyword arg with the
   current default), so a memory-constrained consumer can tune the scale knob.
4. **Add one CHANGELOG/GOVERNANCE sentence on the 0.x breaking-in-minor policy** — when
   breaking changes are allowed pre-1.0 and what 1.0 will lock. The v0.3.0 breaking change
   is fine and well-labeled; the *policy* should be written before consumers exist.

### Larger / architectural (sequence deliberately)

5. **Offer an array-based mapping overload for `cross_level_align`/`aggregate_distributions`.**
   Accept `(map_keys: (M,2) int, map_vals: (M,) int)` alongside the `dict`, so a producer
   can inject a full-grid time-varying mapping without building a Python-object dict. This
   removes the last scale liability on the alignment path and is the natural completion of
   the C-20/C-22 vectorization work. *(the highest-value architectural item now)*
6. **Prove the contract with one real external consumer (Epic 3).** The in-repo proxy did
   its job; the next milestone is a sibling repo (pipeline-core/datafactory shim) running
   `assert_frame_contract` + `assert_summarizer_contract` + `assert_cross_level_alignment_law`
   in *its own* CI against *its own* output.
7. **Put `MetricFrame` / the provenance fields on a dated line.** Decide where
   `run_id`/`data_version`/`code_revision` live (extend `FrameMetadata`, or carry them on a
   views-evaluation `MetricFrame`) and say so, because the downstream reporting C-34/C-48
   work depends on the answer and the README still leads with C-48 as motivation.

---

## Appendix — what I inspected

- **Diff:** `git diff 07beefb..HEAD` (40 files, +3050/−89), commits `8dfc8a4` (types/docs),
  `de487ef` (time-aware cross_level_align), `371a605` (vectorized summarizers + uniqueness),
  `f38e14a` (v0.3.0 release), `827e6d2` (register C-19–C-23).
- **Source (read in full):** `src/views_frames/{index,protocols,_typing}.py`,
  `src/views_frames/conformance/__init__.py`, `src/views_frames_summarize/{point,interval,
  conformance}.py`; skimmed `aggregate.py` (already vectorized in v0.2.0).
- **New artifacts (read):** `examples/quickstart.py`, `tests/test_proxy_adapter.py`,
  `tests/test_summarize_scale.py`.
- **Docs/governance (diffed):** README (§0a Quickstart, status, glossary), CHANGELOG
  (v0.3.0 entry), `docs/ADRs/014_cross_level_alignment_boundary.md`,
  `reports/technical_risk_register.md` (C-19–C-23 resolutions), `.github/workflows/ci.yml`
  (new `type-floor` job).
- **Method honesty:** static review only; I did **not** run `pytest`/`mypy`/`ruff` (writes
  cache dirs, outside the one permitted write) — CI is the authority on gate status.
  Findings are grounded in specific lines read this round (e.g. the `hdi` allocations at
  `interval.py:28,36,45`; the dict materialization at `index.py:217,223`; the
  `map_estimate` block loop at `point.py:47`; `CONFORMANCE_FLOOR` at
  `conformance/__init__.py:24`).
- **Not changed:** no source files, no staging, no commit, no branch. The only file this
  review wrote is this report, at
  `perspectives/round02/views-reporting_review.md`.
