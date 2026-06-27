# Technical Risk Register

| Register Info     | Details                              |
|-------------------|--------------------------------------|
| Project           | views-frames                         |
| Owner             | VIEWS platform maintainers           |
| Last Updated      | 2026-06-27                           |
| Total Concerns    | 59                                   |
| Open Concerns     | 11                                   |
| Resolved Concerns | 48                                   |
| Disagreements     | 12                                   |

---

## Tier Definitions

| Tier | Severity | Description |
|------|----------|-------------|
| 1 | Critical | Silent data corruption or output correctness risk. Requires immediate attention. |
| 2 | High | Structural fragility that will cause failures under realistic change scenarios. |
| 3 | Medium | Maintainability or coupling issues that increase cost of change. |
| 4 | Low | Code quality concerns that do not affect correctness or reliability. |

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
> The **3 currently open** items fall into two live clusters (detailed under *Causal
> clusters* in Register Conventions): **(1) summarize-estimator coherence (#89)** — **C-32**
> (`map_estimate` mode bias) and **C-34** (`bimodality` recall); their tower-nesting sibling
> **C-33** was **resolved** by ADR-019 (2026-06-23). **(2) cross-repo coordination** — the
> inherent **concentration risk** **C-13** (accepted / monitored), with disagreements
> D-04/D-05/D-06. The **post-1.1.0 polish** cluster {C-35, C-36, C-37, C-38} was **closed by
> Epic 7** (2026-06-24, now in Resolved Concerns), as were the 2026-06-22 test-review gaps
> {C-29, C-31} by **Epic 6**.

### C-13: concentration risk — single point of coordination failure (accepted / monitored)

| Field | Value |
|-------|-------|
| ID | C-13 |
| Tier | 2 |
| Source | expert-review (2026-06-20) |
| Trigger | A future MAJOR bump to the frozen contract fans out across every consumer at once — when planning one, drive it through the GOVERNANCE coordinated-bump process rather than letting consumers desync. |
| Location | `README.md` §12 (~12 register items, 3+ repos); `GOVERNANCE.md` (coordinated-bump process) |

The leaf's breadth is both its value and an inherent concentration risk (critique_01 §3.7): it is structurally the single point every consumer pins. **Mitigation shipped** — a minimal, stable, **frozen v1.0.0** (ADR-018) gives consumers a contract that will not churn, and ADR-016 / GOVERNANCE name the owner and the coordinated MAJOR-bump process (C-05, C-10 resolved). **Residual is accepted and monitored:** the fan-out cost of any future MAJOR is irreducible; the control is the GOVERNANCE process, watched as consumers adopt. See also D-06.

---

### C-32: `map_estimate` lowest-index tie-break biases the mode toward zero

| Field | Value |
|-------|-------|
| ID | C-32 |
| Tier | 2 |
| Source | views-faoapi integration spike (2026-06-23) |
| Trigger | When a consumer adopts `views_frames_summarize.map_estimate` as a drop-in for an existing histogram-MAP (e.g. faoapi's `PosteriorDistributionAnalyzer`), check the tie-break on its real posteriors — on right-skewed, zero-inflated, low-sample (~32-draw) distributions the lowest-index tie-break systematically pulls the mode toward the left tail (zero), shifting published modes downward. |
| Location | `src/views_frames_summarize/point.py:110` (`np.argmax(counts, axis=1)` — lowest-index tie-break). Evidence: a views-faoapi integration spike (2026-06-23). |

**Symptom.** At 32 draws in 100 bins the histogram peak is almost always a multi-way tie; `np.argmax` takes the lowest index = leftmost = smallest value, so for a right-skewed, zero-inflated posterior the MAP is dragged toward zero. The faoapi spike measured this against the production estimator: **~21% of active cells diverge one-directionally (NEW MAP ≤ OLD MAP always), up to 7.9 in ln-space** (≈2,700× in count-space). This is the **C-24** portability fix's blind side — C-24 removed the numpy-version *instability* of the `density = count/width` tie-break, but the lowest-index choice it landed on carries a *directional bias* C-24 never weighed.

**The real problem is deeper than the tie-break.** The mode is the only one of our point/interval estimates that is a functional of the *density* rather than the *CDF*. Mean is an average; quantiles/HDI are order statistics — both need only the samples ranked, which is **why the spike found HDI bit-identical**. The mode needs an *estimated density* and its argmax, and density estimation is inherently **regularized** — there is no assumption-free, tuning-free density estimate. What we ship is the degenerate corner: a **nonparametric mode with a fixed (non-adaptive) bandwidth (100 bins) and an arbitrary tie-break** — neither parametric nor consistently nonparametric, so it is both **biased *and* non-convergent**. A fixed bin count *cannot* converge to the true mode no matter how many samples are added (consistency needs the bandwidth to shrink with `n` at a controlled rate). A principled MAP therefore requires **one of**: (a) an explicit distributional assumption (fit a family → analytic mode; stable at low `n`, at the cost of model risk), or (b) an **`n`-adaptive smoothing rule *plus* a sufficient-`n` floor** (a sample-count floor alone is necessary, not sufficient). The tie-break is merely **where the under-determination surfaces**; "fix the tie-break" reduces the directional bias but does not make the estimator converge — a band-aid, not a cure.

Note the estimator is **already semi-parametric**: the `zero_mass_threshold` rule (≥30% mass at ~0 ⇒ MAP = 0) is a zero-inflation model. The under-determined part is specifically the **continuous-body mode**, which is why the bias bites hardest on the *partially* zero-inflated active cells (`mass0 ≈ 0.06`).

**Latent today** (the leaf publishes nothing — hence Tier 2, not 1), but it is **silent, directional output incorrectness for any consumer that adopts it expecting parity**. Resolution path: estimator-design effort tracked in **#89** (a distributional assumption *or* `n`-adaptive smoothing + floor; **not** merely a better tie-break; SemVer decision required). See C-24 (resolved), C-25, C-33.

**Mitigation shipped (2026-06-23, ADR-019; redesigned 2026-06-24, C-44) — not a full resolution; stays open.** `tower_point` ships as an **unbinned, median-based** point estimator (the median of the configurable **`tip_mass`** floor, default 0.5 — the shorth), so it carries **none** of the lowest-index histogram tie-break's directional bias, and — reading a *mass-aware* floor rather than the degenerate 2-sample 5% floor — it is now also **robust to minority duplicated draws** (C-44). Scored against a *non-circular analytic-mode* oracle (the active families only — zero-mode families have no analytic continuous mode), it ties/beats `map_estimate` on clean active cells **at the production sample size n=1024**; at **n=128 the two are mixed** (the tip wins on some families, loses on others — see `research/map_hdi/point_pass.py`), so this is a mitigation at production `n`, not a guaranteed win at the low-`n` regime where the bias bites hardest. `bimodality` flags the multimodal cells where any single mode is ill-defined (with its own recall caveat — see C-34). **Residual:** `map_estimate` itself is unchanged (frozen, ADR-018) — a naïve adopter can still step on it (now with a documented better path, `tower_point`); and `tower_point` uses a **fixed** `tip_mass` (50%) floor, so it is **not** the consistency-guaranteed convergent mode this entry calls for. That remains **#89**.

---

### C-34: `bimodality` is conservative by design — limited recall on ambiguous / unequal multimodal posteriors

| Field | Value |
|-------|-------|
| ID | C-34 |
| Tier | 3 |
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
| Source | expert-code-review (2026-06-24, GH #109; Kleppmann/Feathers/Nygard lenses) |
| Trigger | When `views-evaluation` implements `MetricFrame` on the views-frames substrate (Option B, ADR-020), or when the leaf changes its serialisation/round-trip or float32 discipline (`io/`, `_validation.py`) — at that point the envelope invariants (float32 values, round-trip identity, optional-only metadata) exist in two places with no shared check. Re-run a cross-boundary round-trip contract test that calls the leaf's published conformance checker. |
| Location | Leaf side: `src/views_frames/conformance/__init__.py` (`assert_frame_envelope` / `assert_frame_contract`), `src/views_frames/io/`, `src/views_frames/metadata.py`. Boundary: the (to-be) `MetricFrame` in `views-evaluation`. |
| Cross-refs | C-01 (resolved — the home decision: leaf defines only the index/key protocol the eval types conform to), ADR-016 (conformance floor), ADR-020 (the B ratification), GH #109, views-evaluation#21. |

Under Option B (the ratified boundary; C-01), `MetricFrame` lives in `views-evaluation` and reuses the views-frames *substrate* — `FrameMetadata` plus the conformance/IO **patterns**. The float32 discipline and the serialise→load round-trip are therefore guaranteed in the leaf (`assert_frame_contract`) but only **re-asserted by convention** in `views-evaluation`. There is no single schema authority for the shared "frame-like envelope" across the two repos, so the two can drift — a quiet deserialisation or precision mismatch discovered late at the emit→consume boundary, not an outage. **Tier 2** — structural fragility with a clear future trigger; the leaf publishes nothing itself, but the boundary it underwrites can silently mismatch. **Mitigation (recorded in ADR-020):** publish the leaf's conformance/round-trip checks as a reusable, consumer-runnable checker (the conformance suite is already a public artifact, ADR-016) plus an explicit, versioned wire schema (a `schema_version` marker) that both emit and consume validate against — converting "agree by convention" into "validate against one written contract." **Partially mitigated (v1.4.0):** the reusable checker shipped as `assert_frame_envelope` — the shared envelope (float32, trailing axis, round-trip) factored out as one written authority a non-spatiotemporal `MetricFrame` validates against. **Remaining (stays Open):** the explicit versioned wire schema (`schema_version`) and the cross-repo emit→consume round-trip contract test that calls the checker — both live at the boundary / in `views-evaluation`. Resolved when those land.

---

### C-52: construction-convenience accretion on the leaf — the "camel's nose" for adapters (ADR-001)

| Field | Value |
|-------|-------|
| ID | C-52 |
| Tier | 3 |
| Source | expert-code-review (2026-06-24, GH #113 `build_prediction_frame` / `PredictionFrame.from_arrays`); pipeline-core owner calibration |
| Trigger | When a future PR extends the planned `PredictionFrame.from_arrays` with a `value_fn` / `from_grid` / dtype-guessing parameter, or adds a new `src/views_frames/factory.py` that accretes loosely-related construction helpers — **or adds frame-level serialization/adapter conveniences (`to_parquet`/`from_parquet`, and especially `to_pddf`/`from_pddf`) to the frame classes** — pulling consumer-edge responsibility (ADR-001 non-entities: adapters, "convenience abstractions") into the data-contract leaf. |
| Location | (planned) `src/views_frames/prediction_frame.py` (`from_arrays`); guard against a future `src/views_frames/factory.py` and against `to_parquet`/`to_pddf`/`from_pddf` accreting onto `src/views_frames/*_frame.py`. |
| Cross-refs | ADR-001 (ontology / explicit non-entities / accretion = the leaf's #1 failure mode), ADR-011, D-09, **D-11** (serialization-convenience placement — settled off-leaf), C-53, C-54, GH #113. |

ADR-001 (line 17) names accretion as the leaf's existential failure mode — "someone adds an adapter, then grid knowledge … becomes pipeline-core-lite." A construction convenience is the most innocuous possible first step onto that slope. **Tier 3** (recalibrated down from an initial Tier 2 with the pipeline-core owner): under the ratified mitigations the residual risk is boundary-erosion a code-review gate catches, not inherent structural fragility. **Mitigations:** ship the **classmethod** form (a class resists becoming a dumping ground far better than an open `factory.py`); keep it **zero-own-logic**; add a CIC "Construction" **non-goal** that explicitly fences out grid / `value_fn` / inference / adapters. Resolved when `from_arrays` lands with those guards, or closed if #113 is declined.

---

### C-53: two frozen `PredictionFrame` construction paths can diverge

| Field | Value |
|-------|-------|
| ID | C-53 |
| Tier | 3 |
| Source | expert-code-review (2026-06-24, GH #113; Kleppmann lens) |
| Trigger | When a future **additive identifier** (an optional third id beyond `{time, unit}`, ADR-013) is threaded through `PredictionFrame.__init__` / `SpatioTemporalIndex` but **not** through `PredictionFrame.from_arrays` (or vice-versa) — the two **frozen** (ADR-018) construction signatures then drift, and a consumer on one path silently cannot express what the other can. |
| Location | (planned) `src/views_frames/prediction_frame.py` (`__init__` + `from_arrays`). |
| Cross-refs | ADR-013 (optional-additive identifiers), ADR-018 (freeze — both paths are forever), D-09, C-52, GH #113. |

Adding `from_arrays` publishes a **second** construction path that ADR-018 then freezes alongside `__init__`; both must evolve together forever. **Tier 3** — maintainability/coupling, not silent corruption. **Mitigation:** `from_arrays` must carry **zero own logic** — pure delegation to `SpatioTemporalIndex(time, unit, level)` + `__init__(values, index, metadata)` — so a new index identifier flows through `from_arrays` automatically with no signature edit. Resolved when `from_arrays` lands as a zero-logic delegator, or closed if #113 is declined.

---

### C-54: #113 DoD overstates scope — "retires the baseline duplicate" would pull a consumer edge into the leaf

| Field | Value |
|-------|-------|
| ID | C-54 |
| Tier | 3 |
| Source | expert-code-review (2026-06-24, GH #113; cross-repo / views-baseline) |
| Trigger | When a maintainer reads #113's Definition-of-Done literally ("retires baseline's local `build_prediction_frame`") and moves views-baseline's `value_fn` + entity×time grid loop into the leaf to "finish the job" — importing a domain grid-builder (an ADR-001 non-entity / consumer edge) into the data-contract leaf. |
| Location | views-baseline `views_baseline/model/helpers.py:110` ↔ the leaf. |
| Cross-refs | ADR-001 (adapters / grid-builders are consumer edges, not leaf entities), C-52, GH #113, views-baseline #21. |

The views-baseline helper is a **domain grid-builder** (loops a `value_fn` over entity×time to emit `dict[str, PredictionFrame]`), not a thin constructor; the planned `from_arrays` retires only its **innermost** `SpatioTemporalIndex + PredictionFrame` construction line, leaving the grid loop in the engine where it belongs. **Tier 3** — boundary/scope erosion, multi-repo. **Mitigation:** re-scope #113's DoD to "retire the index-construction *line* inside the baseline helper," and keep the helper in views-baseline. Resolved when #113's DoD is corrected.

---

### C-57: `map_estimate` raises an obscure `IndexError` (not a clean error) on ±inf draws

| Field | Value |
|-------|-------|
| ID | C-57 |
| Tier | 3 |
| Source | falsify audit (2026-06-25, P5b — discovered while widening the exceedance/ES guards) |
| Trigger | When a consumer feeds a frame containing an `inf` draw (a valid float32 the leaf does **not** ban — e.g. an upstream model bug) to the frozen `map_estimate`: the histogram span is `inf`, the bin index divides to `nan`, and the `astype(intp)` cast overflows to the int-min sentinel, so `np.take_along_axis` raises `IndexError: index -9223372036854775808 is out of bounds` instead of a clean `ValueError` or a finite result. |
| Location | `src/views_frames_summarize/point.py:89-92` (`_batched_map`). |
| Cross-refs | ADR-018 (frozen v1 surface — behavior is locked), C-50/C-56 (the new estimators now fail loud cleanly on non-finite via `np.isfinite`; `map_estimate` is the frozen sibling that does **not**), ADR-008 (fail-loud posture). |

The frozen surface is **inconsistent** on non-finite draws: `collapse(np.mean)` propagates `inf` (visible), the new `exceedance`/`expected_shortfall` now **fail loud** on it (C-50/C-56), but `map_estimate` **crashes with an obscure `IndexError`** rather than a clean, actionable error. This is **not** silent corruption (it is loud, and `inf` draws are out-of-contract upstream bugs), so it is **not** a publish blocker for v1.6.0 — and `map_estimate`'s behavior is **locked by the ADR-018 freeze**, so it cannot change without an additive hardening pass. **Tier 3** — ungraceful failure on a leaf-permitted input; a future cross-estimator non-finite hardening (a reserved additive MINOR) should give `map_estimate` the same clean `np.isfinite` guard. **Open** — watch-item, no fix shipped in v1.6.0.

---

### C-58: a reconciler cutover verified against the oracle but not a live production slice

| Field | Value |
|-------|-------|
| ID | C-58 |
| Tier | 3 |
| Source | expert-code-review (2026-06-26, #138 cutover review) + the Epic 11 cutover closeout |
| Trigger | When a future reconciliation cutover repoints a consumer to a new reconciler relying only on the in-repo evidence — the frozen torch-oracle fixtures + the synthetic new-vs-old head-to-head — and **skips a comparison against an actual served production slice** at the repoint. If the in-repo oracle and the live served path have drifted (e.g. an upstream input or mapping change not reflected in the fixtures), the re-baseline of served numbers goes unverified. |
| Location | The cutover gates (runbook `docs/guides/reconciliation_migration_and_cutover_runbook.md`, Phase 2); mitigation tool `scripts/verify_reconcile_parity.py` (`--compare`). |
| Cross-refs | ADR-023, Epic 11 `#138`, the cutover postmortem (`reports/postmortems/2026-06_reconciliation_cutover_epic11.md`), views-models #191, views-postprocessing #62. |

The Epic 11 cutover was validated by a sound transitive chain — `new == old vpp copy` (136-case bit-identity) and `old vpp == views-reporting torch oracle` (frozen `.npz`), so `new == torch oracle` — but **no comparison was run against an actual served production parquet** (old path vs new path) at the repoint. The residual risk is low (the oracle *is* the torch path's captured output), so this is **not** silent corruption — it is a missing belt on a sound buckle. **Mitigation shipped:** `verify_reconcile_parity.py --compare OLD.parquet NEW.parquet` makes the production-slice check a one-command gate, and the cutover runbook (Phase 2) now requires it for future cutovers. **Tier 3** — a verification-completeness gap, not a known defect. **Open** — watch-item for the next reconciler change. (The expert review's companion "batched-deploy blast radius" concern did **not** materialize: the Epic 11 cutover landed as phased PRs — repoint #202, then delete #63 — so no separate entry is warranted.)

---

### C-59: the summaries notebook teaches named intervals with no calibration / coverage demonstration

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

### C-60: the reconciliation notebook risks presenting bit-identity as method validation

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

### C-61: the notebooks have no spatial / map view despite showcasing spatial forecasts

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

### C-62: `reconcile_proportional` is an information-losing per-draw approximation (no joint-calibration guarantee)

| Field | Value |
|-------|-------|
| ID | C-62 |
| Tier | 3 |
| Source | expert-method-review lineage + S3 design (#145), 2026-06-27 |
| Trigger | When a consumer's decision provably needs **calibrated joint** country tails that proportional's per-draw marginal rescale cannot provide, **or** when the country model (views-models) gains a shared draw-identity / coupling that makes principled joint reconciliation buildable — i.e. when ADR-024's two deferral preconditions are met, build the principled sibling module (never by modifying `proportional`). |
| Location | `src/views_frames_reconcile/proportional.py` (the per-draw method); designed in `docs/ADRs/024_principled_joint_reconciliation_design.md`. |
| Cross-refs | ADR-024 (the design + deferral), ADR-023 (sibling charter; future-sibling-module open question), views-postprocessing C-37 (the cross-repo principled-reconciliation lineage), views-pipeline-core C-198 / C-200b (consumer-side), C-60 (the notebook presentation of this — resolved), D-12 (mode reporting). GH #145 / #142. |

`reconcile_proportional` rescales grid cells to sum, **per draw**, to the country total — pairing grid-draw `s` with country-draw `s`. When the grid and country models are trained **independently** (the current platform reality), draw index `s` has **no shared identity** across them, so the pairing is arbitrary and the reconciled **joint** distribution (the joint country tails an FAO-style worst-case keys on) is not guaranteed calibrated — even though conservation (sum-to-country per draw, zeros preserved, non-negative) holds **exactly**. This is **not silent** (hence **Tier 3**, not Tier 1): it is documented at every layer — the `proportional.py` docstring, ADR-024, the `03_reconciliation.ipynb` bit-identity-≠-method-quality panel (C-60), and surfaced at runtime as the `reconcile_result` mode `aligned-draws` (D-12). It is a **known method-quality limitation with a designed upgrade path** (ADR-024), deliberately deferred until its preconditions hold. **Open** — the limitation persists until the principled sibling module is built.

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
| Resolution | Unresolved — **and now load-bearing.** The simulated perspectives have been *acted upon*: five consumer-adoption issue sets were filed in real repos (datafactory #219–221, pipeline-core #186–190, reporting #137–140, postprocessing #27–29, faoapi #87–91). Those issues are **proposals derived from the simulated perspectives, not consumer buy-in** — treat each repo's adoption as unconfirmed until that team responds. Only `from_views-datafactory` is ratified. Add a "Ratified by: <name/date>" header to each perspective; do not count unratified perspectives (or the issues filed from them) as agreement. See D-05. |

---

### D-05: missing views-evaluation and model-repo perspectives

| Field | Value |
|-------|-------|
| ID | D-05 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §5b ("views-evaluation owns `EvaluationFrame`/would produce `MetricFrame`; a model repo produces `PredictionFrame` — both absent, and they would stress the riskiest claims"), Scope ("write them before promoting `MetricFrame` from exploratory") |
| Resolution | Unresolved — write the views-evaluation + a model-repo perspective before any `MetricFrame` work. See C-01. |

---

### D-06: portfolio / WIP sequencing across three concurrent cross-repo initiatives

| Field | Value |
|-------|-------|
| ID | D-06 |
| Source | expert-review (2026-06-20) |
| Perspectives | Critique_01 §6 ("viewser→datafactory migration, views-appwrite extraction, and views-frames relocation compete for the same coordination budget and destroy change attribution if run concurrently"), Leverage ("views-frames is highest-leverage but also the largest coordination load") |
| Resolution | Unresolved — WIP limit: do not run views-frames relocation and views-appwrite extraction in the same repo concurrently; queue consumer adoption behind the data-migration baseline. See C-13. |

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
| Resolution | **Settled — Option B:** classmethod `PredictionFrame.from_arrays`, **singular** (PredictionFrame only; defer Feature/Target per CRP + ADR-011 honesty-over-symmetry), **zero own logic**, keyword-only `time`/`unit`/`level`, in `prediction_frame.py`, **no alias**. Additive/MINOR; `CONFORMANCE_FLOOR` stays `1.0.0`. **Implementation deprioritized behind the engine migration** (views-hydranet #137 / views-baseline #21) — it is not a blocker. See C-52, C-53, C-54, ADR-011, ADR-018, GH #113. |

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
| Resolution | Both `nit`-severity ultrareview findings fixed; no shipped-package behaviour change. (a) Reworded the `_pin` docstring (`tower.py`) — was "the fixed grid produces no exact distance ties" (false; e.g. `0.075` is equidistant from `0.05`/`0.10`), now "`argmin` breaks ties on the lowest index, so a midpoint mass pins **down** to the lower floor" — matching the tested invariant `test_beige_pinning_is_deterministic_on_ties`. (b) Fixed `research/map_hdi/audit.py:79` stale 3-tuple unpack → `obs, _ref, _modes, meta = battery.load()` to match the 4-tuple `battery.load()` returns (and the four sibling scripts). ruff + 100% coverage green. See C-39 (the earlier doc↔code drift cluster). |

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
| Resolution | Added `tests/test_frame_parity.py` — a builder fixture parametrizing the shared frame surface (`reindex`/`select`/`with_metadata`/`save`-`load`) over **all three** frame types, filling the Feature/TargetFrame `reindex` gap (`feature_frame.py:150-155`, `target_frame.py:109-114`) and locking parity so a future twin divergence fails CI. The construction red-gaps + green laws/getters the same test-review flagged were closed alongside (Epic 6 I3/I4); leaf + summarize are now at **100%** coverage. See C-16 (twins are separate siblings), ADR-005. |

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

### C-18: relocating `SpatialLevel` ports C-65 + a gid/id inconsistency — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-18 |
| Resolved | 2026-06-22 |
| Resolution | ADR-015 (fix-don't-port) — the leaf's `spatial_level.py` ships the time-first index and a consistent identifier vocabulary; the reversed (entity-first) tuple (C-65) and the `priogrid_gid`/`priogrid_id` inconsistency were fixed, not ported. (Subsumes the original C-04 "SpatialLevel slippery slope".) |

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
| Resolution | Documented the stance on `SpatioTemporalIndex` (duplicates allowed — `cross_level_align` makes them; same-level joins assume uniqueness) + added `has_unique_rows()` for consumers that need the guarantee. No construction-time behaviour change. |

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
- **Causal clusters** (assigned by `review-rr`, last reviewed 2026-06-24):
  - **summarize-estimator coherence (#89)** = {C-32, C-34, + resolved C-33} — point/interval estimation over zero-inflated, heavy-tailed, potentially-multimodal conflict posteriors is mathematically under-determined; a single number can mislead. The register's live work; tracked in #89.
  - **cross-repo coordination** = {C-13, D-04, D-05, D-06} — an N-consumer leaf whose consumer buy-in is *assumed, not elicited*; the concentration/fan-out risk plus the unratified-perspective disagreements. Resolvable only across repos, not within the leaf.
  - **post-1.1.0 polish** = {C-35, C-36, C-37, C-38} — **resolved by Epic 7 (2026-06-24)**. Low-severity doc/test-completeness items from the 2026-06-24 repo-assimilation + test-review; closed before the v1.1.0 `main` merge, no `src/` behaviour change.
  - **test-coverage debt** = {C-29, C-31} — **resolved by Epic 6 (2026-06-23)**. Fail-loud / parity paths that existed in code but lacked tests (root cause: the v1.0.0 suite optimized happy-path coverage over failure/parity branches); now closed with a CI 100%-coverage gate.
- **Sources:** `repo-assimilation`, `expert-review`, `test-review`, `falsification-audit`, `persona-critique`, `clean-architecture-review`, `pr-review`, `tech-debt-audit`, `incident`, `manual`.
- **Resolution:** Move to "Resolved Concerns" with resolution date and summary when addressed.
- **Header counts:** Manually maintained — update whenever a concern is added or resolved.
- **Note:** Future concerns will often reference locations in external repos (`views-pipeline-core`, `views-datafactory`, `views-faoapi`, `views-reporting`) because this leaf de-duplicates a data contract not yet relocated. Confirm those locations when the package is stood up.
- **Governed by:** ADR-010 (`docs/ADRs/010_technical_risk_register.md`).
- **Note (v0.2.0, ADR-017):** sample-axis reduction (`collapse`/MAP/HDI/quantiles) was
  removed from the leaf into the `views_frames_summarize` sibling package, eliminating
  the statistics-menu scope leak; the leaf is now a pure data contract.
