# Technical Risk Register

| Register Info     | Details                              |
|-------------------|--------------------------------------|
| Project           | views-frames                         |
| Owner             | VIEWS platform maintainers           |
| Last Updated      | 2026-07-31                           |
| Total Concerns    | 73                                   |
| Open Concerns     | 12                                   |
| Resolved Concerns | 61                                   |
| Disagreements     | 12                                   |

---

## Tier Definitions

| Tier | Severity | Description |
|------|----------|-------------|
| 1 | Critical | Silent data corruption or output correctness risk. Requires immediate attention. |
| 2 | High | Structural fragility that will cause failures under realistic change scenarios. |
| 3 | Medium | Maintainability or coupling issues that increase cost of change. |
| 4 | Low | Code quality concerns that do not affect correctness or reliability. |

## Status (open concerns)

Tier answers *how bad*; **Status answers *can we act***. At 17 open concerns — 13 of them
Tier 3 — tier alone stopped discriminating, and "17 open" read as 17 things someone might
have to do when most cannot be acted on at all. Every open entry carries one:

| Status | Meaning |
|--------|---------|
| **actionable** | Nothing blocks it. It can be closed with work available today; the entry says roughly how much. |
| **awaiting — `<precondition>`** | Cannot be "fixed" — it waits on a MAJOR bump, a consumer receipt, a research result, or another repo. Correct state is *visible and dormant*, not *neglected*. Naming the precondition is mandatory; "awaiting" with no named condition is a bug in the entry. |

Read the register by Status first, Tier second: **Status is the work queue, Tier is the
ordering within it.** An `awaiting` entry is not a backlog item and must not be treated as
one — re-auditing it produces the same answer its precondition already gives.

---

## Open Concerns

> Seeded 2026-06-21 from four internal design critiques (kept local, not tracked in the repo)
> and the 11 falsification stubs (`tests/test_falsification_*.py`). IDs are permanent; the gap at
> **C-04** is intentional (the original "SpatialLevel slippery slope" finding was merged into
> **C-18**).
>
> **Reconciled against v1.0.0 (2026-06-22).** The design-phase concerns (C-01, C-02, C-03,
> C-05, C-06, C-08, C-10, C-12, C-15, C-16, C-18) were *resolved-by-decision* in README §13a
> and formalised by ADRs 011–016, all of which merged and shipped/froze in **v1.0.0**
> (ADR-018) — they are now in **Resolved Concerns**. C-01/C-08/C-12 are resolved-by-decision
> and persist only as **frozen-invariant guards** (their triggers protect the frozen scope).
> **The 12 open concerns are grouped under *Causal clusters* in Register Conventions —
> that list is the single authority and this preamble deliberately does not restate it**
> (it drifted when it did). In one line each: **summarize-estimator coherence (#89)**
> {C-32, C-34, C-43, C-57}; **reconcile method + governance** {C-62}; **cross-repo coordination** {C-13, C-46};
> **immutability enforcement** {C-66}; **scale & footprint awareness** {C-71, C-73}; plus the
> cross-cutting **verification-completeness** theme {C-74, C-75} and the
> **freeze-as-root-cause** meta-cluster that spans several of them. Read the
> Conventions entries for *why* each is open — most are waiting on a precondition, not on
> effort. **The 2026-07-31 pre-release sweep added C-74/C-75/C-76** — all three are
> *ship-readiness* items (unarmed gates, fossil tests, a frozen-surface wording call), none
> blocking, and unlike most of the register they are cheap and actionable *now*.

### C-13: concentration risk — single point of coordination failure (accepted / monitored)

| Field | Value |
|-------|-------|
| ID | C-13 |
| Tier | 3 (recalibrated from 2 on 2026-07-31, `review-rr` strategic) |
| Status | **awaiting** — the next MAJOR bump (this entry *is* its pre-tag checklist) |
| Source | expert-review (2026-06-20) |
| Trigger | **When a MAJOR bump is opened — before tagging:** confirm every consumer repo has an adoption issue filed and a pinned floor per GOVERNANCE §coordinated-bump, and pair the bump with the **freeze-cluster rider list** (C-66's `setflags` enforce + its red test, C-57's `np.isfinite` guard on `map_estimate`, C-43's shared-binning extraction) — a MAJOR that fans out without carrying its riders spends the coordination budget for nothing. |
| Location | `README.md` §12 (~12 register items, 3+ repos); `GOVERNANCE.md` (coordinated-bump process) |
| Cross-refs | D-06 (the WIP-sequencing disagreement, resolved-by-events), C-05 / C-10 (resolved — owner + coordinated-bump process), ADR-018 (the freeze this fans out), the **freeze-as-root-cause** meta-cluster (the rider list). |

The leaf's breadth is both its value and an inherent concentration risk (critique_01 §3.7): it is structurally the single point every consumer pins. **Mitigation shipped** — a minimal, stable, **frozen v1.0.0** (ADR-018) gives consumers a contract that will not churn, and ADR-016 / GOVERNANCE name the owner and the coordinated MAJOR-bump process (C-05, C-10 resolved). **Residual is accepted and monitored:** the fan-out cost of any future MAJOR is irreducible; the control is the GOVERNANCE process, watched as consumers adopt.

**Tier 3, recalibrated 2026-07-31.** Originally Tier 2, but Tier 2 means *structural fragility that will cause failures under realistic change scenarios* — this entry describes an irreducible **cost** incurred under a process that already exists and has never failed, not a fragility. It is an **accepted standing condition** kept in Open solely so the coordinated-bump discipline stays visible, and its trigger now does real work: it is the pre-tag checklist for the one event that makes concentration bite. See also D-06.

---

### C-32: `map_estimate` lowest-index tie-break biases the mode toward zero

| Field | Value |
|-------|-------|
| ID | C-32 |
| Tier | 2 |
| Status | **awaiting** — #89 estimator redesign (research); `tower_point` is the shipped mitigation |
| Source | views-faoapi integration spike (2026-06-23) |
| Trigger | When a consumer adopts `views_frames_summarize.map_estimate` as a drop-in for an existing histogram-MAP (e.g. faoapi's `PosteriorDistributionAnalyzer`), check the tie-break on its real posteriors — on right-skewed, zero-inflated, low-sample (~32-draw) distributions the lowest-index tie-break systematically pulls the mode toward the left tail (zero), shifting published modes downward. **Tier watch (2026-07-31):** the FAO forecast path is now live (faoapi #100/#242 in execution), and the *only* thing holding this at Tier 2 rather than Tier 1 is that the leaf publishes nothing itself. If faoapi (or any consumer) adopts `map_estimate` for **published** modes, the bias stops being latent and this entry becomes Tier 1 — route them to `tower_point` instead. |
| Location | `src/views_frames_summarize/point.py::_batched_map` (the `np.argmax(counts, axis=1)` tie-break) (`np.argmax(counts, axis=1)` — lowest-index tie-break). Evidence: a views-faoapi integration spike (2026-06-23). |

**Symptom.** At 32 draws in 100 bins the histogram peak is almost always a multi-way tie; `np.argmax` takes the lowest index = leftmost = smallest value, so for a right-skewed, zero-inflated posterior the MAP is dragged toward zero. The faoapi spike measured this against the production estimator: **~21% of active cells diverge one-directionally (NEW MAP ≤ OLD MAP always), up to 7.9 in ln-space** (≈2,700× in count-space). This is the **C-24** portability fix's blind side — C-24 removed the numpy-version *instability* of the `density = count/width` tie-break, but the lowest-index choice it landed on carries a *directional bias* C-24 never weighed.

**The real problem is deeper than the tie-break.** The mode is the only one of our point/interval estimates that is a functional of the *density* rather than the *CDF*. Mean is an average; quantiles/HDI are order statistics — both need only the samples ranked, which is **why the spike found HDI bit-identical**. The mode needs an *estimated density* and its argmax, and density estimation is inherently **regularized** — there is no assumption-free, tuning-free density estimate. What we ship is the degenerate corner: a **nonparametric mode with a fixed (non-adaptive) bandwidth (100 bins) and an arbitrary tie-break** — neither parametric nor consistently nonparametric, so it is both **biased *and* non-convergent**. A fixed bin count *cannot* converge to the true mode no matter how many samples are added (consistency needs the bandwidth to shrink with `n` at a controlled rate). A principled MAP therefore requires **one of**: (a) an explicit distributional assumption (fit a family → analytic mode; stable at low `n`, at the cost of model risk), or (b) an **`n`-adaptive smoothing rule *plus* a sufficient-`n` floor** (a sample-count floor alone is necessary, not sufficient). The tie-break is merely **where the under-determination surfaces**; "fix the tie-break" reduces the directional bias but does not make the estimator converge — a band-aid, not a cure.

Note the estimator is **already semi-parametric**: the `zero_mass_threshold` rule (≥30% mass at ~0 ⇒ MAP = 0) is a zero-inflation model. The under-determined part is specifically the **continuous-body mode**, which is why the bias bites hardest on the *partially* zero-inflated active cells (`mass0 ≈ 0.06`).

**Latent today** (the leaf publishes nothing — hence Tier 2, not 1), but it is **silent, directional output incorrectness for any consumer that adopts it expecting parity**. Resolution path: estimator-design effort tracked in **#89** (a distributional assumption *or* `n`-adaptive smoothing + floor; **not** merely a better tie-break; SemVer decision required). See C-24 (resolved), C-25, C-33.

**Mitigation shipped (2026-06-23, ADR-019; redesigned 2026-06-24, C-44) — not a full resolution; stays open.** `tower_point` ships as an **unbinned, median-based** point estimator (the median of the configurable **`tip_mass`** floor, default 0.5 — the shorth), so it carries **none** of the lowest-index histogram tie-break's directional bias, and — reading a *mass-aware* floor rather than the degenerate 2-sample 5% floor — it is now also **robust to minority duplicated draws** (C-44). Scored against a *non-circular analytic-mode* oracle (the active families only — zero-mode families have no analytic continuous mode), it ties/beats `map_estimate` on clean active cells **at the production sample size n=1024**; at **n=128 the two are mixed** (the tip wins on some families, loses on others — see `research/map_hdi/point_pass.py`), so this is a mitigation at production `n`, not a guaranteed win at the low-`n` regime where the bias bites hardest. `bimodality` flags the multimodal cells where any single mode is ill-defined (with its own recall caveat — see C-34). **Residual:** `map_estimate` itself is unchanged (frozen, ADR-018) — a naïve adopter can still step on it (now with a documented better path, `tower_point`); and `tower_point` uses a **fixed** `tip_mass` floor (0.25 — the top-quartile floor since ADR-019 Amendment 3, 2026-07-24; originally the 0.5 shorth), so it is **not** the consistency-guaranteed convergent mode this entry calls for. That remains **#89**.

---

### C-34: `bimodality` is conservative by design — limited recall on ambiguous / unequal multimodal posteriors

| Field | Value |
|-------|-------|
| ID | C-34 |
| Tier | 3 |
| Status | **awaiting** — a genuinely multimodal model regime (#89) |
| Source | merge-gate review (2026-06-23) |
| Trigger | When a model change begins producing genuinely multimodal posteriors, watch whether the `bimodality` flag rate rises on those cells. If it stays ~0 while separated modes appear — especially an unequal-weight split, or one mode tall-and-narrow beside a spread mode — the detector is under-flagging and a consumer trusting the single `tower_point` / a single interval will be misled. |
| Location | `src/views_frames_summarize/bimodality.py` (the coarse-histogram + smoothing + prominence + `min_mass` heuristic). Thresholds (`bimodality_bins`/`prominence`/`min_mass`/`smooth`) now live in `config.TOWER_CONFIG` (C-44 redesign) — still battery-tuned; the trigger is unchanged. |

`bimodality` is deliberately tuned for **zero false positives** on the normal regime (right-skewed, zero-inflated, and active unimodal posteriors all read unimodal), at the cost of **recall** on harder cases. Empirically it fires on clearly-separated comparable-mass modes (and a zero-atom + distinct bump when the atom is substantial), but **misses**: (a) a minority mode below `min_mass=0.15` (e.g. an 85/15 split); (b) a mode that is tall-and-narrow beside a spread mode — the spread mode cannot clear the prominence bar the tall peak sets (e.g. a ~17% zero atom under a tight positive bump); (c) overlapping modes with no genuine sub-prominence valley. It is a **heuristic flag for a clear regime change, not a formal multimodality test** (ADR-019 states this; the edge-bin smoothing fix improved the atom case but did not remove the gap). Latent today (Tier 3) — current models are effectively unimodal — but it is a **silent single-point-trust risk** under a future multimodal regime, the same family as **C-32** (biased mode) and **C-33** (no tower coherence, resolved). Resolution path if multimodality becomes real: a stronger detector (a dip test, or a mass-based criterion that does not penalize spread modes); tracked alongside **#89**. See C-32, C-33 (resolved), ADR-019.

---

### C-43: per-row binning duplicated between `bimodality` and the frozen `map_estimate`

| Field | Value |
|-------|-------|
| ID | C-43 |
| Tier | 4 |
| Status | **awaiting** — #89 or a MAJOR; `point.py` is frozen and ulp-sensitive (C-24) |
| Source | tech-debt-cleanup (2026-06-24) |
| Trigger | When `map_estimate` is unfrozen or reworked (#89), or the bimodality binning needs to change — at that point extract a shared row-blocked binning helper. It is **not** safely de-dupable now: `point._batched_map` is frozen (ADR-018) and its bin edges are ~1-ulp-sensitive across numpy versions (the C-24 portability saga), so touching it risks a behaviour change to `map_estimate`. |
| Location | `src/views_frames_summarize/bimodality.py` (`_coarse_counts`); `src/views_frames_summarize/point.py` (`_batched_map`). |

Both functions implement per-row histogram binning over a row-block. `_coarse_counts` (v1.1.0) is a deliberately simplified clipped-linear bucket for a heuristic flag; `_batched_map` (frozen v1.0.0) reproduces `numpy.histogram`'s edge-exact path bit-for-bit for the MAP. The two are **independently correct and tested** — the "debt" is the maintenance cost of two binning implementations to keep mentally aligned. **Tier 4** — no correctness or reliability impact; bounded because `point.py` is frozen and won't drift. Intentionally **not** unified now (extracting a shared helper would touch frozen, C-24-ulp-sensitive code — a stability risk the tech-debt protocol says to defer). See C-24 (resolved — the binning portability constraint), ADR-018 (the freeze that blocks the fix), #89.

---

### C-46: the leaf's frame-envelope invariants are re-asserted in `views-evaluation`'s `MetricFrame` — no single authority, can drift

| Field | Value |
|-------|-------|
| ID | C-46 |
| Tier | 2 |
| Status | **awaiting** — views-evaluation's `MetricFrame` (cross-repo; not resolvable here) |
| Source | expert-code-review (2026-06-24, GH #109; Kleppmann/Feathers/Nygard lenses) |
| Trigger | When `views-evaluation` implements `MetricFrame` on the views-frames substrate (Option B, ADR-020), or when the leaf changes its serialisation/round-trip or float32 discipline (`io/`, `_validation.py`) — at that point the envelope invariants (float32 values, round-trip identity, optional-only metadata) exist in two places with no shared check. Re-run a cross-boundary round-trip contract test that calls the leaf's published conformance checker. |
| Location | Leaf side: `src/views_frames/conformance/__init__.py` (`assert_frame_envelope` / `assert_frame_contract`), `src/views_frames/io/`, `src/views_frames/metadata.py`. Boundary: the (to-be) `MetricFrame` in `views-evaluation`. |
| Cross-refs | C-01 (resolved — the home decision: leaf defines only the index/key protocol the eval types conform to), ADR-016 (conformance floor), ADR-020 (the B ratification), GH #109, views-evaluation#21. |

Under Option B (the ratified boundary; C-01), `MetricFrame` lives in `views-evaluation` and reuses the views-frames *substrate* — `FrameMetadata` plus the conformance/IO **patterns**. The float32 discipline and the serialise→load round-trip are therefore guaranteed in the leaf (`assert_frame_contract`) but only **re-asserted by convention** in `views-evaluation`. There is no single schema authority for the shared "frame-like envelope" across the two repos, so the two can drift — a quiet deserialisation or precision mismatch discovered late at the emit→consume boundary, not an outage. **Tier 2** — structural fragility with a clear future trigger; the leaf publishes nothing itself, but the boundary it underwrites can silently mismatch. **Mitigation (recorded in ADR-020):** publish the leaf's conformance/round-trip checks as a reusable, consumer-runnable checker (the conformance suite is already a public artifact, ADR-016) plus an explicit, versioned wire schema (a `schema_version` marker) that both emit and consume validate against — converting "agree by convention" into "validate against one written contract." **Partially mitigated (v1.4.0):** the reusable checker shipped as `assert_frame_envelope` — the shared envelope (float32, trailing axis, round-trip) factored out as one written authority a non-spatiotemporal `MetricFrame` validates against. **Remaining (stays Open):** the explicit versioned wire schema (`schema_version`) and the cross-repo emit→consume round-trip contract test that calls the checker — both live at the boundary / in `views-evaluation`. Resolved when those land.

---

### C-57: `map_estimate` raises an obscure `IndexError` (not a clean error) on ±inf draws

| Field | Value |
|-------|-------|
| ID | C-57 |
| Tier | 3 |
| Status | **awaiting** — a cross-estimator non-finite hardening pass (additive MINOR) |
| Source | falsify audit (2026-06-25, P5b — discovered while widening the exceedance/ES guards) |
| Trigger | When a consumer feeds a frame containing an `inf` draw (a valid float32 the leaf does **not** ban — e.g. an upstream model bug) to the frozen `map_estimate`: the histogram span is `inf`, the bin index divides to `nan`, and the `astype(intp)` cast overflows to the int-min sentinel, so `np.take_along_axis` raises `IndexError: index -9223372036854775808 is out of bounds` instead of a clean `ValueError` or a finite result. |
| Location | `src/views_frames_summarize/point.py::_batched_map` (the `astype(np.intp)` cast feeding `np.take_along_axis`) (`_batched_map`). |
| Cross-refs | ADR-018 (frozen v1 surface — behavior is locked), C-50/C-56 (the new estimators now fail loud cleanly on non-finite via `np.isfinite`; `map_estimate` is the frozen sibling that does **not**), ADR-008 (fail-loud posture). |

The frozen surface is **inconsistent** on non-finite draws: `collapse(np.mean)` propagates `inf` (visible), the new `exceedance`/`expected_shortfall` now **fail loud** on it (C-50/C-56), but `map_estimate` **crashes with an obscure `IndexError`** rather than a clean, actionable error. This is **not** silent corruption (it is loud, and `inf` draws are out-of-contract upstream bugs), so it is **not** a publish blocker for v1.6.0 — and `map_estimate`'s behavior is **locked by the ADR-018 freeze**, so it cannot change without an additive hardening pass. **Tier 3** — ungraceful failure on a leaf-permitted input; a future cross-estimator non-finite hardening (a reserved additive MINOR) should give `map_estimate` the same clean `np.isfinite` guard. **Open** — watch-item, no fix shipped in v1.6.0.

---

### C-62: `reconcile_proportional` is an information-losing per-draw approximation (no joint-calibration guarantee)

| Field | Value |
|-------|-------|
| ID | C-62 |
| Tier | 3 |
| Status | **awaiting** — ADR-024's two deferral preconditions (a joint-tail need, or shared draw identity upstream) |
| Source | expert-method-review lineage + S3 design (#145), 2026-06-27 |
| Trigger | When a consumer's decision provably needs **calibrated joint** country tails that proportional's per-draw marginal rescale cannot provide, **or** when the country model (views-models) gains a shared draw-identity / coupling that makes principled joint reconciliation buildable — i.e. when ADR-024's two deferral preconditions are met, build the principled sibling module (never by modifying `proportional`). |
| Location | `src/views_frames_reconcile/proportional.py` (the per-draw method); designed in `docs/ADRs/024_principled_joint_reconciliation_design.md`. |
| Cross-refs | ADR-024 (the design + deferral), ADR-023 (sibling charter; future-sibling-module open question), views-postprocessing C-37 (the cross-repo principled-reconciliation lineage), views-pipeline-core C-198 / C-200b (consumer-side), C-60 (the notebook presentation of this — resolved), D-12 (mode reporting). GH #145 / #142. |

`reconcile_proportional` rescales grid cells to sum, **per draw**, to the country total — pairing grid-draw `s` with country-draw `s`. When the grid and country models are trained **independently** (the current platform reality), draw index `s` has **no shared identity** across them, so the pairing is arbitrary and the reconciled **joint** distribution (the joint country tails an FAO-style worst-case keys on) is not guaranteed calibrated — even though conservation (sum-to-country per draw, zeros preserved, non-negative) holds **exactly**. This is **not silent** (hence **Tier 3**, not Tier 1): it is documented at every layer — the `proportional.py` docstring, ADR-024, the `03_reconciliation.ipynb` bit-identity-≠-method-quality panel (C-60), and surfaced at runtime as the `reconcile_result` mode `aligned-draws` (D-12). It is a **known method-quality limitation with a designed upgrade path** (ADR-024), deliberately deferred until its preconditions hold. **Open** — the limitation persists until the principled sibling module is built.

---

### C-66: value-buffer write-protection is deferred to the next MAJOR (the C-63 enforce-rider)

| Field | Value |
|-------|-------|
| ID | C-66 |
| Tier | 3 |
| Status | **awaiting** — the next MAJOR (the one-line enforce + red test are pre-written) |
| Source | review-diff + register-risk (2026-06-28, epic #179 / S2) — the residual of the C-63 resolution-by-decision (ADR-025). |
| Trigger | When a MAJOR bump is opened for **any** reason — add `self._values.setflags(write=False)` after the `self._values = ...` assignment in the three frame constructors (`prediction_frame.py::PredictionFrame.__init__`, `target_frame.py::TargetFrame.__init__`, `feature_frame.py::FeatureFrame.__init__`) **and** a red test (`frame.values.flags.writeable is False`; mirror `tests/test_properties.py::test_with_metadata_shares_the_values_buffer`), riding that MAJOR for free. **Or** sooner, if a consumer is found applying an in-place `.values` mutation (`frame.values[mask] = 0`, `*=`, a clamp) on a `with_metadata`/`select` buffer-sharing frame — promote/expedite the enforce then. |
| Location | the `self._values = values` assignment in each of `src/views_frames/prediction_frame.py::PredictionFrame.__init__`, `target_frame.py::TargetFrame.__init__` and `feature_frame.py::FeatureFrame.__init__` (bare assignment, no `setflags`); `src/views_frames/_validation.py::coerce_values` (`coerce_values` returns float32 without copy); contrast `src/views_frames/index.py::SpatioTemporalIndex.__init__` (the two `setflags(write=False)` calls) (the index **is** write-protected). Decision in `docs/ADRs/025_value_buffer_immutability_by_convention.md`. |
| Cross-refs | **C-63** (RESOLVED by contract correction — this entry tracks the *deferred enforce* it left open), **ADR-025** (the decision + the exact one-line-per-constructor change), ADR-018 (`values` is frozen-surface, so the enforce is a MAJOR), GOVERNANCE.md (SemVer: "tightening an invariant" = MAJOR), C-07 (the zero-copy reason the buffer is left writeable). |

C-63 was resolved by **correcting the contract** (ADR-025): the value buffer is documented as immutable *by convention* and the docs no longer claim an unenforced guarantee. But the **code** is unchanged — `frame.values.flags.writeable` is still `True`, and `with_metadata` shares the buffer — so the underlying mechanism (an in-place `.values` mutation **silently corrupts every frame sharing the buffer**, the Tier-2 basis of C-63) is **mitigated, not removed**. The mitigation is documentation (three frame CICs §9 + README design principle 3 say it is unsupported) + the empirical fact that **nothing in `src/` or `tests/` mutates `.values`**. The actual write-protection (`setflags(write=False)`) is deliberately deferred because, on the frozen-surface `values`, it is a **MAJOR** (GOVERNANCE/ADR-018) and does not justify a standalone cross-repo coordinated bump. **Tier 3** — this entry tracks the *accepted deferral* of a documented-and-unexercised exposure (the acute silent-corruption path requires a consumer to ignore the published contract); it is a governance/safety-tracking item, not a current defect, and exists so the deferred enforce stays visible in the **Open** section rather than buried in a resolved entry. **Open** — until the enforce rides the next MAJOR.

---

### C-71: dense-grid fill allocates the full dense buffer — grid-scale memory footgun

| Field | Value |
|-------|-------|
| ID | C-71 |
| Tier | 3 |
| Status | **awaiting** — a receipted need for bounded-memory densification |
| Source | expert-code-review (2026-07-27, the #203 design review), Nygard lens; shipped with ADR-026 (v1.10.0). |
| Trigger | When a consumer densifies at grid scale — a full-pgm `cartesian` target (~259k cells × months ≈ tens of millions of rows) fed to `reindex_fill` on a sampled frame — check the buffer arithmetic first: the dense values buffer is `target.n_rows × (trailing axes) × 4` bytes (at S=1000, hundreds of GB). Same check applies to `cartesian` itself (eager `T × U` identifier allocation). |
| Location | `src/views_frames/index.py` (`cartesian`); `src/views_frames/{prediction_frame,feature_frame,target_frame}.py` (`reindex_fill` — `np.full` of the full dense shape). |
| Cross-refs | **ADR-026** (the decision: the leaf documents the cost, never guesses a size guard — that would be policy), C-21 (the uniqueness stance `reindex_fill` inherits and `cartesian`'s duplicate-input `ValueError` protects), C-22/C-25 (the memory-bounded precedent on the *estimator* side — deliberately not applied here: densification's output *is* the allocation). |

The fill primitive makes densification a one-liner, which is the point (#203, faoapi #242) — and also the hazard: the allocation that faoapi's pandas implementation made visible (an explicit `MultiIndex.from_product` + concat) is now behind one method call. The cost is **inherent to densifying** (the output *is* the dense buffer), not an implementation choice, so the leaf's controls are documentation (both docstrings state the cost) and this entry. The failure is **loud** (`MemoryError`/OOM-kill), not silent — hence Tier 3, an operational-awareness item, not a correctness risk. If a consumer legitimately needs bounded-memory densification (block-wise fill-and-stream), that is a future additive design, receipted first.

---

### C-73: `io.arrow.load` is read-all-to-RAM — no mmap or partitioned path on the wire format

| Field | Value |
|-------|-------|
| ID | C-73 |
| Tier | 3 |
| Status | **awaiting** — a memory-wall receipt (an OOM *despite* per-month sharding) |
| Source | GH #199 item 2 (ADR-013 §8, views-postprocessing); split out when item 1 shipped as C-72 (2026-07-31) — the residual was recorded only inside the *resolved* C-72 and needed to stay visible in Open. |
| Trigger | When a consumer loads a **full-S global-reference shard in one call** — i.e. drops or widens the per-month sharding on the FAO/postprocessing ingestion path (views-faoapi #100), or loads several shards concurrently in one process. At that point do the arithmetic before running: `N_rows × S × 4` bytes for the flat table **plus** the same again for the reshaped values (`pq.read_table` materializes the whole table, then `.to_numpy()`/`reshape`/`np.stack` copy it). #199 measures ~1.6 GB transient per full-S month shard at global reference. |
| Location | `src/views_frames/io/arrow.py::load` (the `pq.read_table` call) (`pq.read_table` — whole-table materialization), `the per-column `.to_numpy().reshape()` / `np.stack` block in the same function` (per-column `.to_numpy().reshape()` + `np.stack` — the second full copy). The npz path already has `mmap=True`; arrow has no equivalent. |
| Cross-refs | **C-72** (the same function's *correctness* half — resolved v1.10.1; this is the explicitly-deferred remainder of the same issue), C-71 (the sibling grid-scale allocation footgun), C-25/C-22 (the memory-bounded precedent on the estimator side), GH #199 item 2, views-postprocessing ADR-013 §4.5(b)/§8, views-faoapi #100. |

`arrow` is the platform's **interchange** codec — the format the FAO/postprocessing path actually ships forecasts in — and `load` reads the entire parquet into RAM, then copies it again to reshape. ADR-013 §8 states the mitigation as **per-month sharding** (a consumer-side contract obligation) and names mmap/partitioned reading as the long-term fix while explicitly declaring it **NOT a contract dependency** — so this is deliberately open, not neglected: shipping FAO data does not wait on it. **Tier 3** — the failure mode is a loud `MemoryError`/OOM-kill under a footprint the consumer controls, never a wrong number; the cost is operational, and the mitigation already exists. Deliberately **not designed yet**: the leaf does not guess a streaming API for a wall nobody has hit. The receipt that would change this — a consumer OOM *despite* sharding, or a shard size that cannot be reduced further — is the thing to wait for; a design without it risks a speculative, frozen surface (ADR-018, C-52).

---

### C-74: the CI gate is a strict subset of the local gate — `validate_docs.sh` and `ruff format` run only by habit

| Field | Value |
|-------|-------|
| ID | C-74 |
| Tier | 3 |
| Status | **actionable** — two `- run:` lines in `ci.yml` + one `ruff format .` pass |
| Source | pre-release repo sweep (2026-07-31), prompted by the ship-readiness review; found while checking what the C-70 "recurrence guard" actually enforces. |
| Trigger | **At the next MINOR/MAJOR version bump** — the case where the README banner must move — do not rely on CI to catch a stale banner; run `bash docs/validate_docs.sh` locally before tagging, or wire it into `ci.yml` first. Same at the next multi-file contribution: without a `ruff format --check` job, the first contributor whose formatter runs produces a reformat-the-world diff. |
| Location | `.github/workflows/ci.yml:20-22` (gates `ruff check`, `mypy src/`, `pytest --cov-fail-under=100` — **and nothing else**); `docs/validate_docs.sh` (referenced **nowhere** under `.github/`); `ruff format` (never invoked in CI; **22 of 77 files** currently drifted). |
| Cross-refs | **C-70** (its resolution claimed this guard was live — corrected there), C-51 / C-58 (the same "the check exists but is not exercised" family), C-75 (the sibling finding: tests inside the gate that don't test the code), the cross-cutting **verification-completeness** cluster. |

Two checks the project treats as gates are not gates. **(1)** `validate_docs.sh` — including the README-banner-vs-`pyproject` check added *specifically* as C-70's recurrence guard — is not referenced anywhere in `.github/`; it runs only when a maintainer types it. C-70's resolution asserts the opposite ("the narrative epoch-lag pattern **fails validation** instead of accumulating"), so the register itself carried an overstated enforcement claim until this entry (C-70 corrected 2026-07-31). The guard is one `- run:` line from being real. **(2)** `ruff format` is never run in CI, and 22 of 77 files are already drifted from it — harmless today because one person formats deliberately, a noisy-diff generator the moment a second contributor's editor does it automatically.

**Tier 3** — no correctness or silent-corruption path: the failure mode is documentation drift and diff noise, both loud and cheap once noticed, and the underlying checks all exist and pass right now. It is Tier 3 rather than Tier 4 because the drift pattern is **empirically proven to recur here** — C-70 documented an entire epoch of accumulated narrative lag, and the guard written to stop it was never armed. Resolved when both checks run in `ci.yml`.

**Half done (2026-07-31, Epic #208 / S3 #211).** `ci.yml` now has a `docs` job that runs `bash docs/validate_docs.sh` on every push and pull request to `main` and `development` — so the version-banner check is finally a gate, in time for this epic's own version bump. It is a **separate job rather than a step in the four-version matrix**: the script is bash and grep with no Python involvement, so running it inside the matrix would repeat it four times and couple documentation policy to the list of supported Python versions. **Still open for the formatting half** — `ruff format --check` cannot be turned on until the 22 drifted files are fixed, or it fails every pull request. That is S10 (#218), deliberately sequenced after the release. This entry closes there.

---

### C-75: four design-phase falsification tests assert README *prose*, inside the 100%-coverage gate

| Field | Value |
|-------|-------|
| ID | C-75 |
| Tier | 3 |
| Status | **actionable** — rewrite four assertions against the API, or retire the probes as design-phase fossils |
| Source | pre-release repo sweep (2026-07-31) — stale `TODO` markers whose stated precondition has been satisfied since v0.1.0. |
| Trigger | **When the README is reworded** (a §11/§13a edit, a banner/chronicle refresh, a design-bible rewrite) these tests go **red for the wrong reason** — the contract is intact, the prose moved. Conversely, when `cross_level_align` / the index API is next changed, they stay **green regardless**. At either moment, replace the regex with an assertion against the actual API (the ADR-014 decision they were waiting on is documented, and `cross_level_align` has existed since v0.1.0). |
| Location | `tests/test_falsification_domain_free_crosslevel.py` — the four `TODO`s in `test_falsify_cl_01_crosslevel_mapping_home_is_decided`, `..._cl_02_crosslevel_not_expressible_in_declared_numpy_ops`, `..._cl_03_no_internal_contradiction_on_alignment_ownership` and `..._cl_04_stability_contract_survives_the_mapping` (four `# TODO: replace with a real check once the decision is documented` / `once the actual index API exists`). The prose-regex pattern spans four files — `test_falsification_{domain_free_crosslevel,twin_parity,spatiallevel_and_metricframe,immutability_copy}.py` (16 / 19 / 13 / 7 README references respectively). |
| Cross-refs | **C-51** (the direct precedent: paths that *looked* covered were only transitively asserted — coverage-green ≠ verified), C-58 (verification-realism), C-74 (the sibling gate-completeness finding), ADR-014 (the decision these TODOs were blocked on), ADR-005 (red/beige/green taxonomy). |

These began as legitimate **design-phase** falsification probes: before the code existed, asserting that the README *decided* where the cm↔pgm mapping lives was the only check available. The design phase ended — ADR-014 ratified the injected-mapping protocol and `cross_level_align` shipped in v0.1.0 — but the probes were never upgraded, and their own `TODO`s say so. The result is inverted tests sitting inside the project's strongest gate: they are counted by `--cov-fail-under=100`, they pass, and they are coupled to the wording of a document rather than the behavior of the code. **Tier 3** — no correctness risk (the real contract *is* pinned elsewhere, by the conformance suite and the frame/index test modules), but it is maintainability debt with a false-confidence edge: a reader auditing coverage sees the cross-level contract "tested" when what is tested is a sentence. Resolved when the four TODOs assert against the API, or when the probes are retired as design-phase fossils with that decision recorded.

---

## Disagreements

### D-01: `SpatioTemporalIndex` domain-purity fork (where does cross-level alignment live?)

| Field | Value |
|-------|-------|
| ID | D-01 |
| Source | falsification-audit (2026-06-20) |
| Perspectives | Consumers (reporting/pipeline-core: "the index should do the cm↔pgm join"), Leaf-purity (critique_02: "the mapping is time-varying viewser-sourced domain data — it cannot live in a numpy-only stable leaf") |
| Resolution | **Resolved** — leaf owns the `cross_level_align(index, mapping)` protocol; the consumer injects the mapping (ADR-014, README §13a.4). See C-14. |

---

### D-02: C-48 run-identity is a cross-repo decision the leaf only homes

| Field | Value |
|-------|-------|
| ID | D-02 |
| Source | expert-review (2026-06-20) |
| Perspectives | Reporting ("a stamped run/eval identity in frame metadata is the cure for C-48"), Leaf ("frames give provenance a *home*; selecting *the* run and where it is stored is a cross-repo decision frames do not auto-resolve") |
| Resolution | Partially resolved — ADR-013 gives provenance a typed home; the run-selection/storage decision remains cross-repo (tracked for views-evaluation/reporting). See C-08. |

---

### D-03: twin-unification model — A vs B vs C

| Field | Value |
|-------|-------|
| ID | D-03 |
| Source | expert-review (2026-06-20) |
| Perspectives | Option A (shared `_BaseFrame` — max sharing, but god-class/C-36 risk), Option B (composition + typed header — README intent, discipline-dependent), Option C (separate siblings, shared index only — lowest churn, ~80% value) |
| Resolution | **Resolved** — Option C, ratified by datafactory owner 2026-06-21; A rejected in writing (ADR-011, README §13a.1). See C-03, C-16. |

---

### D-04: the consumer perspectives are simulated, not elicited

| Field | Value |
|-------|-------|
| ID | D-04 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §5 ("uniform structure/idioms suggest one author wrote all three — they are the proposer's hypotheses, not stakeholder buy-in"), Author ("they pressure-test the design from multiple angles") |
| Resolution | **Resolved-by-events (2026-06-27).** The simulated perspectives were acted on and then *ratified by real adoption*: the Epic 11 reconciliation cutover shipped through pipeline-core (#233) and views-models (#191/#202), with adoption work progressing in datafactory/reporting/faoapi — demonstrated buy-in, not assumed. The original caveat (five filed issue-sets — datafactory #219–221, pipeline-core #186–190, reporting #137–140, postprocessing #27–29, faoapi #87–91 — "unconfirmed until the team responds"; only `from_views-datafactory` ratified at filing) is now overtaken. See D-05, C-13. |

---

### D-05: missing views-evaluation and model-repo perspectives

| Field | Value |
|-------|-------|
| ID | D-05 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §5b ("views-evaluation owns `EvaluationFrame`/would produce `MetricFrame`; a model repo produces `PredictionFrame` — both absent, and they would stress the riskiest claims"), Scope ("write them before promoting `MetricFrame` from exploratory") |
| Resolution | **Resolved-by-events (2026-06-27).** The substance — the views-evaluation boundary — was settled by **ADR-020** (`MetricFrame` lives in views-evaluation on the views-frames substrate; only generic provenance on the leaf header; C-47 resolved), decided with views-evaluation Informed/Consulted. The formal "write the perspectives before `MetricFrame`" step was overtaken by that ADR decision. See C-01, C-47, ADR-020. |

---

### D-06: portfolio / WIP sequencing across three concurrent cross-repo initiatives

| Field | Value |
|-------|-------|
| ID | D-06 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §6 ("viewser→datafactory migration, views-appwrite extraction, and views-frames relocation compete for the same coordination budget and destroy change attribution if run concurrently"), Leverage ("views-frames is highest-leverage but also the largest coordination load") |
| Resolution | **Resolved-by-events (2026-06-27).** The sequencing played out as advised: views-frames relocation ran as the highest-leverage track through Epics 2–11 without being run concurrently with the views-appwrite extraction in the same repo, and consumer adoption queued behind the data-migration baseline. The concurrent-WIP / change-attribution concern is now historical. See C-13. |

---

### D-07: `exceedance` NaN policy — fail-loud vs explicit `nan_policy` vs silent-skip

| Field | Value |
|-------|-------|
| ID | D-07 |
| Source | expert-code-review (2026-06-24, exceedance-probability design) |
| Perspectives | Nygard / ADR-008 ("fail loud on any NaN — silently counting NaN as non-exceeding deflates the onset metric; an undetected wrong number is worse than an exception"); Beck / ergonomics ("consumers already strip NaN upstream, so a fail-loud default with no param is the smallest viable v1; a `nan_policy` is YAGNI"); middle ("an explicit `nan_policy='raise'|'skip'` — skip-and-renormalise the denominator — serves both, at the cost of an all-NaN-row 0/0 edge"). |
| Resolution | **Settled by ADR-021** — fail-loud NaN (raise `ValueError` on any NaN in a reduced row, ADR-008); a `nan_policy='skip'` is a reserved, reversible additive MINOR. See C-50. |

---

### D-08: `exceedance` threshold direction — strict `>` vs an `inclusive` (`>=`) option

| Field | Value |
|-------|-------|
| ID | D-08 |
| Source | expert-code-review (2026-06-24, exceedance-probability design) |
| Perspectives | Beck / onset ("strict `>` only — `P(Y>0)` = 'any violence' requires it, and it matches the survival-function convention `1 − F(c) = P(X>c)` from the Book of Statistical Proofs / catastrophe-modeling EP curve"); Martin / Kleppmann ("integer-count consumers expecting `P(Y ≥ 25)` will pass `25` and silently receive `P(Y > 25)` — an off-by-one for counts; offer an `inclusive` flag or document the `≥k ⇒ pass k−1` workaround"). |
| Resolution | **Settled by ADR-021** — strict `>` (the survival-function standard; makes onset well-defined), with the integer-count `≥k ⇒ pass k−1` note; an `inclusive`/`≥` flag deferred as a reversible MINOR. See C-50 (same reducer). |

---

### D-09: construction-factory shape — free function vs classmethod

| Field | Value |
|-------|-------|
| ID | D-09 |
| Source | expert-code-review (2026-06-24, GH #113) + pipeline-core owner exchange |
| Perspectives | **#113-as-filed / pipeline-core:** add a `build_prediction_frame(...)` **free function** to the leaf. **views-frames owner + all eight expert lenses:** a `@classmethod PredictionFrame.from_arrays(y_pred, *, time, unit, level, metadata=None)` — it matches the leaf's only construction-helper convention (`from_2d` / `load`), single-homes construction (SRP/CCP), is the smaller frozen surface (Ousterhout), resists accretion (Nygard), and is the canonical Python Factory Method (GoF); a free-function alias is **strictly dominated** because every consumer already imports `PredictionFrame`. |
| Resolution | **Settled — Option B:** classmethod `PredictionFrame.from_arrays`, **singular** (PredictionFrame only; defer Feature/Target per CRP + ADR-011 honesty-over-symmetry), **zero own logic**, keyword-only `time`/`unit`/`level`, in `prediction_frame.py`, **no alias**. Additive/MINOR; `CONFORMANCE_FLOOR` stays `1.0.0`. **Implementation deprioritized behind the engine migration** (views-hydranet #137 / views-baseline #21) — it was not a blocker. **Outcome (2026-07-31, ADR-027):** never implemented, and now **declined** — the engines migrated by constructing `SpatioTemporalIndex` directly, so the settled shape was never needed. D-09's design is **not discarded**: ADR-027 carries it forward verbatim as the form any future construction convenience must take, together with what would reopen the question. This disagreement is therefore settled *twice* — on shape (here) and on whether to build at all (ADR-027). See C-52/C-53/C-54 (resolved), ADR-011, ADR-018, **ADR-027**, GH #113. |

---

### D-10: worst-case scenario statistic — `max` vs high-quantile vs expected-shortfall

| Field | Value |
|-------|-------|
| ID | D-10 |
| Source | design discussion (2026-06-25, views-frames owner + maintainer) |
| Perspectives | **min/max** (intuitive "best/worst", but `max` is a single extreme order statistic — the **highest sampling variance** of any summary, not reproducible across re-samples, worst for the heavy-tailed multi-source-uncertainty posteriors here: MC-dropout × distributional head × ensemble all feed one sample axis); **high quantile (e.g. 99.5th) via the existing `quantiles`** (robust, zero new code — but the level is arbitrary and a point quantile is **not** a coherent risk measure); **expected shortfall / tail mean (CVaR)** (the mean of the worst `t` fraction — most stable under re-sampling, a **coherent/subadditive** risk measure, and the conditional-expectation companion to `exceedance` / the catastrophe-modeling OEP-AEP framing). |
| Resolution | **Settled — `expected_shortfall` is the worst-case** (principled), with the high-quantile path documented as the lighter alternative; **`max` is never offered.** **Best-case ships no function** — a low quantile (via `quantiles`) plus `exceedance(frame, [0])` cover it (CRP — don't force a best-case symbol no one reuses). See C-55, C-56, ADR-022. |

---

### D-11: frame serialization-convenience placement — `to_parquet`/`to_pddf` on the leaf vs off it

| Field | Value |
|-------|-------|
| ID | D-11 |
| Source | expert-code-review (2026-06-26) — the DataFrame→views-frames transition question (consumer sites that load/distribute parquet) |
| Perspectives | **Add frame-level conveniences to the leaf** (`frame.to_parquet`/`from_parquet` via pyarrow, and/or `frame.to_pddf`/`from_pddf` via pandas) — migration ergonomics at the many parquet load/distribute sites; conceived as **transitional**, possibly removed once the migration completes. **Keep them off the frozen leaf** (all eight lenses + the constitution): the leaf is **frozen** (ADR-018 — additions are permanent, removal = platform-wide MAJOR), so "transitional/removable" + "frozen leaf" is **self-contradictory** (Beck/reversibility); **pandas is ratified out** (ADR-001 line 120 non-entities, README §11, import-DAG `FORBIDDEN`) and a `to_pddf` emitting the object-dtype **list-in-cell** encoding would re-arm the ~33× #181 OOM the frame exists to kill (README §7); serialization formats change for **different reasons** than the data contract (CCP) and concrete format/pandas sugar on the most-stable-most-abstract leaf breaks **SAP/SDP**; it is the C-52 camel's nose (`to_parquet` → `to_pddf` → `from_grid` → store knowledge). |
| Resolution | **Settled — keep them off the frozen leaf.** (1) **pandas (`to_pddf`/`from_pddf`): never on the leaf** — place in a **consumer adapter** (pipeline-core, beside `PredictionFrameConverter`), or, only if ≥2 repos need the identical adapter (REP/CRP), an explicitly-transitional **unfrozen sibling** (e.g. `views_frames_compat`, pandas an optional extra) so it stays removable post-transition (the ADR-017/ADR-023 sibling precedent). (2) **parquet:** the codec already exists (`io.arrow`) — **reject new frozen frame symbols** (`to_parquet`/`from_parquet`); if frame-level ergonomics are wanted, do **Option B'** — make the existing `Frame.save/load` **format-selectable** (`save(path, format="parquet"\|"npz")`, pyarrow imported lazily; additive, floor stays 1.0.0), and only **if/when a consumer actually reaches for it** (no demand yet → **defer**). (3) **Governing rule:** anything that might be removed post-transition must **not** touch the frozen leaf surface. **No work required in views-frames now**; B' is the only candidate leaf change and it is deferred. |

Cross-refs: ADR-018 (freeze — additive-only, removal = MAJOR), ADR-001 (adapters/pandas = consumer edges; accretion = the leaf's #1 failure mode), ADR-017 + ADR-023 (unfrozen sibling-package precedent), README §7 (the #181 list-in-cell foot-gun) / §11 (scope — pandas/parquet-store → consumer repos), `tests/test_import_enforcement.py` (`FORBIDDEN` pandas), C-52 (the accretion this extends).

---

### D-12: reconciliation-mode provenance placement — stamp the leaf frame vs report it from the sibling

| Field | Value |
|-------|-------|
| ID | D-12 |
| Source | implementation + review-diff (2026-06-27) — S2 of the reconciliation right-home epic (#144) |
| Perspectives | **Stamp the mode on the frame** (#144 as originally written): write the reconciliation mode (`point-broadcast` / `aligned-draws`) into the reconciled frame's `FrameMetadata`, so an auditor reads it off the frame in isolation (a "self-describing" frame). **Keep reconciliation vocabulary off the leaf**: the leaf's `FrameMetadata` is governed **generic-only** (ADR-020 / register C-47) — it carries provenance meaningful for *any* frame (`run_id`, `data_version`) and deliberately excludes domain/operation-specific fields (the precedent: eval's `scoring_code_version` lives in views-evaluation's `MetricFrame`, never the leaf). Stamping `reconciliation_mode` would push sibling-only vocabulary into the numpy leaf that must not know reconciliation exists (ADR-001 accretion guard), and `FrameMetadata` lives in `views_frames` while reconciliation lives in the sibling — a layering inversion. |
| Resolution | **Settled — report the mode from the sibling; do not stamp the leaf.** `ReconciliationModule.reconcile_result(cm, pgm)` returns a `ReconciliationResult` (`frame`, `mode`, `method`) carrying the mode; `reconcile()` still returns just the frame (bit-unchanged). The mode lives in `views_frames_reconcile` (`result.py`), off the leaf's generic header, so the C-47 / ADR-020 generic-only guard holds and the leaf stays free of reconciliation vocabulary. The mode literals (`point-broadcast`/`aligned-draws`) match pipeline-core's `reconcile_frames` constants verbatim for cross-repo consistency. A caller needing in-isolation auditability records the returned mode in its own (consumer-side) metadata. |

Cross-refs: C-47 (eval provenance kept out of the generic header — the precedent), ADR-020 (provenance split by concern), ADR-013 (`FrameMetadata` optional-extensible but generic), ADR-001 (leaf accretion guard), ADR-023 (the reconciliation sibling; its Open-Questions records this), D-11 (the analogous "keep removable/edge conveniences off the frozen leaf" decision); GH #144; pipeline-core C-200b (the silent-mode risk this addresses consumer-side).

---

## Resolved Concerns

> Resolved 2026-07-31 by **ADR-027** (Epic #208 / S1 #209) — the #113 decision.

### C-58: a reconciler cutover verified against the oracle but not a live production slice — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-58 |
| Resolved | 2026-07-31 (Epic #208 / S2 #210) |
| Resolution | **Both things this entry asked for have shipped, and were verified present before closing.** (1) The check itself is a single command — `scripts/verify_reconcile_parity.py --compare OLD.parquet NEW.parquet` (`run_compare`), which aligns two served forecast parquets on their identity columns and reports drift against `rtol=1e-5/atol=1e-6`. (2) The cutover runbook now *requires* it: `docs/guides/reconciliation_migration_and_cutover_runbook.md` Phase 2 gives the exact invocation and says **stop and investigate** if it diverges, and the runbook's gate table lists "Production slice" as a required row. The original gap — a cutover validated only by the frozen oracle chain, with no comparison against a file production actually served — is therefore closed by tooling plus a written requirement. **What is left is process compliance, not a technical gap:** someone could still skip a step the runbook tells them to run. That is not a defect this register can hold open, and it is the same trust the other runbook gates rest on. |

---

### C-76: `FeatureFrame.from_2d` was documented "deprecated" on the frozen surface — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-76 |
| Resolved | 2026-07-31 (Epic #208 / S2 #210) |
| Resolution | **The docstring was simply wrong, and the fix was to correct it — the method is not deprecated and there is no reason to remove it.** Reading the code settled this: `from_2d` builds a frame from a 2-D `(N, F)` array of *unsampled* features and adds the trailing sample axis to give `(N, F, 1)`. Because ADR-012 makes the sample axis always explicit, that is the ordinary constructor for deterministic features — not a shim for a superseded API. It is exercised by two tests (`tests/test_frames.py`, `tests/test_construction_red.py`) and documented in the FeatureFrame contract. The words "legacy" and "(deprecated shim)" were leftover framing from when the sample axis was introduced. Docstring rewritten to describe what the method does; `docs/CICs/FeatureFrame.md` updated to match and to say explicitly that it is ordinary supported surface. **No MAJOR-removal rider is recorded** — the earlier assumption that one was needed came from believing the docstring rather than the code. |

---

### C-52: construction-convenience accretion on the leaf — the "camel's nose" for adapters (ADR-001) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-52 |
| Resolved | 2026-07-31 (**ADR-027**, Epic #208 / S1 #209) |
| Resolution | **ADR-027 declines #113** — no `build_prediction_frame`, no `PredictionFrame.from_arrays`, no `factory.py`. The concern guarded an addition that will not be made, so the slope it feared has no first step. Its substance is **preserved, not discarded**: ADR-027 records the binding constraints any future construction convenience must satisfy (classmethod, zero own logic, singular, no `factory.py`) and names what would reopen the decision (a receipted site where two steps are genuinely inadequate — verbosity alone is not a receipt). Future accretion requests close by citing ADR-027 rather than re-litigating. The **serialization** half of this entry's trigger (`to_parquet`/`to_pddf` on the frame classes) was already settled off-leaf by **D-11**. |

---

### C-53: two frozen `PredictionFrame` construction paths can diverge — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-53 |
| Resolved | 2026-07-31 (**ADR-027**, Epic #208 / S1 #209) |
| Resolution | **ADR-027 declines #113** — the second construction path is never created, so there is nothing to diverge from `__init__`. (Had it shipped, D-09's **zero-own-logic** constraint was the mitigation: pure delegation means a future additive identifier per ADR-013 flows through without a signature edit. ADR-027 records that constraint for any future reconsideration.) |

---

### C-54: #113 DoD overstates scope — "retires the baseline duplicate" would pull a consumer edge into the leaf — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-54 |
| Resolved | 2026-07-31 (**ADR-027**, Epic #208 / S1 #209) |
| Resolution | **ADR-027 declines #113**, so its Definition-of-Done is moot and cannot be misread. ADR-027 states explicitly that views-baseline's helper is a **domain grid-builder** (a `value_fn` looped over entity×time) — an ADR-001 consumer edge that **stays in views-baseline**, and that only its innermost two-line construction was ever in scope. No cross-repo action follows for any sibling repo. |

---

### C-72: `arrow.load` trusted the parquet row order it never checked — silent sample-slot corruption on out-of-order input — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-72 |
| Tier | 2 (silent data corruption, but only reachable via an out-of-contract intermediary mutating the file between `save` and `load` — the supported save→load path was always correct) |
| Source | views-postprocessing ADR-013 §4.5(b) (the consumer-side check it mandated); filed as #199 item 1 (2026-07-19); fixed 2026-07-28 (v1.10.1). |
| Resolved | 2026-07-28 (v1.10.1, #199 item 1) |
| Location | `src/views_frames/io/arrow.py` (`load` — the positional `reshape(n, s)` reconstruction). |
| Resolution | `load` now validates the wire-contract layout before reshaping and raises `ValueError` on: row count not a positive multiple of the header's `n_samples` (truncated/filtered); the `sample` column deviating from the written `tile(arange(S), N)` order (row-level reorder); or `time`/`unit` not constant within a sample block (cross-cell row swaps — invisible to the tile check alone). A whole-cell block reorder stays loadable (identifiers travel with their draws — a consistent table). Red tests pin all three raises + the consistent-reorder boundary (`tests/test_io.py`). Consumers' WET pre-checks per ADR-013 §4.5(b) are now redundant — the leaf hardens every consumer at once. Residual: #199 item 2 (mmap/partitioned arrow reading) stays open in the issue — an optimization, explicitly not a contract dependency. |
| Cross-refs | C-29 (the original io red-team family this extends), C-51 (assert-raise-path testing convention), #199. |

---

### C-70: audit polish bundle — docs narrative epoch-lag + three small test adds (four-axis audit 2026-07) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-70 |
| Tier | 3 |
| Source | four-axis audit 2026-07-02 (review-base-docs Phase 2 + test-review Phase 3) |
| Trigger | The next docs or tests PR — fold this bundle in rather than letting the narrative lag compound (a new contributor/agent onboarding from `CLAUDE.md` today is told a two-package v0.1.0 architecture). |
| Location | **Docs:** `CLAUDE.md` (epoch-stale: "Two packages", "Status: v0.1.0", no `views_frames_reconcile`); `README.md:7` (banner says v1.7.0; chronicle ends at 1.7.0); `docs/ADRs/013_*.md` (claims `feature_names` lives in `FrameMetadata` — it is a `FeatureFrame` constructor arg, `feature_frame.py::FeatureFrame.__init__`); `docs/CICs/{PredictionFrame,TargetFrame,FeatureFrame}.md` §5 (say `y_pred/y_true/y_features.npy` — actual artifact is `values.npy`, `io/npz.py::save`); `PredictionFrame.md` §6 ("TypeError on non-float32" — float64 is *coerced*, object dtype raises *ValueError*); `docs/CICs/README.md:52-56` ("no contracts yet" contradicting its own Active list); `docs/ADRs/README.md:6-55` (design-bible framing, "011–016", "six decisions"); `Reconcile.md` §10 (blanket "each §6 mode maps to a red test" — the missing-map-entry mode is pinned only at the leaf); stale `Last reviewed` dates on 3 frame CICs. **Tests:** a share-proportionality *law* test (the method's essence is otherwise pinned only by the frozen oracle; the falsify F5 probe proved the law holds — commit it); an mmap read-only pin (`frame.values.flags.writeable is False` after `load(mmap=True)` — F2 proved it); a reconcile-suite test for the missing-`(time,gid)`-mapping-entry raise. |
| Cross-refs | The systemic pattern: all doc drift is in narrative text `validate_docs.sh` does not check (banners, framing, filenames), while every mechanically-validated element is current. C-46 (the "verification surface depends on usage" family), C-58 (test-realism, registered), resolved C-67/C-68/C-69 (the fixed half of the same audit). |

The 2026-07 four-axis audit found the code↔contract agreement strong (30/30 public symbols CIC-covered, 15/16 project ADRs accurate, ~57/60 CIC guarantee items pinned) but the **narrative documentation an epoch behind** and three cheap test additions open. None affects correctness; the CLAUDE.md/ADR-013 items are the material ones (they misinform onboarding). **Tier 3** — maintainability/onboarding accuracy, multiple contributors affected via CLAUDE.md. **Resolved** (2026-07-02, the option-3 cleanup): the tests half by PR #195 (share-proportionality law, mmap read-only pin, missing-map-entry raise); the docs half in the follow-up docs PR (CLAUDE.md rewritten for the three-package released reality; README banner → v1.8.0 + chronicle; ADR-013 as-built amendment; the three CIC §5 filenames → `values.npy`; PredictionFrame §6 coercion wording; SpatioTemporalIndex §6 NaN-via-dtype wording; CICs/ADRs README framing refreshed; `Last reviewed` dates bumped; Reconcile.md §10 updated to name the actual pinning files). Plus a **recurrence guard**: `validate_docs.sh` now checks the README banner's MAJOR.MINOR against `pyproject.toml`, so the narrative epoch-lag pattern fails validation instead of accumulating. **Correction (2026-07-31, see C-74):** that last clause overstated the guard — `validate_docs.sh` is **not referenced in `.github/`**, so it fails validation only when a maintainer runs it locally, never in CI. The check exists and passes; it is simply not armed. Tracked as **C-74**; C-70 itself stays resolved (its docs+tests remediation did land).

---

### C-68: `reconcile_proportional` silently violated sum-to-country for tiny nonzero draw sums (the `+ 1e-8` epsilon), and silently clamped negative totals — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-68 |
| Tier | 2 |
| Source | test-review (2026-07-02, the untested-region flag) + falsify audit 2026-07-02 (F1 hard, F8 soft — empirically confirmed, independently reproduced) |
| Trigger | (historical) A country-month whose nonzero grid draws summed ≲1e-4 against a material cm total — the reconciled output silently under-conserved (50% shortfall at draw-sum 1e-8, 91% at 1e-9; still violating the §3 rtol at 1e-5), and `assert_reconcile_contract` rejected the package's own output. A negative country total silently clamped to an all-zero output (sum 0 ≠ the total). |
| Location | `src/views_frames_reconcile/proportional.py` (formerly `_EPS = 1e-8` at :30, `sum_nonzero + _EPS` at :74). |
| Cross-refs | Reconcile.md §3 (the sum-to-country guarantee that was silently violated) + §6 (now documents both fixes), ADR-023 (the bit-parity mandate the fix preserves), C-58 (the untested-region sibling), C-62 (same file, distinct: joint calibration), resolved C-67/C-69 + open C-70 (the same audit's other findings). |

The port's `+ 1e-8` denominator epsilon was a float32 **no-op for draw sums ≳ 0.1** (machine epsilon exceeds it — which is why all oracle-parity and gamma-draw tests never saw it) but **silently deflated the scale factor** for tiny nonzero sums: at a draw sum of 1e-8 a country total of 100 reconciled to 50, with no error signal, violating the stated §3 guarantee inside the documented input domain — the audit's one **hard falsification**. A negative country total was likewise neither rejected nor conserved (clamped to zero). **Tier 2** — silent violation of a stated contract guarantee, demonstrated in-domain; not Tier 1 because realistic fatality-scale draws sit well above the band. **Resolved** (2026-07-02): the epsilon is replaced by an explicit all-zero-draw guard (exact division for any nonzero sum; all-zero draws stay zero exactly as before), and negative totals now raise `ValueError`. The fix is **bit-identical on all realistic data** (torch-oracle parity green, unchanged); conservation now exact at float32 precision across the whole domain. Pinned by `tests/test_falsification_safety_audit_2026_07.py` (TestF1HardEpsilonRegion, TestF8SoftNegativeCountryTotal); Reconcile.md §6 updated; `proportional.py` module docstring records the deliberate deviation from the torch original.

---

### C-67: the published conformance suites were a silent no-op under `python -O` — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-67 |
| Tier | 4 |
| Source | repo-assimilation (2026-07-02) + falsify audit 2026-07-02 (F3 — a float64 non-conformer with working save/load passed the envelope under `-O`) |
| Trigger | (historical) A consumer wiring `assert_frame_contract` / `assert_summarizer_contract` / `assert_reconcile_contract` into a CI or production job running `python -O`/`-OO` — every check silently passed regardless of conformance. |
| Location | `src/views_frames/conformance/__init__.py`, `src/views_frames_summarize/conformance.py`, `src/views_frames_reconcile/conformance.py` (bare `assert` throughout — stripped under optimized bytecode). |
| Cross-refs | ADR-016 (the cross-repo floor whose teeth this restores), C-46 (the "verification depends on how consumers run it" family). |

The three published conformance suites — the ADR-016 floor consumers run in *their* CI — were bare `assert` statements: under `-O` the interpreter strips them and the suite reports green while checking nothing. **Resolved** (2026-07-02): each suite's public entry points now call `_require_assertions()`, which raises `RuntimeError` when `__debug__` is false — under `-O` the suite **refuses to run loudly** instead of lying. Pinned by a subprocess regression test (`TestF3SoftConformanceUnderO`). **Tier 4** — no consumer was known to run optimized bytecode; latent sharp edge on the verification surface, not a data-corruption path.

---

### C-69: empty-index `searchsorted` crashed with an obscure `IndexError` — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-69 |
| Tier | 4 |
| Source | repo-assimilation (2026-07-02, the `np.clip(pos, 0, -1)` observation) + falsify audit 2026-07-02 (F4 — confirmed empirically) |
| Trigger | (historical) Any same-level join against an **empty** `SpatioTemporalIndex` (e.g. aligning to a frame filtered down to zero rows) — `searchsorted` clipped positions into an empty array and died with `IndexError: index -1 is out of bounds` instead of a clean result. |
| Location | `src/views_frames/index.py` (`searchsorted`, the `np.clip(pos, 0, len-1)` corner at the formerly-unguarded empty-self path). |
| Cross-refs | C-57 (the same loud-but-obscure error family — `map_estimate`'s inf `IndexError`, still open with #89), C-21 (row-semantics territory). |

**Resolved** (2026-07-02): an explicit empty-self early-return — every row of `other` is absent from an empty index, so the result is all `-1`, the method's documented not-found value. Pinned by `TestF4SoftEmptyIndexSearchsorted`. **Tier 4** — a crash (loud), not silent corruption; ergonomics-grade. The falsify audit's bonus observation (a *frame* passed to `reindex` surfaces as `AttributeError` rather than a clean `TypeError`) is noted here, deliberately unfixed — same family, below threshold.

---

### C-65: non-finite fail-loud proven only on the single-shot path, not the blocked (multi-block) path — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-65 |
| Tier | 3 |
| Source | test-review (2026-06-27) |
| Trigger | When the per-block `np.isfinite(...)` guard in `exceedance`/`expected_shortfall` is hoisted, vectorized, or otherwise moved out of the per-block reducer — a refactor the existing single-row tests would not catch. |
| Location | `src/views_frames_summarize/exceedance.py` + `expected_shortfall.py` (the `np.isfinite` guard, called per block by `_common.block_apply`); pinned by `tests/test_summarize_exceedance.py::test_nonfinite_in_a_non_first_block_raises` + the matching test in `tests/test_summarize_expected_shortfall.py`. |
| Cross-refs | C-50 (exceedance fail-loud on NaN — RESOLVED), C-56 (expected_shortfall fail-loud on NaN/±inf — RESOLVED; the guard *exists*, this was the **verification-completeness gap** on its blocked path), C-25 (the block_apply memory-bounding that introduces the path). |

The non-finite guard (reject NaN/±inf draws) lives **inside** `_exceed`/`_expected_shortfall`, which `block_apply` calls **per row-block** — but every committed adversarial test placed the non-finite draw in a **1–2 row** frame (the single-shot path, `n ≤ ROW_BLOCK`), so the blocked path had **no red test** and a future hoist of the guard above the per-block loop would have silently regressed. **Tier 3** — verification completeness, not a current defect. **Resolved** (2026-06-28, epic #179 / S3 #182): a parametrized red test (NaN, +inf, −inf) now forces `>1` block via the `block_rows` kwarg with the non-finite draw in a **non-first** block and **block 0 all-finite** — so a guard that inspected only the first block would pass silently, and the test fails loud as required. 100% line+branch coverage held; no `src/` change.

---

### C-63: the frame `values` buffer is not write-protected, so the immutability guarantee is unenforced — RESOLVED (contract corrected; enforce deferred)

| Field | Value |
|-------|-------|
| ID | C-63 |
| Tier | 2 |
| Source | repo-assimilation (2026-06-27), empirically verified; confirmed + extended by test-review (2026-06-27) |
| Trigger | When a consumer applies an in-place numpy mutation to `frame.values` (a natural idiom — e.g. `frame.values[mask] = 0`, `frame.values *= scale`, a clamp/normalise in place) on a frame obtained from `with_metadata`/`select`'s buffer-sharing path. |
| Location | `src/views_frames/_validation.py::coerce_values` (`coerce_values` returns a float32 input **without copy** and without `setflags(write=False)`); contrast `src/views_frames/index.py::SpatioTemporalIndex.__init__` (the two `setflags(write=False)` calls) (the index arrays **are** write-protected); `with_metadata` (`prediction_frame.py`/`target_frame.py`/`feature_frame.py`) shares the buffer; `tests/test_properties.py::test_with_metadata_shares_the_values_buffer` pins only the *sharing*, not read-only-ness. **Contract side:** the three frame CICs §9 + README design principle 3 (now corrected). |
| Cross-refs | ADR-025 (the resolving decision + the deferred-enforce MAJOR-rider), C-07 (copy-vs-view / structural-sharing semantics — RESOLVED), ADR-013 + README design principle 3 (immutable value objects), GOVERNANCE.md (SemVer: "tightening an invariant" = MAJOR), ADR-018 (`values` is frozen-surface). |

The leaf advertised **immutable value objects**, but the guarantee was enforced only for the *index* (`time`/`unit` are stored `setflags(write=False)`), not for the *value block*: `frame.values.flags.writeable` is **True**, `with_metadata` shares the buffer, so an in-place mutation of `frame.values` would **silently corrupt every frame sharing it**, with no error signal. **Tier 2** (silent-corruption potential + structural fragility with a realistic trigger), not Tier 1 — the system itself never mutates `.values` (the audit found **zero** in-place `.values`/`_values` mutations in `src/` or `tests/`). **Resolved** (2026-06-28, epic #179 / S2 #181, **ADR-025**): the enforce — `setflags(write=False)` on `.values` — is a **MAJOR** under `GOVERNANCE.md` ("tightening an invariant" on the frozen-surface `values`, ADR-018), triggering the cross-repo coordinated-bump process; disproportionate for an unexercised hole. So the contract was **corrected to match the code** instead: the value buffer is immutable **by convention** (writeable on purpose, to preserve zero-copy / `mmap`; mutating it in place is unsupported and may corrupt shares), the **index** is the enforced one. Corrected in the three frame CICs §9/§3 + README design principle 3; ADR-025 records the decision **and** the `setflags`-enforce as a **deferred MAJOR-rider** (added free on the next MAJOR — the exact one-line-per-constructor change + a red test). **Resolution carries a residual:** the value buffer is still writeable, so a careless in-place mutation is still *possible* until the deferred enforce lands — mitigated by the documented unsupported-status and the absence of any such mutation in the ecosystem.

---

### C-64: `views_frames_reconcile` ships without a CIC — the package is contract-less — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-64 |
| Tier | 3 |
| Source | test-review (2026-06-27) |
| Trigger | When a behavior change to the reconcile package needs a written contract to test against and amend — e.g. adding a third reconciliation mode, the ADR-024 principled-reconciliation **sibling module**, or a new public symbol on `ReconciliationModule`/`ReconciliationResult` — and there is no §3-guarantee / §6-failure-mode CIC to extend. |
| Location | `docs/CICs/Reconcile.md` (now authored); governs `src/views_frames_reconcile/{module,result,proportional,grouping,validation,conformance,frames}.py` incl. `reconcile_result`/`ReconciliationResult`/`POINT_BROADCAST`/`ALIGNED_DRAWS`/`METHOD_PROPORTIONAL`. |
| Cross-refs | ADR-006 (intent contracts for non-trivial classes — the governing requirement), ADR-023 (the reconcile sibling), ADR-024 (the principled-reconciliation design the CIC §11 points to), C-62 (the per-draw-approximation limitation, documented in §2/§6), D-12 (the mode-reporting decision, §2/§3). |

The leaf and summarize surfaces are CIC-governed, but the **entire `views_frames_reconcile` package** (shipped Epic 11, v1.7.0; extended v1.8.0) had **none**, and `Summarize.md §2` explicitly fences reconciliation out — so the package's red/beige/green completeness had nothing authoritative to be measured against. **Tier 3** — governance/maintainability (contract↔test alignment), not silent corruption. **Resolved** (2026-06-28, epic #179 / S1 #180): `docs/CICs/Reconcile.md` authored as a package-level CIC (§1–§11) modeled on `Summarize.md` — documenting the sum-to-country / zero-preservation / non-negativity / de-mutation guarantees (§3), the point/aligned **mode** contract (§3), the five fail-loud validation guards + the per-draw-approximation caveat (§6), and the green/beige/red test alignment (§10); listed under Active Contracts in `docs/CICs/README.md`; `validate_docs` green.

---

### C-59: the summaries notebook teaches named intervals with no calibration / coverage demonstration — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-59 |
| Tier | 3 |
| Source | expert-method-review (2026-06-26 — Gneiting/Gelman seats) |
| Trigger | When `notebooks/02_summaries.ipynb` is built and shipped **without** a calibration/coverage section — displaying named X% HDI/quantile intervals (and the MAP) whose nominal coverage is never demonstrated on synthetic data with a known latent truth. |
| Location | `notebooks/02_summaries.ipynb` (planned — §4 HDI tower / §5 quantiles). |
| Cross-refs | C-60, C-61 (the notebook-completeness cluster); the views-evaluation boundary (scoring lives there — but coverage-on-synthetic-truth is a property demo, not scoring). |

A notebook whose purpose is to build trust in these summaries that shows a "90% HDI" but never that it covers ~90% asserts the very claim it should prove. On synthetic draws the latent truth is known, so empirical coverage of each band + a PIT histogram are free to compute and are the highest-value addition (Gneiting2014; Kuleshov2018). **Highest-priority of the three notebook gaps.** **Resolved** (2026-06-27, PR #174 / commit `ea39cc6`): `02_summaries.ipynb` ships a calibration/coverage panel — empirical coverage of the 50/90/95/99 HDIs against the known synthetic truth, a PIT histogram (calibrated vs over-confident), and a recovery-vs-`S` view (Gneiting2014/Kuleshov2018), all on the ground-truth-carrying `notebooks/_synthetic.py`. No scoring API was added (scoring stays in views-evaluation).

---

### C-60: the reconciliation notebook risks presenting bit-identity as method validation — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-60 |
| Tier | 3 |
| Source | expert-method-review (2026-06-26 — Hyndman seat) |
| Trigger | When `notebooks/03_reconciliation.ipynb` headlines the oracle / bit-identity parity story **without** (a) situating per-draw *proportional* reconciliation in its literature (MinT / bottom-up / probabilistic reconciliation; proportional = the pragmatic, information-losing baseline; the principled upgrade is deferred as views-postprocessing C-37) and (b) separating *implementation fidelity* (bit-identical to the torch oracle) from *method quality*. |
| Location | `notebooks/03_reconciliation.ipynb` (planned — §7 provenance). |
| Cross-refs | C-59, C-61; views-postprocessing C-37 (probabilistic-reconciliation upgrade); C-58 (the analogous "don't over-read bit-identity" caution at the cutover). |
| | Lit: Wickramasuriya2019 (MinT), Hyndman2011, Panagiotelis2023 (probabilistic reconciliation). |

Bit-identity proves the *port* is faithful; it says nothing about whether proportional reconciliation is *good*. A reader infers methodological endorsement of a method the forecasting literature considers superseded. **Resolved** (2026-06-27, PR #174 / commit `ea39cc6`): `03_reconciliation.ipynb` panel §A situates proportional top-down against MinT (Wickramasuriya2019) / probabilistic reconciliation (Panagiotelis2023), states explicitly that **bit-identity proves faithful relocation, not method quality**, and frames the principled upgrade as deferred (views-postprocessing C-37); panel §B adds a does-it-help check against the known truth (it improves the country total but *worsens* per-cell — coherence, not accuracy).

---

### C-61: the notebooks have no spatial / map view despite showcasing spatial forecasts — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-61 |
| Tier | 3 |
| Source | expert-method-review (2026-06-26 — Wilke/Kay + VIEWS/FAO domain seats) |
| Trigger | When the notebooks are shipped with only per-cell / histogram displays and **no map/lattice view** — the most operationally-expected visualization for PRIO-GRID forecasts is absent, so adopters can't connect the summaries to the spatial product they consume. |
| Location | `notebooks/02_summaries.ipynb` / `notebooks/03_reconciliation.ipynb` (planned). |
| Cross-refs | C-59, C-60. Constraint: views-frames is geography-blind (ADR-014) — the map view must use a **toy synthetic lattice**, embedding no domain geography. |

A spatial-forecasting showcase with no spatial display under-serves the audience. Achievable on a synthetic square lattice with zero domain knowledge. **Resolved** (2026-06-27, PR #174 / commit `ea39cc6`): both `02_summaries.ipynb` and `03_reconciliation.ipynb` render toy-lattice map views on a synthetic square lattice (no domain geography — ADR-014): 02 maps the point estimate, the 90% HDI width, and decision-relevant exceedance; 03 maps raw-vs-reconciled point estimates and the change map.

---

### C-55: aggregate `expected_shortfall` worst-case is silently wrong when summed samples are not a true joint posterior — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-55 |
| Tier | 2 |
| Resolved | 2026-06-25 (Epic 10 / I3, v1.6.0) |
| Resolution | `expected_shortfall` stays geography-blind; country worst-case = `aggregate_distributions` → `expected_shortfall` (compose). `test_aggregate_composition_is_joint_worst_case` (`tests/test_summarize_expected_shortfall.py`) proves it on **anti-aligned** draws (`[1,2,3,100]`/`[100,3,2,1]` → summed `[101,5,5,101]`): the joint ES(0.5) = **101**, while the per-cell ES sum to **103** — non-recoverable, and subadditive (`101 ≤ 103`). The joint-sample obligation is the consumer's (a documented CIC failure-mode); the residual upstream guarantee lives in views-models / reconciliation. See ADR-022, C-49, C-56. |

---

### C-56: naive `expected_shortfall` silently corrupts the worst-case when NaN draws are present — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-56 |
| Tier | 2 |
| Resolved | 2026-06-25 (Epic 10 / I1+I2, v1.6.0) |
| Resolution | `expected_shortfall` **fails loud** on any non-finite value in the reduced values (`_expected_shortfall` raises `ValueError` before the sort, so the NaN/`+inf`-sorted-last top-`k` mean can never silently select them) rather than return a NaN/`inf` worst-case (ADR-008). The guard is `np.isfinite`, **widened from `np.isnan` to also reject ±inf by the falsify audit 2026-06-25** (an `inf` draw — always an upstream bug — otherwise contaminated the tail mean to `inf` silently; P5b). `test_nan_draw_raises` + `test_inf_draw_raises` (`tests/test_summarize_expected_shortfall.py`) assert it raises (including a NaN in a non-first block). See ADR-022, C-50, C-55, C-57. |

---

### C-49: aggregate `exceedance` tail is silently wrong when summed samples are not a true joint posterior — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-49 |
| Tier | 2 |
| Resolved | 2026-06-24 (Epic 9 / I3, v1.5.0) |
| Resolution | The compose path is implemented and proven: country exceedance = `aggregate_distributions(grid, mapping, level)` → `exceedance` per row, never a per-cell combination. `test_aggregate_composition_is_joint_exceedance` (`tests/test_summarize_exceedance.py`) shows `P(Σ > c)` on the summed posterior (= 0.5 for the worked case) is **unrecoverable** from the per-cell exceedances (both 0). The joint-sample requirement is an explicit CIC failure-mode (Summarize §6) contracted on the aggregation boundary, not on `exceedance` — the estimator stays geography-blind (ADR-014). The residual upstream obligation (are the summed samples a true joint?) lives in views-models / reconciliation, outside the leaf. See ADR-021, C-50. |

---

### C-50: naive `exceedance` silently deflates onset (`P(Y>0)`) when NaN draws are present — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-50 |
| Tier | 2 |
| Resolved | 2026-06-24 (Epic 9 / I1+I2, v1.5.0) |
| Resolution | `exceedance` **fails loud** on any non-finite value in the reduced values (`_exceed` raises `ValueError` before the silent `NaN > c == False` miscount) rather than returning a deflated probability (ADR-008; D-07 settled as fail-loud). The guard is `np.isfinite`, **widened from `np.isnan` to also reject ±inf by the falsify audit 2026-06-25** (an `inf` draw otherwise silently blessed `P` as a valid-looking probability since `inf > c` is `True`, masking the upstream bug; P5b — ±inf *thresholds* stay valid). `test_nan_draw_raises` + `test_inf_draw_raises` (`tests/test_summarize_exceedance.py`) assert a non-finite draw raises. A `nan_policy='skip'` remains a reversible future MINOR (D-07). See ADR-021, C-49, C-57. |

---

### C-51: `assert_frame_envelope`'s structural rejection paths were tested only transitively — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-51 |
| Tier | 3 |
| Resolved | 2026-06-24 (test-review follow-up) |
| Resolution | Added three **direct** adversarial tests for the published checker's reject paths (`tests/test_conformance.py`), each asserting `assert_frame_envelope` raises: `test_envelope_rejects_non_ndarray_values` (a Python list — the `isinstance ndarray` assert), `test_envelope_rejects_missing_trailing_axis` (1-D values — `ndim >= 2`), and `test_envelope_rejects_row_count_mismatch` (`n_rows` ≠ `values.shape[0]`). With the pre-existing `test_envelope_rejects_non_float32_values`, all four **reachable** reject assertions now have a dedicated red test; the object-dtype assert is unreachable (guarded by the `== float32` check) and left as defensive code. Test-only — no `src/` change, `CONFORMANCE_FLOOR` stays 1.0.0. See C-46 (the mitigation this verifies), ADR-020. |

---

### C-47: evaluation-specific provenance must not leak into the generic `FrameMetadata` — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-47 |
| Tier | 3 |
| Resolved | 2026-06-24 (v1.4.0; ADR-020 substrate work) |
| Resolution | The (previously deferred) `FrameMetadata` extension was made and **respects the split** (the C-47 guard). v1.4.0 adds only **generic** provenance — `run_id`, `data_version` — as optional/MINOR fields (ADR-013), meaningful for any frame. **Eval-specific** provenance (`scoring_code_version`, a full-precision `evaluation_timestamp`) was deliberately kept out of the generic header and stays in `views-evaluation`'s `MetricFrame` metadata, so evaluation semantics never enter a package that is explicitly *not* evaluation (ADR-014/ADR-017). The `metadata.py` module docstring records the guard for future extensions. See ADR-020, C-46, D-02; `src/views_frames/metadata.py`. |

---

### C-42: bimodality caveat + estimator-choice guidance absent from the shipped public docs — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-42 |
| Tier | 4 |
| Resolved | 2026-06-24 (publish-review follow-up) |
| Resolution | Added to the public **README** (§0a Quickstart): a "Which estimator?" note pairing each frozen estimator with its coherent-tower sibling (`map_estimate`↔`tower_point`, `hdi`/`quantiles`↔`hdi_tower`, `summarize_tower`), and a **bimodality caveat** — a `0` flag means "no clear bimodality detected," **not** "proven unimodal" (conservative-by-design). Mirrored in the **CHANGELOG** `[Unreleased]` (Documentation). The behaviour-level limitation remains tracked as the still-open **C-34** (and #89). Docs-only, no contract change. See C-34, ADR-019. |

---

### C-41: ultrareview v1.1.0 nits — misleading `_pin` docstring + stale `audit.py` unpack — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-41 |
| Tier | 4 |
| Resolved | 2026-06-24 (ultrareview follow-up) |
| Resolution | Both `nit`-severity ultrareview findings fixed; no shipped-package behaviour change. (a) Reworded the `_pin` docstring (`tower.py`) — was "the fixed grid produces no exact distance ties" (false; e.g. `0.075` is equidistant from `0.05`/`0.10`), now "`argmin` breaks ties on the lowest index, so a midpoint mass pins **down** to the lower floor" — matching the tested invariant `test_beige_pinning_is_deterministic_on_ties`. (b) Fixed `research/map_hdi/audit.py::collect_cells` stale 3-tuple unpack → `obs, _ref, _modes, meta = battery.load()` to match the 4-tuple `battery.load()` returns (and the four sibling scripts). ruff + 100% coverage green. See C-39 (the earlier doc↔code drift cluster). |

---

### C-40: no Trove classifiers on the PyPI release — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-40 |
| Tier | 4 |
| Resolved | 2026-06-24 (falsify follow-up) |
| Resolution | A `/falsify` release-readiness audit (soft falsification P3) found `pyproject [project]` declared no Trove `classifiers`, so the public PyPI release would not advertise supported Pythons / development status / topic (publishes fine, but unpolished). Added classifiers (`Development Status :: 5 - Production/Stable`, `Intended Audience :: Science/Research`, `Operating System :: OS Independent`, `Programming Language :: Python :: 3` + 3.10–3.13, `Topic :: Scientific/Engineering`, `Typing :: Typed`); the deprecated `License ::` classifier is intentionally omitted (the PEP-639 `license = "MIT"` expression is used). Verified in the built wheel METADATA; guarded by `tests/test_packaging.py`. The rest of the audit **survived** — additive over the frozen v1.0 contract, wheel builds + installs + imports + runs end-to-end from a clean env (P1/P2/P4/P6). Source: falsify (2026-06-24). |

---

### C-39: foundational CICs/ADRs lag the code — stale signature, fossil examples, undocumented methods — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-39 |
| Resolved | 2026-06-24 (review-base-docs follow-up) |
| Resolution | Reconciled the foundational CICs + ADRs against the v1.1.0 code (`validate_docs.sh` green; fossils confirmed removed). **SpatioTemporalIndex CIC:** corrected the `cross_level_align(mapping, target_level)` signature + examples; documented `cross_level_align_arrays`, `select`, `has_unique_rows`, the C-21 duplicate-row stance, and the accessor surface. **Protocols CIC:** purged the pre-ADR-017 `Sampled.collapse` fossil (§5/§6/§8/§10), added the `SpatioTemporalIndexed.index` member, cited `test_frames_satisfy_runtime_checkable_protocols`. **Prediction/Feature/Target CICs:** fixed the `pf.collapse("arithmetic_mean")` example (→ `collapse(pf, np.mean)`) and documented `select`/`reindex`. **Summarize CIC:** added `aggregate_distributions_arrays`, refreshed the v0.2.0 note. **ADR-018:** forward pointer to ADR-019's additive surface; **ADR-019:** fixed the reproducibility example + resolved the `research/`-landing open question; **ADR-017** charter + **ADR-005** testing notes refreshed. Docs-only (no code change). See C-23 (an earlier doc↔code drift fix), ADR-006. |

---

> Resolved 2026-06-24 by **Epic 7** (post-1.1.0 polish, branch `development`): the
> **post-1.1.0 polish** cluster {C-35, C-36, C-37, C-38} — low-severity doc/test-completeness
> items from the 2026-06-24 repo-assimilation + test-review — closed before the v1.1.0 `main`
> merge. **No `src/` behaviour change** (the only `src`-adjacent touch was the coverage config).

### C-35: README "Status" header still presents v1.0.0 after the v1.1.0 release — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-35 |
| Resolved | 2026-06-24 (Epic 7, I1 #92) |
| Resolution | Updated the README `Status` header to present **v1.1.0** (frozen since v1.0.0, ADR-018; the v1.1.0 surface is additive, ADR-019) and added the coherent-tower estimators to the package description. The only remaining `v1.0.0` mention is the correct freeze-baseline reference; `CONFORMANCE_FLOOR` left at `1.0.0` (additive surface → no floor bump). `validate_docs.sh` green. See ADR-018, ADR-019. |

---

### C-36: 100% coverage gate is line-only — branch outcomes can go untested — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-36 |
| Resolved | 2026-06-24 (Epic 7, I3 #94) |
| Resolution | Enabled `branch = true` in `[tool.coverage.run]` (`pyproject.toml`); the existing `--cov-fail-under=100` gate now enforces **line AND branch** coverage. Free to enable — the suite already covered **118/118 branches (0 partial)** — and it permanently closes the blind spot: a future untested branch fails CI. See C-29, C-31 (resolved), ADR-005. |

---

### C-37: Protocol runtime-conformance (Frame / Sampled / Persistable) not directly asserted — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-37 |
| Resolved | 2026-06-24 (Epic 7, I2 #93) |
| Resolution | Added a parametrized 🟩 green test (`tests/test_properties.py::test_frames_satisfy_runtime_checkable_protocols`) asserting all three frames are runtime instances of each `@runtime_checkable` protocol — `Frame`, `SpatioTemporalIndexed`, `Sampled`, `Persistable` — directly asserting the Protocols CIC §3 guarantee (previously checked only indirectly via `assert_frame_contract`). 100% coverage held. See ADR-005, ADR-016. |

---

### C-38: vectorized-summarizer memory tests are environment-sensitive (latent CI flake) — RESOLVED (accepted / monitored)

| Field | Value |
|-------|-------|
| ID | C-38 |
| Resolved | 2026-06-24 (Epic 7, I4 #95) |
| Resolution | Assessed and **accepted as monitored** (no behaviour change). Measured headroom at n=1M: the scale guards run **4.0–6.8x** under threshold; the tower guard is tightest at **2.1x** (`hdi_tower`/`bimodality`, ~61 MB vs 128 MB input) — adequate for a deterministic op, and a real blocking regression (whole-grid alloc, hundreds of MB+) still trips it. Documented the margin + the trigger in a comment on `test_tower_memory_is_bounded_at_grid_scale`. Reopen if the trigger fires (a `numpy<3` bump or a CI-runner-class change). See C-22, C-25 (resolved). |

---

### C-45: tower "quiet row" rule was an absolute-magnitude (`max ≤ 1.0`) zeroing — count-domain assumption in a domain-agnostic leaf — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-45 |
| Tier | 2 |
| Source | views-faoapi integration spike (2026-06) — `REPORT_tower_quiet_rule_scale_contract.md` |
| Resolved | 2026-06 (Epic 8, ADR-019 amendment; v1.3.0) |
| Trigger | If a future change re-introduces a magnitude-based zero default (a non-`None` `zero_cutoff`, or a hard `max <= k` short-circuit), it returns — re-run the distribution-agnostic tests (a tight sub-1 mode and a `beta`/`[0,1]` field are not zeroed by default; scale-consistency under ×k; opt-in `zero_cutoff` reproduces the magnitude behaviour). |
| Location | `src/views_frames_summarize/tower.py` (`_zero_mask`), `config.py` (`zero_cutoff`); the four call sites `tower_point.py`/`summarize_tower.py`/`bimodality.py`/`hdi_tower`. |

**Symptom.** The original "quiet row" short-circuit returned `0.0` for any row whose **maximum draw was ≤ 1.0**, ignoring where the mass sat — zeroing the point **and** all `hdi_tower` bands **and** suppressing `bimodality`. On 1.2.0 it zeroed a tight sub-1 mode (`[0.7]*32 → 0`), zeroed a `beta`/`[0,1]` probability target **everywhere**, flipped at the `max == 1.0` boundary (scale-dependent), and on the FAO raw-count cache silently zeroed ~11,075 low-intensity active cells. A **count-domain magnitude assumption** baked into a domain-agnostic leaf (against ADR-014/ADR-003); the platform reserves "all draws < 1.0" for a scale-plausibility *alarm* (ADR-055 / D-29), not output zeroing. **Distinct from C-44** (the degenerate-tip bug, resolved).

**Resolution (Epic 8 — #102, v1.3.0).** The magnitude rule is **removed as a default**: `config['zero_cutoff']` defaults to `None` (off) and is read **live** by `_zero_mask` (the import-time snapshot wart is fixed). Zero-inflation is now handled entirely by the **density** of the `tip_mass` floor (shipped in C-44) — a zero-majority row reads 0, a body-majority row reads the body mode — so the family is **distribution-agnostic** (counts, continuous, normal, rate/probability), proven across a distribution test matrix. A **count** consumer that wants the old "sub-1 ⇒ 0" behaviour sets `zero_cutoff` to a float (opt-in, runtime-live), *or* applies its own `mass_at_zero` policy (faoapi already has one) — the modeling choice is the consumer's, not a leaf default. ADR-019 amended; Summarize CIC documents the opt-in + the consumer-owns-the-zero-policy note. See C-32 (the sibling "estimator design" concern, #89 cluster), C-44 (resolved, distinct), ADR-014/ADR-003, ADR-019.

---

### C-44: `tower`/`tower_point` minority-duplicate collapse (inside-out construction) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-44 |
| Tier | 1 |
| Source | views-faoapi integration audit (2026-06-24) — confirmed on the real forecast cache |
| Resolved | 2026-06-24 (ADR-019 amendment) |
| Location | `src/views_frames_summarize/tower.py` (`_dense_tower`, `_shortest_contained_in`, `_shortest_seed`); `tower_point.py`; `summarize_tower.py`. |
| Trigger | If a future change reverts to a **narrowest-floor-first** construction, drops the containment constraint, or sets `tip_mass` back to the ~2-sample 5% floor, the collapse returns — re-run the A–L truth-table + real-faoapi-cell red tests in `tests/test_summarize_tower.py`. |

**Symptom (silent output incorrectness — Tier 1).** The tower was built **inside-out** from the narrowest 5% floor, which at S≈32 holds only ~2 samples. "Shortest interval holding 2 samples" = "the two closest draws", and any **minority duplicated value** (a couple of exact zeros, a lone pair) is distance 0 apart and unbeatably "shortest". That degenerate floor became the foundation, and the inside-out nesting dragged the tip **and every published band** onto it. Confirmed on real faoapi cells (`pred_ln_sb_best`, 32 draws): cells with 2–3 exact zeros + a clear positive body returned `tower_point = 0.0` and `hdi 50% = [0, 1.49]` — silent signal loss on a non-trivial slice (~289 cells with faoapi mode > 0.5, up to 4.38, zeroed). The trigger is *any* duplicate, at any value (the bug report's case L: a lone `3.0` pair in an otherwise-distinct body captured the point at 3.0).

**Resolution.** The tower is now built **outside-in** (widest floor first, each narrower floor the shortest interval *contained in* its wider parent), robust by construction: the wide floors are well-determined and shed lonely outliers, and the containment constraint forbids a narrower floor from re-selecting an outlier window. The tip reads the configurable **`tip_mass`** floor (default 0.5 — the shorth), not the degenerate 5% floor. A `k<=0` floor collapses to a real *sample* (not an averaged median), keeping containment well-defined. The superseded partial fix (`_select_window`, a 50%-density tie-break that handled competing duplicates but not the lone-duplicate / real-data case) was removed. Covered by the A–L truth table, the duplicate-count sweep, the two real faoapi cells, and vectorized==scalar across seeds/shapes (all green; 100% line+branch). See C-32 (shared root — the directional-mode half, still open at #89), C-33 (the nesting half, resolved), ADR-019 (amended), ADR-009 (the config that now holds `tip_mass`).

---

### C-33: `hdi` computes each mass independently — no nesting (tower) guarantee — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-33 |
| Resolved | 2026-06-23 (ADR-019) |
| Resolution | Delivered the multi-mass guaranteed tower the entry prescribed: `views_frames_summarize.hdi_tower(frame, masses)` reads each requested mass off a **fixed canonical tower** built outside-in (each narrower floor the shortest interval *contained in* its wider parent — the direction was reversed in the C-44 redesign), so the bands **nest by construction** — no post-hoc expand/shift, no MAP coupling. Requested masses are **pinned** to the fixed grid (never inserted), so a mass's interval is independent of the other requested masses (the **reproducibility law**, asserted in the conformance suite). `tower_point` (the tower tip) and `bimodality` accompany it; `summarize_tower` bundles all three in one pass. The frozen single-mass `hdi` is unchanged — additive, MINOR under ADR-018. See C-32 (shared root — the directional-mode half, mitigated by `tower_point` but still open), ADR-019, #89. |

---

> Resolved 2026-06-23 by **Epic 6** (post-freeze test-coverage debt, branch
> `test/strengthen-tests`): the cluster {C-29, C-31} plus the test-review blind spots
> (construction red-gaps, green laws, value-object getters) are closed, and CI now enforces
> **100% line coverage** (`--cov-fail-under=100`).

### C-29: IO failure-mode paths have no red-team tests — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-29 |
| Resolved | 2026-06-23 (Epic 6, I1 #81) |
| Resolution | Added a 🟥 IO failure-mode block to `tests/test_io.py`: `arrow.save` with unsupported `values.ndim`, `FeatureFrame.load` from a state missing `feature_names`, `npz.load` with a missing `values.npy`/`header.json`, and `arrow.load` of a non-frame parquet. `io/arrow.py` + `io/npz.py` are now at 100% line coverage, and the I5 gate keeps them there. See C-09 (io state-dict contract), ADR-005. |

---

### C-31: `reindex` tested on `PredictionFrame` only — twin-parity coverage gap — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-31 |
| Resolved | 2026-06-23 (Epic 6, I2 #82) |
| Resolution | Added `tests/test_frame_parity.py` — a builder fixture parametrizing the shared frame surface (`reindex`/`select`/`with_metadata`/`save`-`load`) over **all three** frame types, filling the Feature/TargetFrame `reindex` gap (`feature_frame.py::FeatureFrame.reindex`, `target_frame.py::TargetFrame.reindex`) and locking parity so a future twin divergence fails CI. The construction red-gaps + green laws/getters the same test-review flagged were closed alongside (Epic 6 I3/I4); leaf + summarize are now at **100%** coverage. See C-16 (twins are separate siblings), ADR-005. |

---

> Reconciled to Resolved 2026-06-22 against the **v1.0.0 freeze (ADR-018)**: design-phase
> concerns whose owning ADRs (011–016) merged and shipped. **C-01 / C-08 / C-12** are
> resolved *by-decision* — the decision is ratified and frozen, and their original triggers
> persist only as **frozen-invariant guards** (they now describe a violation of the frozen
> scope, not an open question).

### C-01: `MetricFrame` does not satisfy the frame definition — RESOLVED (by-decision)

| Field | Value |
|-------|-------|
| ID | C-01 |
| Resolved | 2026-06-22 |
| Resolution | ADR-016 / README §13a.6 keep `MetricFrame` and `EvaluationFrame` in views-evaluation; the leaf defines only the index/key protocol they conform to. Ratified and frozen by ADR-018 (v1.0.0). **Frozen-invariant guard:** the original trigger — adding `MetricFrame` as a leaf frame sibling — now describes a scope violation of the frozen contract, not an open design question. See D-05. |

---

### C-02: "verbatim move" + "unify twins" + "defer sample-axis" cannot co-hold — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-02 |
| Resolved | 2026-06-22 |
| Resolution | The three-way contradiction is moot — the relocation was a deliberate numpy-only re-implementation, not a verbatim move. ADR-011 (Option C, no unified base) + ADR-012 (sample axis closed as explicit trailing `S≥1`) + README §10.2 reworded to "not verbatim"; pandas-free relocation done (C-17). Shipped in v1.0.0. See C-16. |

---

### C-03: unified twin base under-specified on the fields the twins differ on — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-03 |
| Resolved | 2026-06-22 |
| Resolution | ADR-011 Option C — no shared base. `feature_names`/`metadata` live on `FeatureFrame` only; `PredictionFrame` carries neither; siblings share only `SpatioTemporalIndex` + `_validation` + `protocols` + `io`. The god-class (`_ViewsDataset`/C-36) path was rejected in writing. Realised in v1.0.0 `feature_frame.py`/`prediction_frame.py`. See C-16. |

---

### C-05: governance/ownership gap for an N-repo leaf — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-05 |
| Resolved | 2026-06-22 |
| Resolution | ADR-016 + `GOVERNANCE.md` establish a named owner, release cadence, conformance floor, and the coordinated cross-repo MAJOR-bump process; the v1.0.0 freeze (ADR-018) fixes the contract the N repos pin. The residual *inherent* concentration risk is tracked as the one open item, C-13. See C-10. |

---

### C-06: blocking decisions must close before first code — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-06 |
| Resolved | 2026-06-22 |
| Resolution | The four blocking decisions (sample-axis, twin-model, metadata, cross-level) were ratified in README §13a and formalised by ADRs 011–016 *before* `src/views_frames/` was built; the v0.1.0→v1.0.0 implementation proceeded from ratified decisions, not against an unfinished doc. Moot once shipped. |

---

### C-08: identifier-set widening is a platform-wide MAJOR break — RESOLVED (by-decision)

| Field | Value |
|-------|-------|
| ID | C-08 |
| Resolved | 2026-06-22 |
| Resolution | ADR-013 — `{time, unit}` fixed; future identifiers are optional-only via the typed optional-extensible header. Frozen by ADR-018. **Frozen-invariant guard:** the original trigger — a *required* new identifier — is now a MAJOR bump that must run through the GOVERNANCE coordinated-bump process, not an open modelling choice. See D-02, C-13. |

---

### C-10: conformance-suite version-coordination paradox — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-10 |
| Resolved | 2026-06-22 |
| Resolution | ADR-016 conformance-floor policy + C-27 — `CONFORMANCE_FLOOR` is a single governed version that tracks the whole published conformance surface and bumps on any breaking change; consumers test against one floor, not a per-consumer pin. See C-05. |

---

### C-12: `SpatioTemporalIndex` naming collision — RESOLVED (by-decision)

| Field | Value |
|-------|-------|
| ID | C-12 |
| Resolved | 2026-06-22 |
| Resolution | The rename window closed at the v1.0.0 API freeze (ADR-018); the name `SpatioTemporalIndex` was kept and the collision with `pandas.Index` and datafactory's `SpatioTemporalGrid` accepted. **Frozen-invariant guard:** a future rename is now a MAJOR per GOVERNANCE, not a cheap pre-pin change. |

---

### C-15: cross-level alignment specified nowhere / not tracked — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-15 |
| Resolved | 2026-06-22 |
| Resolution | ADR-014 + README §4.3 split (same-level owned / cross-level protocol + injected mapping); `cross_level_align` is a specified, implemented, tested operation, made time-varying in C-20. Shipped in v1.0.0. See C-14, C-20. |

---

### C-16: the twins are not near-1:1 (≥6 divergence axes) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-16 |
| Resolved | 2026-06-22 |
| Resolution | ADR-011 (Option C) + ADR-012 + README §1 corrected — the ≥6 divergence axes are handled by *separate sibling classes* rather than a forced unification; sample-axis position is a single explicit trailing-axis convention. See C-02, C-03. |

---

### C-18: relocating `SpatialLevel` ports the entity-first tuple + a gid/id inconsistency — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-18 |
| Resolved | 2026-06-22 |
| Resolution | ADR-015 (fix-don't-port) — the leaf's `spatial_level.py` ships the time-first index and a consistent identifier vocabulary; the reversed (entity-first) tuple (**pipeline-core's C-65** — *not* this register's C-65, see Register Conventions → foreign ids) and the `priogrid_gid`/`priogrid_id` inconsistency were fixed, not ported. (Subsumes the original C-04 "SpatialLevel slippery slope".) |
| Recurrence guard | **Resolved-by-decision — the trigger now protects the decision.** Re-opens if anyone adds an alias/normalization layer for the legacy identifier spelling to `spatial_level.py`; the answer is ADR-015 (the leaf carries one canonical vocabulary) + the rename belongs upstream in pipeline-core (its ADR-034). |

**2026-07-27 — first live recurrence, discarded.** An unmerged remote branch (`gid_patch`, ~19 real lines plus an accidental 9,984-line dump) added exactly the ported inconsistency this entry resolved: `_ENTITY_ALIASES = {"priogrid_gid": "priogrid_id"}` plus a `SpatialLevel.normalize_entity_column` helper, with the *calling* half already merged in a sibling repo — i.e. a cross-repo change whose two halves landed 26 seconds apart, only one of which was reviewed here. Discarded on ratified grounds (ADR-015 fix-don't-port; ADR-018 freeze — an unratified addition to the frozen surface; C-52 accretion guard), branch deleted, and the legitimate follow-up (the upstream rename) tracked in views-r2darts2#24 with a SHA breadcrumb. Recorded here because it demonstrates the guard is load-bearing, not historical: the pressure to re-port the alias comes from consumers, arrives via feature branch, and can be pre-satisfied in another repo before the leaf ever reviews it.

---

> Resolved 2026-06-22 (release housekeeping).

### C-28: first-publish PyPI API token was account-wide (over-privileged) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-28 |
| Resolved | 2026-06-22 |
| Resolution | Switched to **Trusted Publishing** — added a GitHub OIDC trusted publisher on the PyPI `views-frames` project (Owner `views-platform`, Repo `views-frames`, Workflow `publish_package.yml`), so future releases publish **tokenless** via `publish_package.yml`. Deleted both the account-wide `views-frames-release` token and a transient project-scoped token. **No PyPI API token now exists** — nothing to store or leak. The publishing guide documents the tokenless flow. |

---

> Resolved 2026-06-21 by Epic 5 (leaf completion, v1.0.0, PRs #68–#72).

### C-24: `map_estimate` equivalence test non-portable (red on the numpy floor) — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-24 |
| Resolved | 2026-06-21 (v1.0.0, PR #68) |
| Resolution | Root-caused in production, not the test: the tie-break was `argmax(counts/widths)` (matching `np.histogram(density=True)`), whose float64 bin widths differ by ~1 ulp across numpy versions and flip the argmax on ties — a full-bin divergence (15 failed on 1.26.4). Changed to **integer-counts argmax** (lowest-index), which is bit-identical on every numpy build, so `map_estimate` is deterministic and portable. The centre still differs by ~1 ulp (edges), so the test asserts float32 tolerance. The CI **`floor` job now runs pytest** at `numpy==1.26.4` (was mypy only) — the floor is behaviour-checked. CHANGELOG claim scoped to "float32 precision". See C-19, C-22 (resolved). |

---

### C-25: `hdi`/`quantiles` allocate full-grid temporaries, no scale guard — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-25 |
| Resolved | 2026-06-21 (v1.0.0, PR #69) |
| Resolution | Added a shared `ROW_BLOCK` + `block_apply` helper; `hdi`/`quantiles` now run row-blocked like `map_estimate` (peak memory bounded by one block, not the full grid). All three estimators take a `block_rows` kwarg. A `tracemalloc` guard covers `hdi` and `quantiles` at 1e6 rows. Output unchanged. |

---

### C-26: `cross_level_align` dict mapping is O(N) caller allocation at grid scale — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-26 |
| Resolved | 2026-06-21 (v1.0.0, PR #71) |
| Resolution | Benchmark (5M cells) confirmed the dict dominates: ~30× slower, ~10× the memory of the columnar form. Added `cross_level_align_arrays(map_keys, map_vals, …)` + `aggregate_distributions_arrays`, sharing one remap/aggregate path with the dict entries, so a producer holding a grid-scale mapping stays vectorized end-to-end. The `dict` form remains the ergonomic small-mapping path. See C-20 (resolved). |

---

### C-27: conformance floor stale + bump policy unstated — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-27 |
| Resolved | 2026-06-21 (v1.0.0, PR #72) |
| Resolution | At the v1.0 freeze, `CONFORMANCE_FLOOR = "1.0.0"`; GOVERNANCE now states the floor tracks the **whole published conformance surface** (frame contract + laws) and bumps on any breaking change to it (additive surface is MINOR, no bump). ADR-018 records the freeze. See C-10. |

---

> Resolved 2026-06-21 by Epic 4 (hardening, v0.3.0, PRs #63–#65 + register #51).

### C-19: `mypy --strict` not enforced at the numpy floor — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-19 |
| Resolved | 2026-06-21 (v0.3.0, PR #63) |
| Resolution | Added `src/views_frames/_typing.py` (`IntArray = NDArray[np.integer[Any]]`) and parameterized the 14 bare `NDArray[np.integer]` sites. A CI `type-floor` job pins `numpy==1.26.4`; `mypy --strict` is green at the floor (was 14 `[type-arg]` errors). |

---

### C-20: `cross_level_align` mapping static vs ADR-014 time-varying — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-20 |
| Resolved | 2026-06-21 (v0.3.0, PR #64) |
| Resolution | `cross_level_align`/`aggregate_distributions` now take `Mapping[tuple[int, int], int]` keyed by `(time, unit)`; the remap is vectorized (void-viewed keys + `searchsorted`) and fails loud on the old unit-only shape or a missing key. Published `assert_cross_level_alignment_law` + a time-varying test (one cell, two months → two countries). ADR-014 was already correct; the code matched it. See C-15. |

---

### C-21: `(time, unit)` row-uniqueness stance undocumented — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-21 |
| Resolved | 2026-06-21 (v0.3.0, PR #65) |
| Resolution | Documented the stance on `SpatioTemporalIndex` (duplicates allowed — `cross_level_align` makes them; same-level joins assume uniqueness) + added `has_unique_rows()` for consumers that need the guarantee. No construction-time behaviour change. **2026-07-27 (ADR-026, v1.10.0):** the stance now also covers `reindex_fill` (assumes unique rows in *self*; duplicate target rows allowed) and is *enforced* at the one place a duplicate is always a caller bug — `cartesian` raises on duplicated input values. See C-71. |

---

### C-22: per-row Python loops on the report-stage reduction path — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-22 |
| Resolved | 2026-06-21 (v0.3.0, PRs #64, #65) |
| Resolution | `cross_level_align` (PR #64) and `map_estimate`/`hdi` (PR #65) are vectorized — no per-row Python loop. `map_estimate` uses a row-blocked batched histogram (peak memory `O(block × bins)`, bit-for-bit identical to v0.2.0 incl. the `density=True` tie-break). A `tracemalloc` scale guard at 1e6 rows asserts memory does not scale with `rows × bins`. |

---

### C-23: missing `py.typed` + doc↔code drift — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-23 |
| Resolved | 2026-06-21 (v0.3.0, PR #63) |
| Resolution | `py.typed` shipped in both packages (verified in the wheel); `index` added to the `SpatioTemporalIndexed` protocol (README §5 was already claiming it); README header → v0.3.0, dropped the nonexistent `align` (§4.3), fixed the `collapse` glossary (§13a.2/§14). |

---

> Resolved 2026-06-21 by the v0.1.0 implementation (Epic 2, PRs #31–#35).

### C-07: copy-vs-view semantics unspecified vs the scaling thesis — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-07 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | Frames are immutable; `with_metadata` returns a new frame **sharing** the `values` buffer (`np.shares_memory`), and only `collapse` allocates — the reduced array. `mmap` propagates via `io/npz`. Pinned in `tests/test_properties.py` + the conformance suite. |

---

### C-09: save/load sidecar asymmetry couples `io/` to per-frame schema — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-09 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `io/npz` operates on a generic frame **state dict** (values + identifiers + a JSON header carrying `feature_names`/`metadata`); the I/O layer carries no per-frame schema. `io/arrow` follows the same state contract. |

---

### C-11: the leaf guarantees structural, not temporal, validity — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-11 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `_validation` enforces integer dtype / length-N / completeness only; `time` is an opaque integer (no epoch/range/monotonicity check). Documented in the module + the `SpatioTemporalIndex` CIC. |

---

### C-14: cross-level cm↔pgm alignment needs domain data the leaf forbids — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-14 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `SpatioTemporalIndex.cross_level_align(mapping, target_level)` requires a **consumer-injected** mapping and raises without one; the leaf embeds/fetches no mapping (asserted in tests). Same-level alignment stays pure-numpy. |

---

### C-17: "move `PredictionFrame` verbatim" imports pandas into the numpy-only core — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-17 |
| Resolved | 2026-06-21 (v0.1.0) |
| Resolution | `PredictionFrame` was relocated with numpy-only validation (the integer-dtype check replaces `pd.isna`); no pandas import. Guarded by `tests/test_import_enforcement.py`. |

---

---

## Register Conventions

- **ID format:** `C-xx` for concerns, `D-xx` for disagreements. IDs are permanent — gaps in numbering indicate merged or resolved entries.
- **Skipped ids:** **C-04** was merged into C-18 (the "SpatialLevel slippery slope"). **C-30** is intentionally skipped — it is *pipeline-core's* external id for the cross-repo contract-test gap (referenced in ADR-005 / ADR-016), not a views-frames concern. **C-48** is intentionally skipped — it is *views-reporting's* external id for the run-identity concern (referenced in D-02 / ADR-020), not a views-frames concern.
- **Foreign ids (collisions, not skips):** unlike the skipped ids above, **C-65** exists in *both* registers — pipeline-core's C-65 is the reversed entity-first tuple (cited in **C-18**), while *this* register's C-65 is the non-finite fail-loud blocked-path gap (resolved 2026-06-28). Any cross-register id must name its repo; an unqualified `C-xx` always means this register.
- **Causal clusters** (assigned by `review-rr`, last reviewed **2026-07-31**). This list is the **single authority** on clustering — the Open-section preamble points here and must not restate it:
  - **the freeze as a root cause** (meta-cluster, spanning the others) = {C-43, C-57, C-66, the C-32 residual, + resolved C-53, C-76, D-09, D-11} — **the price ledger for ADR-018.** These entries are not open because anyone failed to fix them; they are open because the freeze converts otherwise-fixable defects into permanent items: C-43 cannot dedupe the binning (`point.py` frozen + C-24 ulp-sensitive), C-53 will have two frozen construction paths forever once the second lands, C-57 cannot give `map_estimate` a clean non-finite error, C-66's one-line `setflags` enforce is a MAJOR, and `map_estimate`'s bias (C-32) is mitigated *alongside* rather than fixed. D-09 and D-11 were both **settled by** the same constraint ("anything removable must not touch the frozen surface"). The freeze is working as designed; this cluster is what it costs. **Actionable consequence:** when a MAJOR is opened for *any* reason, this cluster is the rider shopping list — C-66 already records the exact one-line-per-constructor change and its red test, C-57 the `np.isfinite` guard, C-43 the shared-binning extraction. Plan them together or the MAJOR is wasted.
  - **scale & footprint awareness** = {C-71, C-73, + resolved C-25, C-26, C-22} — the leaf ships primitives whose cost is *inherently* grid-scale allocation, and ADR-026 ratified the stance: **document the cost, never guess a size guard** (a guard would be consumer policy). C-71 (dense fill / `cartesian`) and C-73 (`arrow.load` whole-table read) are that one decision applied twice; both fail **loud** (`MemoryError`/OOM), never silently. The resolved trio is the deliberate **counter**-precedent — on the *estimator* side the leaf **did** bound memory (block-wise reduction, C-22/C-25; O(N) caller allocation removed, C-26). The tension is intentional and worth keeping visible: bounded by design where the output is a *reduction*, unbounded by design where the output *is* the allocation.
  - **summarize-estimator coherence (#89)** = {C-32, C-34, C-43, C-57, + resolved C-33} — point/interval/mode estimation over zero-inflated, heavy-tailed, potentially-multimodal conflict posteriors is mathematically under-determined; a single number can mislead, and the frozen `map_estimate` additionally carries an obscure inf-error (C-57) and a per-row binning duplication with `bimodality` (C-43). The register's live estimator work; tracked in #89.
  - **reconcile method + governance** = {C-62, + D-12; resolved C-58, C-64, C-37-lineage} — the per-draw `proportional` reconciler is a pragmatic, information-losing port (C-62) whose principled joint upgrade is deferred (ADR-024); its cutover-verification residual (C-58) **closed 2026-07-31** once the production-slice check existed as a one-command tool *and* the runbook required it — leaving C-62, the method limitation itself, as the only open member. The mode-reporting decision is recorded as D-12. The package's **missing CIC** (C-64) was the other half of the governance debt — closed by `docs/CICs/Reconcile.md` (epic #179 / S1).
  - **construction-convenience accretion (#113)** = {resolved C-52, C-53, C-54, + D-09} — **CLOSED 2026-07-31 by ADR-027** (Epic #208 / S1 #209). The planned `PredictionFrame.from_arrays` factory was the "camel's nose" for leaf bloat: accretion (C-52), two frozen construction paths diverging (C-53), a DoD overstating scope (C-54) — all three guarding an addition that was **never made and is now declined**. The cluster is instructive rather than dead: it is the register's clearest case of concerns that existed *only* because a proposal sat undecided. Thirteen months open, zero code written, three entries consuming review attention every cycle — and the resolution was a decision, not an implementation. **The guard survives as a written precedent:** ADR-027 records the binding constraints any future construction convenience must satisfy and what would reopen the question, so the next such request is closed by citation instead of re-argued. The lesson generalises to the `awaiting` Status class: an undecided proposal is not free.
  - **cross-repo coordination** = {C-13, C-46, D-04, D-05, D-06} — an N-consumer leaf whose buy-in is *assumed, not elicited*: the concentration/fan-out risk (C-13), the envelope re-assertion in views-evaluation (C-46), plus the unratified-perspective disagreements. Resolvable only across repos, not within the leaf.
  - **immutability enforcement** = {C-66, + resolved C-63, C-07} — the **contract-correction** half is done (**C-63 resolved** by ADR-025, 2026-06-28, epic #179 / S2): immutability is enforced for the *index* (`setflags(write=False)`) and held *by convention* for the *value buffer* (writeable on purpose, to preserve zero-copy / `mmap`; mutating `.values` is documented-unsupported across the three frame CICs + README design principle 3). The **enforcement** half — `setflags(write=False)` on `.values` — is a MAJOR ("tightening an invariant", GOVERNANCE/ADR-018) and is **deferred, tracked open as C-66** (the enforce-rider for the next MAJOR), so the residual writeable-buffer exposure stays visible rather than buried in the resolved C-63.
  - cross-cutting **verification-completeness** = {**C-74**, **C-75**, resolved C-51, C-58, C-65} — **the register's most persistent pattern: a check exists, passes, and does not actually exercise the thing it appears to guard.** The reconciler's production-slice check was never run (C-58 — **closed 2026-07-31**, the tool and the requirement both now exist); `validate_docs.sh` and `ruff format` are treated as gates but are absent from CI (C-74); four falsification tests inside the 100%-coverage gate assert README prose rather than the API (C-75); and the precedent — `assert_frame_envelope`'s rejection paths were "covered" only transitively (C-51, resolved by direct adversarial tests). The recurring lesson is that **coverage-green and gate-green are not the same as verified**, and the failure is always *false confidence*, never a wrong number — which is why this cluster is uniformly Tier 3 yet keeps producing entries. Its sibling — the non-finite fail-loud on the blocked/multi-block path (C-65) — was **resolved by a red test (2026-06-28, epic #179 / S3)** placing a non-finite draw in a non-first block via `block_rows`. Its sibling — the non-finite fail-loud on the blocked/multi-block path (C-65) — was **resolved by a red test (2026-06-28, epic #179 / S3)** placing a non-finite draw in a non-first block via `block_rows`.
  - **post-1.1.0 polish** = {C-35, C-36, C-37, C-38} — **resolved by Epic 7 (2026-06-24)**. Low-severity doc/test-completeness items from the 2026-06-24 repo-assimilation + test-review; closed before the v1.1.0 `main` merge, no `src/` behaviour change.
  - **test-coverage debt** = {C-29, C-31} — **resolved by Epic 6 (2026-06-23)**. Fail-loud / parity paths that existed in code but lacked tests (root cause: the v1.0.0 suite optimized happy-path coverage over failure/parity branches); now closed with a CI 100%-coverage gate.
- **Tier 4 in Open — the scheduled-trigger rule** (adopted 2026-07-31, `review-rr` strategic): a Tier 4 concern earns a place in **Open** only if its trigger is an **event it must ride** — otherwise it is a chore, not a risk, and belongs in an issue. **C-43** (extract the shared binning when `map_estimate` is unfrozen) and **C-76** (decide `from_2d`'s deprecated-but-frozen status at the next MAJOR) both qualify: each is a *decision that must not be rediscovered* at the moment it becomes possible. This rule was written after the register briefly held both a recommendation to demote C-43 for being cosmetic and a fresh registration of C-76 with the same profile — the two are the same case and are now handled the same way.
- **Citing code — name things, never line numbers.** Write `` `path/to/file.py::function_name` ``, never a path followed by a colon and a line number. Where the point of interest is *inside* a function, name the function and describe the part in words ("the `astype(intp)` cast in `point.py::_batched_map`"). **Reason:** this register is the most durable artifact in the repository — permanent IDs, entries never deleted, resolutions kept for years — and a line number is the least durable way to point at code. Any edit above a cited line silently invalidates it, and nothing checks. **This had already happened before the convention was written:** C-63 and C-66 both pointed at `index.py` lines 55 and 56 for the index write-protection, which has actually been at lines **53 and 54** for some time. Nobody noticed, because nothing was looking. Names survive reformatting, reordering and inserted imports; line numbers survive nothing. **Exception:** citations into *other* repositories keep their line numbers (ADR-014 and ADR-026 cite views-reporting and views-faoapi). They are frozen historical evidence about code we do not control and cannot verify from here, so re-anchoring them would be guesswork.
- **Field order:** `ID`, `Tier`, `Status` (open only), `Source`, `Trigger`, `Location`, `Cross-refs`. Resolved entries compress to `ID`, `Resolved`, `Resolution` (some retain `Tier` where the severity is part of the record).
- **Sources:** `repo-assimilation`, `expert-review`, `test-review`, `falsification-audit`, `persona-critique`, `clean-architecture-review`, `pr-review`, `tech-debt-audit`, `incident`, `manual`.
- **Resolution:** Move to "Resolved Concerns" with resolution date and summary when addressed.
- **Header counts:** Manually maintained — update whenever a concern is added or resolved.
- **Note:** Future concerns will often reference locations in external repos (`views-pipeline-core`, `views-datafactory`, `views-faoapi`, `views-reporting`) because this leaf de-duplicates a data contract not yet relocated. Confirm those locations when the package is stood up.
- **Governed by:** ADR-010 (`docs/ADRs/010_technical_risk_register.md`).
- **Note (v0.2.0, ADR-017):** sample-axis reduction (`collapse`/MAP/HDI/quantiles) was
  removed from the leaf into the `views_frames_summarize` sibling package, eliminating
  the statistics-menu scope leak; the leaf is now a pure data contract.
