# Technical Risk Register

| Register Info     | Details                              |
|-------------------|--------------------------------------|
| Project           | views-frames                         |
| Owner             | VIEWS platform maintainers           |
| Last Updated      | 2026-06-22                           |
| Total Concerns    | 31                                   |
| Open Concerns     | 3                                    |
| Resolved Concerns | 28                                   |
| Disagreements     | 6                                    |

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
> The genuinely open items below are the inherent **concentration risk** (C-13, accepted /
> monitored) and two summarize-estimator-coherence concerns from the views-faoapi integration
> spike (2026-06-23): **C-32** (`map_estimate` tie-break bias) and **C-33** (`hdi` has no
> nesting/tower guarantee) — both tracked together in #89. The 2026-06-22 test-review's gaps
> (C-29, C-31) were closed by **Epic 6** and are now in **Resolved Concerns**.

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
| Location | `src/views_frames_summarize/point.py:100` (`np.argmax(counts)` — lowest-index tie-break). Evidence: a views-faoapi integration spike (2026-06-23). |

**Symptom.** At 32 draws in 100 bins the histogram peak is almost always a multi-way tie; `np.argmax` takes the lowest index = leftmost = smallest value, so for a right-skewed, zero-inflated posterior the MAP is dragged toward zero. The faoapi spike measured this against the production estimator: **~21% of active cells diverge one-directionally (NEW MAP ≤ OLD MAP always), up to 7.9 in ln-space** (≈2,700× in count-space). This is the **C-24** portability fix's blind side — C-24 removed the numpy-version *instability* of the `density = count/width` tie-break, but the lowest-index choice it landed on carries a *directional bias* C-24 never weighed.

**The real problem is deeper than the tie-break.** The mode is the only one of our point/interval estimates that is a functional of the *density* rather than the *CDF*. Mean is an average; quantiles/HDI are order statistics — both need only the samples ranked, which is **why the spike found HDI bit-identical**. The mode needs an *estimated density* and its argmax, and density estimation is inherently **regularized** — there is no assumption-free, tuning-free density estimate. What we ship is the degenerate corner: a **nonparametric mode with a fixed (non-adaptive) bandwidth (100 bins) and an arbitrary tie-break** — neither parametric nor consistently nonparametric, so it is both **biased *and* non-convergent**. A fixed bin count *cannot* converge to the true mode no matter how many samples are added (consistency needs the bandwidth to shrink with `n` at a controlled rate). A principled MAP therefore requires **one of**: (a) an explicit distributional assumption (fit a family → analytic mode; stable at low `n`, at the cost of model risk), or (b) an **`n`-adaptive smoothing rule *plus* a sufficient-`n` floor** (a sample-count floor alone is necessary, not sufficient). The tie-break is merely **where the under-determination surfaces**; "fix the tie-break" reduces the directional bias but does not make the estimator converge — a band-aid, not a cure.

Note the estimator is **already semi-parametric**: the `zero_mass_threshold` rule (≥30% mass at ~0 ⇒ MAP = 0) is a zero-inflation model. The under-determined part is specifically the **continuous-body mode**, which is why the bias bites hardest on the *partially* zero-inflated active cells (`mass0 ≈ 0.06`).

**Latent today** (the leaf publishes nothing — hence Tier 2, not 1), but it is **silent, directional output incorrectness for any consumer that adopts it expecting parity**. Resolution path: estimator-design effort tracked in **#89** (a distributional assumption *or* `n`-adaptive smoothing + floor; **not** merely a better tie-break; SemVer decision required). See C-24 (resolved), C-25, C-33.

---

### C-33: `hdi` computes each mass independently — no nesting (tower) guarantee

| Field | Value |
|-------|-------|
| ID | C-33 |
| Tier | 3 |
| Source | views-faoapi integration spike (2026-06-23) |
| Trigger | When a consumer composes multiple `hdi(frame, mass)` results into a credible-band tower (e.g. a fan chart), check that the bands actually nest — on skewed / multimodal empirical samples the independently-computed shortest 50% interval need not sit inside the shortest 95% interval, so a narrower band can poke **outside** a wider one. |
| Location | `src/views_frames_summarize/interval.py:23-48` (`hdi` — independent per-mass shortest interval; no nesting, no MAP-containment; single-mass-per-call API) |

`hdi` returns the empirical **shortest interval** for one mass per call and stops; it neither enforces nor offers an API for **nesting** across masses. For a true unimodal density the shortest-interval HDIs nest automatically (they are superlevel sets `{f ≥ c}`), but **empirical** shortest intervals computed independently per mass can fail to nest on skewed/multimodal samples — the densest 50% window need not lie inside the densest 95% window. A consumer's production analyzer enforces a tower **post-hoc** (expand each wider interval to contain the narrower, plus a MAP-containment shift), at the cost that the intervals are no longer the true shortest and the narrowest is **dragged by the (biased) MAP** (C-32). The two sit at opposite corners: views-frames is **honest-but-incoherent** (each interval true-shortest, no tower); the post-hoc approach is **coherent-but-corrupted** (tower forced, intervals shifted/expanded + MAP-coupled). The principled resolution is **shared with C-32**: nesting and "MAP ∈ HDI" are the **same density-level-set coherence** — derive the whole family together (one coherent/smoothed density, or the shrinking shortest-interval) so the tower **and** the mode fall out **nested-by-construction**, exposed via a multi-mass `hdi(frame, masses=[…])` that returns a guaranteed tower. Tier 3: each call is individually correct; the gap is a missing cross-call coherence guarantee / API (consumers must re-derive nesting). Tracked with C-32 in **#89**. See C-32, C-25 (resolved).

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

## Resolved Concerns

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
- **Skipped ids:** **C-04** was merged into C-18 (the "SpatialLevel slippery slope"). **C-30** is intentionally skipped — it is *pipeline-core's* external id for the cross-repo contract-test gap (referenced in ADR-005 / ADR-016), not a views-frames concern.
- **Causal clusters** (assigned by `review-rr`): **test-coverage debt** = {C-29, C-31} — **resolved by Epic 6 (2026-06-23)**. Fail-loud / parity paths that existed in code but lacked tests (root cause: the v1.0.0 suite optimized happy-path coverage over failure/parity branches); now closed with a CI 100%-coverage gate.
- **Sources:** `repo-assimilation`, `expert-review`, `test-review`, `falsification-audit`, `persona-critique`, `clean-architecture-review`, `pr-review`, `tech-debt-audit`, `incident`, `manual`.
- **Resolution:** Move to "Resolved Concerns" with resolution date and summary when addressed.
- **Header counts:** Manually maintained — update whenever a concern is added or resolved.
- **Note:** Future concerns will often reference locations in external repos (`views-pipeline-core`, `views-datafactory`, `views-faoapi`, `views-reporting`) because this leaf de-duplicates a data contract not yet relocated. Confirm those locations when the package is stood up.
- **Governed by:** ADR-010 (`docs/ADRs/010_technical_risk_register.md`).
- **Note (v0.2.0, ADR-017):** sample-axis reduction (`collapse`/MAP/HDI/quantiles) was
  removed from the leaf into the `views_frames_summarize` sibling package, eliminating
  the statistics-menu scope leak; the leaf is now a pure data contract.
