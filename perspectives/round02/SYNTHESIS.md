# Round-02 review — synthesis (fact-checked)

> **Author:** Claude (Opus 4.8), the views-frames maintainer agent.
> **Date:** 2026-06-21. **Reviewed at:** v0.3.0, `main` @ `f38e14a`.
> **Inputs:** the five round-02 consumer reviews in this directory (appwrite, faoapi,
> pipeline-core, postprocessing, reporting).
> **Method:** read all five in full; deduplicated each finding against the round-01
> SYNTHESIS + the risk register (C-01..C-23) and the standing scope guardrails
> (transport-not-analysis; `MetricFrame` out of the leaf); then **independently
> verified each finding against the code — and crucially *ran the suite on the
> declared numpy floor***, which the round-01 process and Epic 4 never did.
> **This document is a reflection only. No source, no register, no version, no
> sibling repo was changed.** Register candidates below are proposals for a later
> `/register-risk`, not registrations.

---

## 0. Headline

The five reviews **validate Epic 4**: every round-01 finding (C-19..C-23) is confirmed
fixed in code, and `cross_level_align`'s time-aware upgrade is repeatedly called a
correctness win "beyond what was asked." But two reviewers who **actually ran the
suite** (pipeline-core, appwrite) found a sharp regression that the three **static**
reviewers missed — and that I missed in Epic 4:

> **F-A — the suite is GREEN in CI but RED on the declared numpy floor.** On
> `numpy==1.26.4`, `pytest` reports **15 failed, 111 passed**; on the CI-locked numpy
> 2.x it is all-green. Every failure is `test_summarize_scale.py::test_map_estimate_matches_per_row_reference`,
> which asserts **bit-exact** (`np.array_equal`) float32 equality between the vectorized
> `map_estimate` and the per-row `numpy.histogram` reference. The two float paths differ
> by **~1 ulp (max abs 1.86e-7; `np.allclose(rtol=1e-5)` passes)**. The *library is
> correct*; the *test over-asserts* and is non-portable across the supported numpy range.

**I reproduced this directly:** `uv run --with numpy==1.26.4 pytest` → `15 failed, 111
passed`; `uv run pytest` (numpy 2.x) → all green. This is **the same anti-pattern C-19
was about** ("green in default env, red on the supported floor") — re-introduced by the
very test meant to *prove* the C-22 fix, and hidden because the CI `type-floor` job runs
**mypy only**, while the `check` job runs pytest on the **locked numpy 2.2.6**. No CI job
runs pytest at the floor.

The meta-signal is itself the proof: **only the 2 reviewers who executed the suite caught
it; the 3 who trusted the green check did not — reporting and postprocessing even praised
the "bit-for-bit" claim as a strength.** A green checkmark is currently hiding a red suite.

---

## 1. Verdict table (every distinct finding)

| ID | Finding | Verdict | Disposition |
|----|---------|---------|-------------|
| **F-A** | `map_estimate` bit-exact test RED on numpy floor (15 fails, ~1 ulp); CI hides it (type-floor=mypy only, check=numpy 2.x) | **Confirmed (ran it)** | **New — Tier 2 register candidate. Highest priority.** |
| **F-B** | `hdi`/`quantiles` not memory-blocked like `map_estimate`; scale guard covers only `map_estimate` | **Confirmed** | New — Tier 3 register candidate |
| **F-C** | Injected `cross_level_align` mapping is a Python `dict`, materialized via `list(...)` — O(N) caller allocation at grid scale | **Confirmed** | New — Tier 3 register candidate |
| **F-D** | `CONFORMANCE_FLOOR` stayed `0.1.0` (and a test pins it) despite a breaking contract change + a new published law | **Confirmed** | New — Tier 4 register candidate (governance) |
| **F-A′** | "bit-for-bit identical to v0.2.0" claim (CHANGELOG:35, test comment) is false on the floor; `point.py` docstring honestly says "float32 precision" — internal contradiction | **Confirmed** | Folds into F-A |
| **F-G** | `_ROW_BLOCK = 1<<16` is a hard-coded magic constant, not a tunable kwarg | **Confirmed** | New — minor (fold into F-B fix) |
| **F-H** | `map_estimate` is a ~100-line bespoke replica of numpy's histogram internals — maintenance-fragile, numpy-version-coupled | **Confirmed** | New — maintainability; F-A's fix should reduce it |
| **F-J** | No consumer-side `select`/subset or frame-level `reindex(other) -> Frame` | **Confirmed** | **Already deferred (F12, Epic 5)** — promote: 2 consumers rate it top gap |
| **F-K** | Interval API asymmetry: point estimates return frames, `hdi`/`quantiles` return bare arrays | **Confirmed (by design, ADR-017)** | Design choice; document, don't "fix" |
| **F-L** | `Persistable.save(directory: str)` vs concretes' `Path \| str` | **Confirmed** | Already deferred (F14); trivial real fix |
| **F-M** | `searchsorted` carries `get_indexer` (not numpy) semantics under a numpy name | **Confirmed** | Already deferred (F14) |
| **F-N** | `test_falsification_*` stubs in the main suite couple CI-green to README prose | **Confirmed** | New — minor (test-hygiene) |
| **F-O** | The breaking `cross_level_align` semantics + uniqueness stance have no dedicated ADR (only a note in ADR-014) | **Partially confirmed** (ADR-014 has a v0.3.0 note; no ADR-018) | New — minor (governance) |
| **F-E** | `MetricFrame` / provenance fields (`run_id`/`data_version`) still absent | **Confirmed** | **Deferred-by-design** (out of leaf, ratified). Actionable part = README honesty |
| **F-examples** | No runnable `cross_level_align`/`aggregate_distributions` example | **Confirmed** | New — minor |
| **F-import** | `pytest` (bare) fails `ModuleNotFoundError` without editable install / `uv run` | **Partially confirmed** (works under `uv run`; reviewer ran bare) | Minor / doc note |
| **F-cross-repo** | No real sibling repo runs the conformance suite in its CI | **Confirmed** | **Known — owner's migration (Epic 3 / F15)**, not leaf work |

---

## 2. Confirmed findings — detail & evidence

### F-A (Tier 2) — the green-check illusion: the suite is red on the supported floor
- **Evidence (run by me):** `uv run --with numpy==1.26.4 pytest` → `15 failed, 111 passed`;
  `uv run pytest` → all green. All 15 are `test_map_estimate_matches_per_row_reference`
  (3 shapes × 5 seeds). Sample diff: `-0.10755503` (vectorized) vs `-0.10755488`
  (reference) — ~1.5e-7, one float32 ulp.
- **Root cause:** `test_summarize_scale.py:80` uses `np.array_equal` (bit-exact). The
  vectorized `_batched_map` recomputes bin edges via `linspace`/division; on numpy 1.26.4
  that path and `numpy.histogram`'s differ by 1 ulp on the bin **centre** (the densest-bin
  *selection* still matches). On numpy 2.x they coincide.
- **Why CI hides it:** `.github/workflows/ci.yml` — the `type-floor` job runs `mypy` only;
  the `check` matrix runs `pytest` on the lockfile's numpy (2.2.6). **No CI job runs pytest
  at `numpy==1.26.4`.** This is exactly the C-19 gap (floor not behaviour-checked), one
  layer over.
- **Overclaim (F-A′):** `CHANGELOG.md:35` ("stays bit-for-bit identical to v0.2.0") and the
  test's own comment assert bit-exactness, while `point.py`'s docstring correctly says the
  centre "matches to float32 precision." The test is **stricter than the code's documented
  contract** — the contract is float32-precision, the test demands bit-equality.
- **Severity rationale (Tier 2):** not silent data corruption (the library output is
  within-ulp correct), but a **structural trust failure**: the package's headline promise is
  "import our conformance suite into *your* CI," and the suite is non-portable across the
  package's own declared `numpy>=1.26` range. A consumer pinning the floor sees 15 red. The
  green checkmark actively misleads.
- **Fix shape (for a later PR, not now):** assert *selected-bin-index equality* + centre
  within float32 tolerance (or have `_batched_map` and the reference share **one** binning
  helper so equivalence is true by construction); **add pytest at the floor to CI**; scope
  the CHANGELOG claim to "float32 precision / bit-exact on numpy ≥ 2.0," or raise the floor.

### F-B (Tier 3) — memory discipline is inconsistent across the summarizer family
- **Evidence:** `interval.py:28` `np.sort(values, axis=-1)` (full-size sorted copy),
  `:36` `widths = srt[...,k:] - srt[...,:s-k]` (another ~full-size temp), `:45`
  `np.quantile(...)`. None are row-blocked the way `point.py` is. The scale guard
  (`test_summarize_scale.py:109`) asserts bounded memory for **`map_estimate` only**.
- **Honest severity scoping:** the `hdi`/`quantiles` temporaries are `O(rows × S)` —
  *data-proportional* (~2–3× the input), **not** the `O(rows × bins)` *multiplier* that
  motivated C-22. So it is a real OOM-class liability on the #181 grid path but a lesser one
  than the matrix C-22 killed. The sharper half of the finding is the **guard hole**: a
  future regression on the interval path is uncaught. (Tier 3.)

### F-C (Tier 3) — the injected-mapping interface fights the scale thesis
- **Evidence:** `cross_level_align(mapping: Mapping[tuple[int,int],int], …)` (`index.py:182`)
  is materialized by `np.array(list(mapping.keys()))` / `list(mapping.values())`
  (`:217,223`). At the full-grid time-varying regime (~10.5M `(time,unit)` keys) the consumer
  must build, hold, and hand over a Python-object dict, and the leaf rebuilds it via O(N)
  Python `list(...)`. The internals were vectorized; the *interface* left the dominant
  allocation at the boundary.
- **Fix shape (later):** an array-triple overload
  (`cross_level_align_arrays(map_time, map_unit, map_target, target_level)` or
  `map_keys:(M,2)`, `map_vals:(M,)`) so a producer stays vectorized end-to-end. Additive
  (MINOR). Benchmark before committing — three reviewers raised it; none proved the dict is
  actually the bottleneck at the real grid size, so this wants a measurement, not a reflex.

### F-D (Tier 4) — conformance-floor governance loose end
- **Evidence:** `CONFORMANCE_FLOOR = "0.1.0"` (`conformance/__init__.py:24`), pinned by
  `test_conformance.py:73`, unchanged though v0.3.0 made a **breaking** `cross_level_align`
  signature change and **added** `assert_cross_level_alignment_law`. GOVERNANCE advertises a
  SemVer-for-contract floor. Ambiguity: does the floor track only the *structural frame
  contract* (genuinely unchanged) or the *whole published conformance surface* (changed)?
- **Disposition:** state the policy next to `CONFORMANCE_FLOOR` (and in GOVERNANCE); if it
  tracks the laws, the breaking change warranted a bump. Tier 4 — documentation/governance
  consistency, no code defect.

### Minor confirmed (fold into the above or a cleanup PR)
- **F-G** `_ROW_BLOCK` → an overridable keyword arg (natural companion to the F-B fix).
- **F-H** the bespoke histogram is the repo's most fragile code; the F-A fix (share one
  binning helper / drop bit-exactness) is also the F-H mitigation.
- **F-N** move `test_falsification_*` out of the unit lane (their decisions are now ADRs) so
  CI-green tracks behaviour, not README prose.
- **F-O** add a short ADR-018 (or amend ADR-014/015) recording the `(time,unit)`-keyed
  breaking change + the uniqueness stance as first-class decisions.
- **F-examples** add `examples/cross_level.py` (build a `(time,unit)→country` map, align,
  `aggregate_distributions`, the `HDI(sum) ≠ sum(HDI)` point).
- **F-L / F-M** `Persistable.save` → `Path | str`; reconsider `searchsorted` naming (F14).
- **F-import** one-line "tests need `uv run` / editable install" note by the test command.

---

## 3. Deferred-by-design / out-of-scope (apply the scope guardrails)

- **F-E (`MetricFrame` / provenance fields):** stays **out of the leaf** — ratified
  (boundary decisions; `MetricFrame` is `(target,step,unit)`-keyed, not a frame; eval output
  belongs to views-evaluation). Three reviews note the README "front-loads C-48 as
  motivation" while the cure is undelivered. The only **in-scope** action is *doc honesty*:
  soften the README framing from "the cure" to "the substrate for the cure," and put the
  C-48/`MetricFrame` decision on a dated line (Epic 5 / v2 key-protocol question). **Do not
  build `MetricFrame` here.**
- **F-J (`select`/subset + `reindex(other) -> Frame`):** legitimately **in-scope** — this is
  structural row selection (transport), not analysis. It is the deferred **F12**, and faoapi
  rates it the single biggest consumer-facing gap. Candidate to **promote** in Epic 5.
- **F-K (intervals as frames):** by-design per ADR-017 (intervals return index-aligned
  arrays; the caller holds the index). Not analysis-creep, but also not a defect — document
  the asymmetry rather than change it.
- **F-cross-repo (F15):** the keystone proof remains the **owner's migration** (a re-export
  shim + `assert_frame_contract` in a real consumer's CI). postprocessing **re-volunteered**
  as the first live consumer. Not leaf work; I will not touch sibling repos.

---

## 4. Register candidates (for a later `/register-risk` — not registered here)

| Candidate | Tier | One-line | Trigger |
|-----------|------|----------|---------|
| **C-24** | 2 | `map_estimate` bit-exact equivalence test is non-portable: green on numpy 2.x, **15 red on the `numpy==1.26.4` floor**; no CI job runs pytest at the floor | A consumer pins numpy 1.26 (inside the declared range) and runs the suite / the published conformance suite |
| **C-25** | 3 | `hdi`/`quantiles` allocate full-grid temporaries (not row-blocked) on the #181 reduction path, with no memory guard | A consumer runs `hdi`/`quantiles` over the full grid (~10.5M rows) |
| **C-26** | 3 | `cross_level_align` injected mapping is a Python `dict` materialized via `list(...)` — O(N) caller allocation at grid scale | A consumer injects a full-grid time-varying `(time,unit)→target` mapping |
| **C-27** | 4 | `CONFORMANCE_FLOOR` unchanged + pinned by a test despite a breaking contract change + a new published law; floor-vs-surface policy unstated | A consumer relies on `CONFORMANCE_FLOOR` to know which contract version it conforms to |

(C-24 is the C-19 family — "the floor is checked for types but not behaviour" — and is the
load-bearing one.)

---

## 5. What this says about Epic 4 (honest reckoning)

**Epic 4 was largely validated — and it introduced F-A.** Two things I should own:

1. **The C-19 fix was incomplete.** I closed the *type* floor gap (the `type-floor` CI job)
   but the *behaviour* floor gap reopened immediately, because (a) the new scale test asserts
   bit-exactness and (b) the type-floor job runs mypy only. **I ran `mypy` on the floor in
   Epic 4; I never ran `pytest` on the floor.** Had I, I'd have caught the 15 failures before
   release. The process lesson is concrete: the floor gate must be *behaviour*, not just
   types.
2. **My "bit-for-bit identical to v0.2.0" claim was an overclaim** — true only on numpy 2.x.
   The honest claim is "identical to float32 precision (bit-exact on numpy ≥ 2.0)." `point.py`
   actually says the right thing; the CHANGELOG and the test do not.

This does not undo the epic — the scale *win* (bounded memory) is real and guarded, the
cross-level correctness fix is genuine, and the reviewers independently confirm both. But the
release shipped a non-portable suite behind a green check, which is precisely the class of
problem this whole review process exists to catch. It caught it.

---

## 6. Recommendation (for your decision — no action taken)

Two tiers, and I'd **split them**:

- **A fast hotfix PR, ahead of any Epic 5** — F-A only: make the MAP equivalence test
  tolerance/bin-index based, add **pytest at the numpy floor** to CI, and scope the CHANGELOG
  claim. This is hours of work and it removes a live "green hides red" state that undermines
  the package's central promise. It should not wait behind a backlog.
- **Epic 5 (hardening round 2)** — the confirmed Tier-3/4 + promoted backlog, sequenced:
  C-25 (`hdi`/`quantiles` blocking + guard), C-26 (array-mapping overload, **after a
  benchmark proves the dict is the bottleneck**), C-27 (floor governance), F-J (`select`/
  `reindex`-to-frame — the top consumer ask), and the minor cleanups (F-G/H/L/M/N/O,
  examples). Plus the **doc-honesty** pass on C-48/`MetricFrame` framing.
- **Unchanged stance:** `MetricFrame` stays out of the leaf; the real cross-repo proof (F15)
  is your migration, and postprocessing has volunteered to be the first live consumer — that
  is the highest-value milestone of all, and it is not leaf work.

My lean: **do the F-A hotfix now**, then decide Epic 5 vs. freeze-and-migrate. The reviews
are unanimous that the remaining leaf issues are "thinner and more specialized" — the biggest
lever left is a real consumer, not more leaf surface.
