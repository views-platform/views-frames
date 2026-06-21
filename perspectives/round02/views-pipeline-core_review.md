# views-frames — Review (round 02)

> **Reviewer:** Claude (Opus 4.8), as an AI-agent developer who would *consume and
> extend* this package (the views-pipeline-core / orchestration vantage).
> **Date:** 2026-06-21. **Reviewed at:** `v0.3.0` (`f38e14a`, "Epic 4 hardening").
> **Method (read-only):** re-read every module under `src/` (both packages), the
> README/CLAUDE/GOVERNANCE/CHANGELOG, ADRs (incl. the new 011–017), and the test
> suite; ran the gates in a **numpy 1.26.4** env (the declared floor): `ruff` →
> clean; `mypy --strict src/` → **green (21 files)**; `examples/quickstart.py` →
> runs; `pytest` → **RED (see below)**; and cross-checked the **remote GitHub CI**
> (green on `f38e14a`). **No source modified, nothing staged, no commit, no branch.**
> The only file written is this report.
>
> **One-line verdict:** A disciplined hardening release that closed *almost every*
> round-01 finding with visible code+ADR+test evidence — held back by one sharp
> problem: **the test suite is green in GitHub CI but RED on a conforming
> numpy-1.26.4 local env**, because the new vectorized `map_estimate` asserts
> *bit-exact* equivalence to `numpy.histogram` in float32. The scale *win* (bounded
> memory) is real; the scale *equivalence proof* is platform-fragile, and a green
> checkmark currently hides a non-portable suite.

---

## 1. Does the repository now do what I need it to do?

**Yes — more than in round 01, and now with a real on-ramp.**

- **Purpose still exceptionally clear**, and now *measured*: README §1 adds the
  #181 production OOM (C-186) as the live use-case, tying the whole thesis to an
  observed failure.
- **Structure understandable and improved.** Two packages, one-concept-per-file,
  plus a new `_typing.py` (named array aliases) and `examples/`. The file tree still
  tells the responsibilities at a glance.
- **I can finally see *how* without reading tests.** `examples/quickstart.py` runs
  end-to-end (construct index → frame → `map_estimate`/`hdi` → `save`/`load` →
  `assert_frame_contract`) and the README §0a Quickstart points to it. This was the
  single highest-value round-01 gap and it is closed.
- **Abstractions remain strongly agent-friendly**, and the protocol surface is now
  *correct*: `SpatioTemporalIndexed` exposes `.index` (`protocols.py:36`), so a
  consumer typing to the abstraction can reach `cross_level_align` — the round-01
  mismatch is fixed.

As a producer/transport consumer, everything I need is present. The reporting
consumer's headline (`MetricFrame`) is still deferred (§4).

---

## 2. Does it do things the way I would want?

**Mostly yes, and the rough edges from round 01 are sanded down.**

- **Interfaces sensible; the cross-level mapping got *more* correct.** v0.3.0
  re-keys `cross_level_align`/`aggregate_distributions` mappings by `(time, unit)`
  (not `unit` alone, register C-20): a cell's country can change month-to-month, and
  the static shape couldn't express that. The remap is **vectorized** (void-viewed
  `(time,unit)` keys + a single `searchsorted`, `index.py:194–230`) and **fails loud**
  on the old unit-only shape or a missing key. This is exactly the right move:
  correctness *and* the round-01 Python-loop removed in one change.
- **Typed contract is now actually delivered.** `py.typed` ships in both packages,
  and `_typing.IntArray = NDArray[np.integer[Any]]` parameterizes the generics so
  `mypy --strict` is green at the floor (round-01's 14 `[type-arg]` errors gone). I
  re-ran `mypy --strict src/` → clean.
- **The uniqueness assumption is now stated and checkable.** `has_unique_rows()`
  plus a documented "duplicates allowed; same-level joins assume uniqueness"
  stance (register C-21) closes round-01's unstated-invariant hazard.
- **Naming/modularity/docs remain clear**, with module docstrings citing ADR +
  register IDs. The CHANGELOG explicitly maps each change to a round-01 finding —
  excellent for an agent picking up the next round.

Where it diverges from what I'd want: the suite's **portability** (§5) and the
still-**unproven cross-repo conformance** (§4).

---

## 3. What has improved since the previous round?

Round 01's findings were addressed with unusual completeness — verified in code, not
just claimed in the CHANGELOG:

| Round-01 finding | Status in v0.3.0 | Evidence |
|---|---|---|
| `mypy --strict` red on numpy floor (14 errors) | **Fixed** | `_typing.py` aliases; `mypy --strict src/` green; CI `type-floor` job pins `numpy==1.26.4` |
| No `py.typed` | **Fixed** | `src/views_frames/py.typed`, `src/views_frames_summarize/py.typed` |
| Protocols don't expose `.index` | **Fixed** | `protocols.py:36` |
| `cross_level_align` Python-loop at scale | **Fixed + made time-aware** | vectorized void-view+searchsorted, `(time,unit)` keys (`index.py:194–230`) |
| Unstated `(time, unit)` uniqueness | **Fixed** | `has_unique_rows()` + documented stance |
| No runnable example / Quickstart | **Fixed** | `examples/quickstart.py` + README §0a |
| No real consumer exercising the contract | **Partially** | in-repo synthetic `tests/test_proxy_adapter.py` (not yet a *cross-repo* consumer) |
| New conformance law | **Added** | `assert_cross_level_alignment_law` (time-varying cross-level) |

The most meaningful design improvement is the `(time, unit)` mapping: it is both a
correctness fix (a cell's country varies over time) and the round-01 scale fix,
landed together with a fail-loud guard and a conformance law. The
governance→ADR→code→test loop is again intact and traceable.

---

## 4. What is still missing?

- **A real cross-repo consumer running the conformance suite (still the keystone
  gap).** v0.3.0 adds an *in-repo synthetic* adapter proxy (`tests/test_proxy_adapter.py`)
  — good, but it proves the contract against the package's own fixtures, not against
  views-pipeline-core/datafactory output. The central "one contract, N consumers"
  claim remains demonstrated only inside this repo. (Epic 3.)
- **A portability stance for the conformance/equivalence tests.** The suite passes
  in GitHub CI but not on a conforming numpy-1.26.4 local env (§5). For a package
  whose selling point is "import our conformance suite into *your* CI," the suite
  must be portable across platforms, not just green on the maintainer's runner.
  There is no documented "what environments the conformance floor is guaranteed on."
- **`MetricFrame`.** Still deferred. The README front-loads reporting's C-48 (the
  22/25 wrong-run bug) as motivation, but nothing in code addresses the typed eval
  output yet. Either schedule it or move ownership to views-evaluation and say so.
- **A local release gate that matches CI.** `CLAUDE.md` lists `mypy`/`ruff`/`pytest`
  but nothing tells a contributor to run the suite at the numpy *floor* before
  release — which is exactly where the current red hides.
- **Examples beyond the happy path.** `quickstart.py` is single-frame; an
  `examples/` snippet for `cross_level_align` + `aggregate_distributions` (the
  hardest, most novel surface) would help adopters most.

---

## 5. What surprised me this round?

**Good surprises**
- **The round-01 → fix → ADR → test loop closed again, at scale.** Seven of eight
  findings fixed, each with a code change *and* a test/ADR. This is the second
  consecutive round where audit findings landed cleanly; the governance is real.
- **`cross_level_align` got *more correct* under hardening**, not just faster — the
  `(time,unit)` time-varying mapping is a subtle correctness improvement most teams
  would have missed.
- **A dedicated `type-floor` CI job** pinning `numpy==1.26.4` — they took the
  round-01 "verify the lower bound actually passes" point seriously.

**Bad / unexpected surprises**
- **The suite is green in CI but RED on a conforming local floor env.** On
  **numpy 1.26.4** (the declared floor), `pytest` fails **7 cases** in
  `tests/test_summarize_scale.py::test_map_estimate_matches_per_row_reference`
  — `shape1 (200,31)` seeds 7,13 and `shape2 (16,8,40)` all seeds — while GitHub CI
  on the same commit `f38e14a` is **green**. The assertion is
  `np.array_equal(got.values[...,0], ref)` (`test_summarize_scale.py:80`): a
  **bit-exact** comparison of a hand-rolled float32 histogram-MAP
  (`point.py:_batched_map`) against `numpy.histogram`. float32 mode selection has
  tie/edge-rounding that differs across BLAS/libm/platform, so "reproduces
  `numpy.histogram` bit-for-bit" (point.py docstring) is not a portable invariant.
  `hdi` equivalence and the **memory-bound guard pass** — so the *scale win is
  genuine*; it is the *equivalence proof* that is fragile. This is the one finding
  that undermines trust in the green checkmark.

**Mildly unclear / harder than expected**
- The package still isn't importable without `PYTHONPATH=src`/editable install; a
  fresh `pytest` errors with `ModuleNotFoundError: views_frames`. `CLAUDE.md`
  documents `uv sync`, but a one-line "tests need an editable install / PYTHONPATH"
  next to the test command would save a confused first run.

---

## 6. Strongest parts now

1. **The motivation→ADR→code→test→CHANGELOG chain is fully traceable** across two
   review rounds — findings demonstrably drive change. This is the repo's defining
   strength and rare in practice.
2. **Executable architecture, now broader.** AST import-DAG enforcement,
   one-concept-per-file, `np.shares_memory` zero-copy assertions, the new typed-floor
   CI job, and `py.typed` delivery. The "hard constraints" are machine-checked.
3. **Correct, vectorized cross-level alignment** with a time-varying `(time,unit)`
   mapping and fail-loud guards — the hardest piece, handled well.
4. **Agent-readiness end-to-end:** `CLAUDE.md` + design-bible README + ADRs +
   register + a runnable quickstart + an importable conformance suite. An agent has
   everything to make an in-bounds change and a machine-checkable way to confirm it.
5. **Memory scaling is proven, not asserted** — `test_map_estimate_memory_is_bounded_at_grid_scale`
   guards the #181 regime and passes.

---

## 7. Weakest parts now

1. **Non-portable test suite / bit-exact equivalence in `map_estimate`.** Green in
   CI, red on a conforming numpy-1.26.4 local env (§5). The headline weakness:
   `np.array_equal` against a re-implemented `numpy.histogram` in float32 is too
   strict to be portable, and a maintainer-only-green suite defeats the
   "import our conformance into your CI" promise. *(high priority)*
2. **Cross-repo conformance still unproven.** The in-repo proxy is a good proxy, but
   no external consumer yet runs `assert_frame_contract` against its own output. The
   keystone's central claim remains asserted, not demonstrated. *(tracked, Epic 3)*
3. **`MetricFrame` absence** keeps the reporting-C-48 story (a README headline)
   uncured in code. *(medium)*
4. **Release/dev gate doesn't include the numpy floor locally** — the exact place
   the current red lives is not in the documented local checklist. *(small)*

---

## 8. What should be improved next (prioritized)

### Small fixes (hours; do before any consumer trusts the green check)
1. **Make `map_estimate` equivalence portable.** Replace the bit-exact
   `np.array_equal` in `test_summarize_scale.py:80` with a robust check — either
   assert the *selected bin index* matches (compute both from the same binning
   primitive) or assert `np.allclose` on the centres with a float32-scale tolerance,
   *and* treat tie rows explicitly. Better: have the production `_batched_map` and the
   reference share **one** binning helper so "reproduces numpy.histogram" is true by
   construction, not by float coincidence. Re-run on numpy 1.26.4 to confirm green.
2. **Add the numpy-floor run to the local gate.** Put "run `pytest` under
   `numpy==1.26.4` before release" in `CLAUDE.md`/`GOVERNANCE.md`; the maintainer-
   green/floor-red split should never recur silently.
3. **One-line test-setup note** ("`uv sync` / editable install or `PYTHONPATH=src`")
   beside the test commands.
4. **Add a `cross_level_align` + `aggregate_distributions` example** to `examples/` —
   the novel surface adopters will struggle with most.

### Larger / architectural (sequence deliberately)
5. **Document and CI-test the portability contract for the conformance suite.** State
   which platforms/numpy builds the `CONFORMANCE_FLOOR` is guaranteed on, and run the
   conformance suite on at least one non-CI-default platform (or relax all
   equivalence asserts to platform-stable forms). The suite is the cross-repo
   contract; it must be portable to be trustworthy in consumers' CIs.
6. **Prove the contract with one real consumer (Epic 3).** Land the pipeline-core
   `PredictionFrame` re-export shim and have pipeline-core CI run
   `views_frames.conformance.assert_frame_contract` against its own adapter output.
   This is the highest-value *next* milestone after the small fixes.
7. **Decide `MetricFrame` ownership/schedule** (here vs views-evaluation) and put it
   on the roadmap with a date, since the README leans on C-48 as motivation.

---

## Appendix — what I inspected

- **Source (all read):** `src/views_frames/{__init__,index,spatial_level,protocols,
  _validation,_typing,metadata,prediction_frame,feature_frame,target_frame}.py`,
  `io/{npz,arrow}.py`, `conformance/__init__.py`; `src/views_frames_summarize/
  {__init__,_common,collapse,point,interval,aggregate,conformance}.py`.
- **Docs:** README (incl. §0a Quickstart, §13a), CLAUDE.md, GOVERNANCE.md,
  CHANGELOG.md (v0.3.0 entry), ADR index + 011–017, the CIC set.
- **Tests (read + run):** all of `tests/` including `test_summarize_scale.py`,
  `test_proxy_adapter.py`, `test_import_enforcement.py`, `test_index`, `test_io`,
  `test_frames`, `test_conformance`, `test_properties`.
- **Executed (read-only, numpy 1.26.4 — the declared floor):** `ruff check .` → clean;
  `mypy --strict src/` → green (21 files); `examples/quickstart.py` → runs;
  `pytest` → **RED: 7 failures in `test_summarize_scale.py::test_map_estimate_matches_per_row_reference`**
  (`shape1` seeds 7/13; `shape2` all seeds); remainder green; `hdi` equivalence +
  memory-bound guard pass. **Remote GitHub CI on `f38e14a` → green** (the portability
  split in §5/§7.1).
- **Not changed:** no source files, no staging, no commit, no branch. The only
  working-tree change is this report under `perspectives/round02/`; the untracked
  `perspectives/round02/` peers (other repos' reviews) were pre-existing.
