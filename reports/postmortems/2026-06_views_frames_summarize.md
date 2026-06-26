# Postmortem — `views_frames_summarize`, the posterior-summary sibling (v0.2.0 → v1.6.0)

| Field | Value |
|---|---|
| Subject | The sample-axis summarization package: why it was carved out of the leaf, the estimator family it grew (point, interval, tower, exceedance, expected shortfall), the bugs its consumers found, and the falsification discipline that became its release gate |
| Window | 2026-06-21 (ADR-017, `collapse` removed from the leaf) → 2026-06-25 (`v1.6.0`, `expected_shortfall` published to PyPI) |
| Repos | `views-frames` (all code); `views-faoapi` + `views-reporting` (the consumers of record whose adoption found every real bug) |
| Governing docs | ADR-017 (sibling charter), ADR-019 (tower), ADR-021 (exceedance), ADR-022 (expected shortfall); the Summarize CIC; register C-32/C-33/C-34/C-44/C-45/C-49/C-50/C-55/C-56/C-57; research lab `research/map_hdi/` |
| Outcome | A single, tested, **distribution-agnostic** home for the volatile posterior statistics that were duplicated ~500–600 LOC across two repos. Five estimators shipped additively under the v1.0 freeze. Every correctness bug was found by a consumer running real data; the deepest lessons were epistemic — *a green number, a passing test, or a low benchmark score is the easiest place to hide a wrong answer.* |
| Companion | The tower's two production bugs (C-44/C-45) and the four-release scramble are documented in full in [`2026-06_tower_estimator_c44_c45.md`](2026-06_tower_estimator_c44_c45.md); this postmortem covers the **package as a whole** and refers there for that chapter rather than repeating it. |

---

## 1. What we did, and why

The leaf carries posteriors; it must not *interpret* them. But two consumers — `views-faoapi`
(serving VIEWS conflict forecasts to the UN FAO) and `views-reporting` — each independently
re-derived the same statistics from a `(month, priogrid)` posterior: a MAP-like mode, highest-density
intervals, quantiles, and a conservation-correct cross-level aggregation where `HDI(sum) ≠ sum(HDI)`.
The code was ~500–600 LOC, subtle (zero-mass MAP rules, nesting, joint-sampling), and **volatile** —
"the way we collapse uncertainty will change and expand."

ADR-017 ratified the answer: this lives in a **second package in the same repo**,
`views_frames_summarize`, depending on `views_frames` + numpy only, never the reverse (import-DAG
enforced). Volatile, expanding statistical logic does **not** belong in the maximally-pinned leaf
(SAP); but it *is* worth centralising once, because correctness is hard and it was being
re-implemented in 2–3 places. `collapse` and the string-keyed statistics registry were **removed
from the leaf** (a breaking change made while pre-1.0); the leaf kept only the *structural* sample
facts (`sample_count`, `is_sample`).

The charter is bounded — that boundedness is the whole anti-bloat mechanism. The package **may**
contain sample-axis point/interval estimators and conservation-correct aggregation; it **must not**
contain IO, domain/geographic data, actuals or scoring (that is views-evaluation), or any `views_*`
import except `views_frames`.

## 2. How it unfolded — the arc

- **The base estimators (v0.2.0).** `collapse(frame, reducer)`, `map_estimate` (histogram MAP),
  `hdi`, `quantiles`, and `aggregate_distributions` (element-wise joint-sample sum to a coarser
  level). Index-aligned arrays out; the caller holds the index (ADR-017 convention).
- **The tower (v1.1.0 → v1.3.0, ADR-019).** A coherent, reproducible, eventually
  **distribution-agnostic** point+interval summary — the constrained-nested HDI tower, the
  mass-aware tower-tip MAP, and a conservative bimodality flag. This is the eventful chapter: an
  unauthorized publish, two silent-correctness bugs (C-44 minority-duplicate collapse; C-45 a
  count-domain magnitude rule smuggled into a domain-agnostic leaf), both found by the faoapi
  integration spike, four releases in ~36 hours. **See the companion postmortem.** Its design was
  derived in the `research/map_hdi/` lab against a 108-cell synthetic battery with known analytic
  modes.
- **`exceedance` (v1.5.0, ADR-021, Epic 9).** Per-row survival fraction `P(Y > c)` + a
  `collapse`-compatible `exceedance_reducer`. Required, no-default thresholds (the policy is the
  consumer's, never a config); strict `>` (D-08); geography-blind (country exceedance =
  `aggregate_distributions` → `exceedance`). Registered C-49 (aggregate-tail joint-sampling) and
  C-50 (silent NaN onset deflation), both resolved by fail-loud guards.
- **`expected_shortfall` (v1.6.0, ADR-022, Epic 10).** The worst-case tail mean / CVaR — the mean of
  the worst `⌈t·S⌉` draws — as the principled, coherent companion to `exceedance`. **`max` is never
  offered** (D-10: it is the highest-variance, non-reproducible summary). **Best-case ships no code**
  (a low quantile + `exceedance(0)` express it — CRP, don't add a symbol no one reuses). Registered
  C-55/C-56.
- **The pre-publish falsification audit (2026-06-25).** Before promoting v1.6.0 to PyPI, a combined
  `/falsify` audit of `exceedance` + `expected_shortfall` found one real gap: the fail-loud guard was
  `np.isnan(...)`, which catches NaN but **not ±inf**. An infinite draw — always an upstream bug —
  silently produced an `inf` "worst case" or a bug-masking probability. Fixed by widening the guard
  to `not np.isfinite(...).all()` in both cores (C-50/C-56), with a new C-57 recording that the
  frozen `map_estimate` still *crashes* (an `IndexError`) on `inf` draws — a pre-existing,
  freeze-locked inconsistency, not a v1.6.0 blocker. Then published.

## 3. What went well

- **The consumer feedback loop was the best test suite we had.** Every real bug (C-44, C-45) was
  found by *adopting the leaf in faoapi against the real forecast cache*, not by our own tests. The
  cadence — adopt → audit → report → fix → re-adopt — was fast and decisive. The package's
  correctness is, in practice, underwritten by faoapi's CI re-running the published conformance
  contracts on real frames.
- **WET before DRY, applied deliberately.** Each estimator is its own module with its own private
  core (`exceedance._exceed`, `expected_shortfall._expected_shortfall`); they reuse only the stable
  primitives (`block_apply`, `ROW_BLOCK`, `AnyFrame`). We explicitly *refused* to extract a shared
  "tail reducer" abstraction. Two shallow, independent duplications beat one premature coupling — the
  concerns (a survival count vs a tail mean) change for different reasons.
- **Falsification as a release gate caught what green tests could not.** The `inf`-draw finding is
  the canonical case: every test passed, coverage was 100%, and the guard was *still* an incomplete
  expression of its own stated intent ("a draw must be a usable finite number"). `/falsify` —
  attacking the claim rather than confirming it — found it before PyPI did.
- **Laws as tests.** The conformance suite asserts the estimators' *mathematical* laws (exceedance in
  `[0,1]`, non-increasing, `P(>−inf)=1`; expected shortfall in `[min,max]`, non-decreasing as the
  tail deepens, `ES(t) ≥ the (1−t) quantile`). These caught regressions a value-based test would
  miss and document the contract executably.
- **Saying no shipped less code.** ADR-022's "best-case ships no code" and "`max` is never offered"
  are the package at its best: the right answer was often a *deletion* or a *non-addition* (C-45 was
  fixed by removing a harmful special case; the best-case need was met by composing existing
  functions). The bounded charter did its job.

## 4. What went wrong, and what we missed

- **A domain assumption was smuggled into a domain-agnostic package, and our own tests masked it
  (C-45).** ADR-019 introduced a `max(draws) ≤ 1.0 → 0` "quiet row" rule — a hard-coded
  *magnitude* threshold — in a package whose constitution (ADR-003/014) forbids inferring meaning
  from values. It zeroed every cell of a `[0,1]`-valued target and erased low-intensity counts. Our
  synthetic tests used values above 1, so it never tripped. **We had the principle and did not apply
  it; we had the tests and they tested the wrong shapes.**
- **A premature "fixed" claim on unrepresentative data (C-44).** A partial fix was declared done
  against a synthetic case (30 identical body values) that did not resemble real cells (a distinct
  continuous body + a few exact zeros). Only the consumer's "case L" exposed that the fix never
  engaged. Confidence outran evidence.
- **A process failure: an unauthorized publish.** During the v1.1.0 release a pre-confirmation
  ("we're ready") was treated as standing authorization for the specific irreversible steps
  (merge-to-main, create-Release → PyPI). It was not. Nothing was lost (PyPI versions are
  immutable), but trust was; a strict *per-step* authorization protocol followed and made every
  subsequent release boring.
- **An incomplete guard that read as complete.** The NaN guard (`np.isnan`) looked like "reject
  malformed draws" but only covered half of "non-finite." `inf` slipped through for a full release
  cycle until the falsify audit. The guard expressed a *narrower* policy than it intended.
- **The `research/map_hdi/` benchmark oracle was circular, and we nearly trusted it.** The lab that
  designed the tower scored point estimates against a stored `true_mode` that was *itself* a
  histogram argmax — so a histogram-MAP "won" by sharing the oracle's binning. A naive
  optimize-the-metric loop would have *kept the circular artifact and rejected the real C-32 fix*.
  What saved us was the side-diagnostics that re-scored against an independent analytic mode — i.e.,
  distrusting the measure, not optimizing it.

## 5. What surprised us

- **The robust estimate *disagrees* with the incumbent, and the incumbent is the suspect.** On real
  faoapi cells the tower-tip shorth lands on the dense low cluster while the old histogram MAP lands
  on a sparse high cluster. The downward disagreement is largely the **C-32 bias being corrected** —
  but it is a large, visible semantic shift a consumer must consciously accept, not a silent
  improvement.
- **The best fixes were subtractions.** C-45 was resolved by *deleting* the magnitude rule (the
  mass-aware tip already handled zero-inflation by density); the `inf` fix *completed* an existing
  guard rather than adding a new policy; the best-case summary was met without a new function. The
  package improved most when it grew *less*.
- **A metric can be deterministic, un-gamed, and still wrong.** The map_hdi oracle and the `inf`
  guard are the same lesson in two domains: the immutable-harness / passing-test discipline protects
  against *gaming* and *regression*, but not against a measure (or a guard) that is honestly built
  and *incomplete*. Only adversarial falsification closes that gap.
- **`hdi_tower` was affected by both tower bugs**, contrary to the first guess that "only the point
  is at risk." The shared zero-mask and the nested-through-the-narrowest-floor construction
  propagated both defects into the published intervals.

## 6. What would be easier next time

- **Test against real (or realistic) distribution shapes from commit one.** A `[0,1]`/`beta` field, a
  tight sub-1 mode, a distinct continuous body with a few exact zeros, a replay of the real cache
  shape — a handful of cases would have caught *both* tower bugs before release. This matrix is now
  baked into the suite; keep it, and keep a read-only replay against the consumer's data shape.
- **Audit every default for a hidden domain assumption, at ADR time.** Any magic constant (`1.0`, a
  bin count, a magnitude threshold) in a domain-agnostic package is guilty until proven agnostic. Ask
  before the code, not at the third release.
- **Make `/falsify` a standing pre-publish gate for every estimator.** It found the `inf` gap that
  100% coverage missed. The cost is small; the class of bug it catches (incomplete guards,
  silent-wrong outputs) is exactly the one this package exists to avoid.
- **Validate the benchmark before trusting it.** For any optimize-a-metric work, check the oracle for
  *circularity* and *proxy divergence* before believing a single score. The map_hdi loop would have
  shipped the wrong estimator on a trusted-but-circular metric; the audit, not the loop, produced the
  result.
- **Treat "fixed" as a claim that requires the consumer's exact data.** When a report ships a
  paste-ready truth table, run *that table* (and the real cells) before asserting resolution.
- **Keep the per-step release protocol and the WET-before-DRY default.** Both cost almost nothing
  once internalised and each removed a whole class of failure (an unauthorized publish; a premature
  shared abstraction).

## 7. Final state

`views_frames_summarize` ships five estimator families — `collapse`/`map_estimate`, `hdi`/`quantiles`,
the coherent tower (`hdi_tower`/`tower_point`/`bimodality`/`summarize_tower`), `exceedance`, and
`expected_shortfall` — plus conservation-correct `aggregate_distributions`, all additive under the
v1.0 freeze (`CONFORMANCE_FLOOR` stayed `1.0.0` throughout). The summary is coherent (nested,
reproducible), robust (immune to minority-duplicate collapse), distribution-agnostic (no magnitude
assumption; an off-by-default opt-in for count consumers), and fail-loud on non-finite draws.
Resolved: C-33/C-44/C-45/C-49/C-50/C-55/C-56. Open and accepted: C-32 (a fully principled convergent
mode is still #89), C-34 (bimodality recall is a documented conservative trade), C-57 (the frozen
`map_estimate`'s ugly failure on `inf` draws, a future hardening). The consumer (faoapi) re-runs the
published conformance suite on its own real frames in CI.

The one-sentence lesson: **a posterior summarizer is judged not by whether its tests pass but by
whether it tells the truth on the ugly real distributions it will actually meet — and the fastest way
to a wrong number is to trust a green test, a clean metric, or a tidy synthetic case instead of
attacking it on the data and shapes the consumer actually carries.**
