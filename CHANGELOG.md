# Changelog

All notable changes to `views-frames` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/) as governed in `GOVERNANCE.md`.

## [1.8.0] — 2026-06-28

**Native point-country broadcast in `views_frames_reconcile` (ADR-023 amendment, #143 / Epic #142),
the three showcase notebooks (Epic #166), and a governance/test hardening pass (Epic #179).** All
additive — the frozen leaf and summarize public surface are unchanged, and the hardening work makes
**no `src/` behaviour change**; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`ReconciliationModule.reconcile` accepts a point country** (`cm.sample_count == 1`) against a draws
  grid (`pgm.sample_count == S`): the point is broadcast across the `S` draws inside the orchestrator
  (`np.tile`), so callers no longer tile it themselves (the DRY home of pipeline-core's WET
  `align_country_to_grid`, #143). The **aligned-draws** path (`cm.sample_count == S`) is byte-for-byte
  unchanged; any other count still fails loud.
- **`ReconciliationModule.reconcile_result(cm, pgm) -> ReconciliationResult`** (#144) — reconciles and
  **reports the mode** (`POINT_BROADCAST` | `ALIGNED_DRAWS`) + method (`proportional`) on a returned
  `ReconciliationResult`. The mode is *returned*, never stamped on the leaf's generic `FrameMetadata`
  (ADR-020 / register C-47 — the numpy leaf carries no reconciliation vocabulary). `reconcile` is
  unchanged (it returns `reconcile_result(...).frame`). New public names: `ReconciliationResult`,
  `POINT_BROADCAST`, `ALIGNED_DRAWS`, `METHOD_PROPORTIONAL`.

### Notes
- The broadcast lives entirely in `views_frames_reconcile/module.py`; the leaf `proportional` and the
  parity-frozen `grouping` hot loop are untouched, so the torch-oracle parity is exact (0.000e+00).
- The aligned-draws mode remains the documented per-draw approximation. **ADR-024** (#145) records the
  design direction + deferral for the principled joint upgrade (and corrects `proportional.py`'s
  ambiguous "C-37" reference; register C-62). Design-only — no code.

### Documentation
- **Three showcase notebooks** (`notebooks/01_frames`, `02_summaries`, `03_reconciliation`; Epic #166):
  public-frozen-API-only, synthetic-data teaching notebooks for the frames contract, the posterior
  summaries (with a calibration/coverage + PIT panel), and reconciliation — including a
  bit-identity-≠-method-quality panel and a toy-lattice spatial view (register C-59/C-60/C-61).
- **`docs/CICs/Reconcile.md`** (Epic #179) — the package-level Class Intent Contract for
  `views_frames_reconcile` (§1–§11): the sum-to-country / zero-preservation / non-negativity /
  de-mutation guarantees, the point/aligned **mode** contract, the five fail-loud validation guards
  + the per-draw-approximation caveat, and the green/beige/red test alignment. The reconcile package
  was the last non-trivial surface without a CIC (ADR-006); **register C-64 resolved**.
- **ADR-025 — value-buffer immutability is by convention; only the index is enforced** (Epic #179).
  Corrects the "immutable value objects" contract (the three frame CICs §9/§3 + README design
  principle 3) to match the code: the index (`time`/`unit`) is `setflags(write=False)`-enforced; the
  value buffer is immutable *by convention* (left writeable to preserve zero-copy / `mmap` — mutating
  `.values` in place is unsupported). The `setflags`-enforce on `.values` would be a MAJOR
  ("tightening an invariant" on a frozen-surface member, GOVERNANCE/ADR-018), so it is recorded as a
  **deferred MAJOR-rider**, not done now; **register C-63 resolved** (contract corrected).

### Tests
- **Adversarial (red) test hardening** (Epic #179), no `src/` change, 100% line+branch coverage held:
  - the non-finite (NaN / ±inf) fail-loud guard in `exceedance`/`expected_shortfall` is now pinned on
    the **blocked (multi-block) path** — the bad draw placed in a non-first block via the `block_rows`
    kwarg with block 0 all-finite (**register C-65 resolved**);
  - **conformance-suite negatives** — `assert_reconcile_contract` and `assert_summarizer_contract` are
    shown to reject a deliberately non-conforming implementation (the leaf's C-51 envelope-negative
    pattern, extended to the sibling packages);
  - **reconcile mode-corners** — `reconcile_result.mode` for both-points and pre-tiled-cm inputs (both
    `ALIGNED_DRAWS`); and **`ReconciliationResult` frozen-ness** (`FrozenInstanceError`).

## [1.7.0] — 2026-06-26

**Forecast reconciliation is a third sibling package (ADR-023, Epic 11).** A new importable
package `views_frames_reconcile` joins `views_frames` + `views_frames_summarize` in the mono-wheel.
Additive surface — the leaf and summarize are unchanged; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`views_frames_reconcile`** — numpy + `views_frames` only — makes grid (`pgm`) predictions sum,
  per posterior draw, to their country (`cm`) totals:
  - **`ReconciliationModule(map_keys, map_vals)`** — orchestrator holding the **injected**
    `(time, priogrid_gid) → country_id` mapping (never fetched here; ADR-014/ADR-023);
    `.reconcile(cm_frame, pgm_frame)` returns a new pgm `PredictionFrame`.
  - **`reconcile_proportional(grid, country)`** — the per-draw top-down proportional method
    (zeros preserved, country totals authoritative, non-negative).
  - **`assert_reconcile_contract(...)`** — the conformance suite (sum-to-country per draw,
    zero-preservation, non-negativity, level correctness, injected mapping).
- A faithful **WET relocation** of the parity-proven reconciler from views-postprocessing — the
  ported modules differ from the originals by import lines only (no algorithmic change).

### Notes
- **Charter (ADR-023):** frame-reconciliation algorithms only; **never fetch the mapping** (injected
  as arrays, like `cross_level_align`); no IO, scoring, plotting, or foreign `views_*`. Import-DAG
  `views_frames_reconcile → {views_frames}`.
- **Parity is the gate:** green against the frozen views-reporting torch oracle, **and** a
  new-vs-old bit-identity head-to-head (`np.array_equal`, 136 cases) vs the old
  `views_postprocessing.reconciliation` — proven bit-identical at relocation.
- **WET before DRY:** `grouping.py` overlaps the leaf's `cross_level_align`; folding them is a
  deferred later story. The principled probabilistic upgrade (C-37) will be a future sibling module.
- Consumer repoint (views-models) + views-postprocessing deletion are the cross-repo cutover, gated
  on this release.

## [1.6.0] — 2026-06-25

**Worst-case scenario estimator (ADR-022, register C-55/C-56 Resolved).** Additive surface — the
frozen v1.0–v1.5 estimators are unchanged; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`expected_shortfall(frame, tails, *, block_rows=ROW_BLOCK)` → `(N, …, K)` array** — the per-row
  **mean of the worst `⌈t·S⌉` draws** for each upper-tail fraction `t` (the tail mean / CVaR): a
  robust, **coherent** (subadditive) worst-case risk measure and the companion to `exceedance`.
  Vectorized over the trailing sample axis in row-blocks.
- **Conformance:** `assert_summarizer_contract` now also checks the ES laws — `min ≤ ES ≤ max`,
  non-decreasing as the tail deepens, and `ES(t) ≥ the (1 − t)` quantile.

### Notes
- **`max` is never offered** — it is the highest-variance, non-reproducible summary `expected_shortfall`
  replaces (D-10). **Tails are required per-call, no default, not in config**, in `(0, 1]` — the
  consumer's policy. **Fails loud** on any **non-finite draw — NaN or ±inf** (C-56; the guard is
  `np.isfinite`, hardened by the falsify audit 2026-06-25 so an `inf` draw can't silently contaminate
  the tail mean to `inf`), empty `tails`, or any `t ∉ (0, 1]`.
- **Best case ships no code** — a low quantile (`quantiles(frame, [0.005])`) + `exceedance(frame, [0])`
  express it, including the "model puts no mass at zero" case.
- Country worst-case = `aggregate_distributions` → `expected_shortfall` (the estimator never
  aggregates; the joint-sample obligation is the consumer's, C-55).
- **WET before DRY:** its own module, written explicitly — *not* refactored into a shared "tail
  reducer" with `quantiles`/`exceedance`. Deferred, reversible extensions: a lower-tail/`side` mode, an
  `expected_shortfall_reducer`, `cvar`/`tail_mean` synonyms (D-10).

## [1.5.0] — 2026-06-24

**Threshold exceedance-probability estimator (ADR-021, register C-49/C-50 Resolved).** Additive
surface — the frozen v1.0–v1.4 estimators are unchanged; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`exceedance(frame, thresholds, *, block_rows=ROW_BLOCK)` → `(N, …, K)` array** — the per-row
  empirical survival fraction `P(Y > c_k)` for each of `K` caller-supplied thresholds (same
  shape/role family as `quantiles`), vectorized over the trailing sample axis in row-blocks.
  Distribution-agnostic (a counting reducer); the flagship is `P(Y > 0)` = onset.
- **`exceedance_reducer(threshold)` → `Reducer`** — a `collapse`-compatible factory, so
  `collapse(frame, exceedance_reducer(c))` returns `P(Y > c)` as a `(N, …, 1)` frame, sharing one
  strict-`>` / fail-loud-non-finite policy.
- **Conformance:** `assert_summarizer_contract` now also checks the exceedance laws — values in
  `[0, 1]`, non-increasing in the threshold, `P(> −inf) = 1`, `P(> +inf) = 0`.

### Notes
- **Thresholds are required per-call, no default, not in config** — an *input* in the frame's own
  units, like `quantiles`' `qs` (ADR-021). Canonical VIEWS thresholds (25/100/1000 country, 5/25
  grid) are documentation only, never an executable default.
- **Strict `>`** (D-08; for integer counts `P(Y ≥ k)`, pass `k − 1`). **Fails loud** on any
  **non-finite draw — NaN or ±inf** (C-50; `np.isfinite` guard, hardened by the falsify audit
  2026-06-25 so an `inf` draw can't silently bless `P` as valid — ±inf *thresholds* stay valid) and on
  empty thresholds. Country exceedance = `aggregate_distributions` → `exceedance` (the estimator never
  aggregates; the joint-sample obligation is the consumer's, C-49).
- **Deferred, reversible extensions:** an `inclusive`/`≥` flag (D-08), a `nan_policy='skip'` (D-07),
  relative/reference-frame thresholds, an EP-curve helper.

## [1.4.0] — 2026-06-24

**Generic provenance + a published frame-envelope checker (ADR-020, register C-46/C-47).**
Operationalises the substrate half of the `MetricFrame` decision: views-evaluation hosts
`MetricFrame` on the views-frames substrate, and this release provides the two leaf-side
pieces it reuses. No change to the frozen surface (ADR-018); `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`FrameMetadata.run_id` / `FrameMetadata.data_version`** — optional, **generic** provenance
  (additive/MINOR, ADR-013). Meaningful for any frame; they ride the existing
  `to_dict`/`from_dict` and IO round-trip unchanged. Evaluation-specific provenance
  (`scoring_code_version`, full-precision `evaluation_timestamp`) deliberately stays in
  views-evaluation's `MetricFrame`, never this generic header (the C-47 guard).
- **`views_frames.conformance.assert_frame_envelope`** — the shared **frame envelope** (float32
  values, explicit trailing axis, save/load round-trip) factored out of `assert_frame_contract`
  as a single written authority. A non-spatiotemporal sibling (views-evaluation's string-keyed
  `MetricFrame`) validates against it instead of re-asserting drifting copies (mitigates C-46).
  `assert_frame_contract` now composes the envelope + the spatiotemporal `(time, unit)` rule.

### Fixed
- **Conformance round-trip is now NaN-tolerant.** `_assert_roundtrip` compared values with
  `np.array_equal` (NaN-blind: `NaN != NaN`), so a *correct* round-trip of a frame carrying NaN
  values raised a spurious `"save/load changed values"`. Now uses `equal_nan=True` on the float32
  values. This matters for `assert_frame_envelope`'s intended consumer — evaluation metrics are
  realistically NaN ("not calculated"). A bugfix that only *removes a false rejection*, so
  `CONFORMANCE_FLOOR` stays `1.0.0`.

### Notes
- The cross-repo **wire schema + `schema_version`** marker (the other half of the C-46
  mitigation) is the emit/consume wire contract and remains future work, tracked on C-46.

## [1.3.0] — 2026-06-24

**Distribution-agnostic tower summary (register C-45).** Removes a count-domain magnitude
assumption from the tower estimators: the "quiet row" rule zeroed any posterior whose
`max(draws) <= 1.0` — zeroing *every* cell of a rate/probability `[0,1]` target and silently
erasing low-intensity counts. The estimators now work for **any** distribution (counts,
continuous, normal, beta/probability). No change to the frozen estimators (ADR-018);
`CONFORMANCE_FLOOR` stays `1.0.0`.

### Changed
- **No magnitude-based zeroing by default.** `tower_point` / `hdi_tower` / `summarize_tower` /
  `bimodality` no longer collapse sub-1 rows to 0. Zero-inflation is handled by the **density**
  of the `tip_mass` floor (a zero-majority row reads 0 naturally), which is distribution-agnostic.
- **`config['zero_cutoff']` is now an optional, off-by-default opt-in** (default `None`). A count
  consumer that wants "sub-1 ⇒ 0" sets it to a float; it is read **live** (the prior import-time
  snapshot, which made the knob non-configurable at runtime, is fixed).

### Notes
- The modeling choice "should a sub-1 *count* posterior read 0?" is the **consumer's** (set
  `zero_cutoff`, or apply a downstream `mass_at_zero` policy) — not a leaf default.
- ADR-019 amended; the Summarize CIC documents the opt-in and the consumer-owns-the-zero-policy
  note. Register **C-45 → Resolved**.

## [1.2.0] — 2026-06-24

**Outside-in HDI tower + mass-aware tip + fail-loud config (register C-44).** Fixes a silent
output-correctness bug in the v1.1 tower estimators: a **minority duplicated draw** (a couple
of exact zeros, a lone pair) could hijack the degenerate ~2-sample narrowest floor and collapse
both `tower_point` and the nested `hdi_tower` bands — confirmed on real faoapi forecast cells.
No change to the frozen estimators (`map_estimate`/`hdi`/`quantiles`, ADR-018);
`CONFORMANCE_FLOOR` stays `1.0.0`.

### Changed
- **The canonical tower is now built `outside-in`** (widest floor first, each narrower floor the
  shortest interval *contained in* its wider parent) instead of inside-out. Robust by
  construction: a lonely outlier is shed by the well-determined wide floors and the containment
  constraint forbids a narrower floor from re-selecting it. Nesting + reproducibility laws
  unchanged.
- **`tower_point` reads the configurable `tip_mass` floor** (default `0.5` — the "shorth"),
  not the degenerate 5% floor — a mass-aware, duplicate-robust point.
- **The tower-family public functions drop their tunable kwargs** (`bins`/`prominence`/
  `min_mass`/`block_rows`); those values now come from the config (below). `masses` stays a
  per-call argument. The frozen estimators are untouched.

### Added
- **`views_frames_summarize.config`** — a fail-loud config (`TOWER_CONFIG` dict, `REQUIRED_KEYS`,
  `validate_config`, `get`, `canonical_floors`) holding every tower-family tunable (the grid,
  `tip_mass`, the zero cutoff, the bimodality thresholds, the row-block) with **no silent
  defaults**: a missing key raises `ValueError` naming it (ADR-008/009).
- Conformance: the tip law is restated to **tip ∈ the `tip_mass` floor**; a large adversarial +
  edge test matrix (the C-44 truth table A–L, real faoapi cells, duplicate-count sweep,
  NaN/inf locality, multimodality, config fail-loud) — `tests/test_summarize_config.py` added.

### Governance
- **ADR-019 amended** (inside-out → outside-in; `tip_mass`; config). **Register: C-44 → Resolved**
  (Tier 1); C-32 / C-34 mitigation notes updated. The Summarize CIC records the new construction,
  the `tip_mass` tip, and the config failure mode.

## [1.1.1] — 2026-06-24

Documentation only — no public-API or behaviour change (identical contract).

### Documentation
- README: a "Which estimator?" note (frozen `map_estimate`/`hdi`/`quantiles` vs the
  coherent-tower `tower_point`/`hdi_tower`/`summarize_tower`) and a **bimodality caveat** —
  a `bimodality` `0` means "no clear bimodality detected," **not** "proven unimodal"
  (conservative-by-design, register C-34/C-42).
- Corrected the `tower._pin` docstring (ties resolve **down** to the lower floor via
  `argmin`'s lowest-index rule) and the `research/map_hdi/audit.py` stale tuple-unpack
  (register C-41).

## [1.1.0] — 2026-06-24

**Coherent posterior summary (ADR-019).** Additive new surface in `views_frames_summarize`
— the frozen v1.0 estimators (`map_estimate`/`hdi`/`quantiles`/`collapse`/`aggregate_*`) are
unchanged. A constrained-nested HDI tower resolves the C-33 nesting gap and mitigates the
C-32 mode bias.

### Added
- `hdi_tower(frame, masses)` → `(N, …, M, 2)` — nested-**by-construction** HDIs read off a
  **fixed canonical grid** (5% body + fine tail to 0.99); requested masses are *pinned*,
  never inserted, so a mass's interval is reproducible regardless of which other masses are
  requested (resolves register **C-33**). Out-of-range masses fail loud (ADR-008).
- `tower_point(frame)` → `(N, …, 1)` frame — the **tower tip** (median of the narrowest
  floor) with a raw-count zero short-circuit: an unbinned, directionally-unbiased
  alternative to the C-32-biased `map_estimate` (mitigates **C-32**).
- `bimodality(frame)` → `(N, …, 1)` — a deliberately conservative 0/1 flag for genuinely
  multi-peaked rows (where a single point / shortest interval is ill-defined).
- `summarize_tower(frame, masses)` → `TowerSummary(point, intervals, bimodal, masses)` — a
  single-pass bundle deriving all three from one sort; provably equal to the trio.
- Conformance suite extended with the tower laws (nesting / tip-in-narrowest /
  reproducibility / bundle==trio); `tests/test_summarize_tower.py` (🟩/🟫/🟥 per ADR-005).

### Governance
- **ADR-019** records the decision; the `Summarize` CIC documents the new surface and its
  failure modes. Register: **C-33 → Resolved**; **C-32 → mitigation note** (a non-biased
  point now exists; a fully-convergent mode remains #89). Evidence + research note under
  `research/map_hdi/`.

## [1.0.1] — 2026-06-23

**Test hardening (Epic 6).** No public-API change — the frozen v1.0 surface is unchanged.
Closes the post-freeze test-coverage debt: every fail-loud branch and the cross-frame shared
surface are now exercised, and CI enforces 100% line coverage.

### Added
- 🟥 IO failure-mode tests (`tests/test_io.py`): `arrow.save` bad ndim, `FeatureFrame.load`
  missing `feature_names`, `npz.load` missing sidecar, `arrow.load` non-frame parquet
  (register C-29).
- `tests/test_frame_parity.py` — a parametrized matrix asserting `reindex`/`select`/
  `with_metadata`/`save`-`load` across all three frame types, filling the Feature/TargetFrame
  `reindex` gap (register C-31).
- `tests/test_construction_red.py` — construction/validation fail-loud reds (3-D →
  `PredictionFrame`, row-mismatch, `from_2d`, malformed identifiers/values).
- `tests/test_value_object_and_laws.py` — index value-object semantics (`__hash__`/`__eq__`/
  `argsort`), the `SpatialLevel` vocabulary, and the two CIC alignment laws (align∘collapse
  commute; `reindex` idempotent on a superset).

### Changed
- CI (`ci.yml`) enforces **100% line coverage** (`pytest --cov --cov-fail-under=100`) and now
  runs on `development` as well as `main`. `pytest-cov` added to the dev dependency group.

## [1.0.0] — 2026-06-21

**API freeze (ADR-018).** Leaf completion (Epic 5) — the second-round consumer-review
findings, then the v1.0 freeze. Two rounds of consumer review validated
the design (no ADR challenged). From here the public surface is frozen; breaking
changes are MAJOR (GOVERNANCE "Stability — the v1.0 freeze"). The pre-1.0
breaking-in-MINOR latitude ends.

### Added
- `FeatureFrame`/`PredictionFrame`/`TargetFrame` gain `select(positions | mask) ->
  Frame` and `reindex(other) -> Frame` (frame-level row selection / alignment; the
  former returned only positions). `SpatioTemporalIndex.select(indexer)` underlies them.
  Closes the second-round consumer gap F12.
- `SpatioTemporalIndex.cross_level_align_arrays` + `aggregate_distributions_arrays` —
  columnar `(map_keys, map_vals)` mappings, ~30× faster / ~10× less memory than a
  grid-scale Python dict (benchmark-gated; register C-26).

### Changed
- **`map_estimate` tie-break is now deterministic and portable** — it breaks ties on
  integer counts (lowest-index), not `np.histogram(density=True)`'s width-based
  argmax, which differed by ~1 ulp across numpy versions and flipped on ties. Output
  is now identical on every numpy build (register C-24). Only tied rows differ from
  v0.3.0; ties are arbitrary, so this is a strict portability win.
- `hdi`/`quantiles` are row-blocked like `map_estimate`; all three estimators take a
  `block_rows` kwarg. Peak memory no longer scales with the full grid (register C-25).
- `Persistable.save`/`load` typed `Path | str` to match the concretes (register F-L).
- Conformance floor `CONFORMANCE_FLOOR = "1.0.0"`; it tracks the whole published
  conformance surface and bumps on breaking changes to it (register C-27).

### Fixed
- The `map_estimate` equivalence test asserted bit-exact float32 equality and was red
  on the numpy 1.26 floor while green in CI; the **`floor` CI job now runs pytest** at
  `numpy==1.26.4`, not just mypy — the floor is behaviour-checked (register C-24).
- README: `MetricFrame`/C-48 framing softened to "substrate, not the cure" (it is out
  of the leaf); status header → v1.0.0.

### Governance
- **ADR-018** records the freeze and the frozen surface; GOVERNANCE adds the 1.0
  stability policy and the pre-1.0 latitude's end.
- `examples/cross_level.py` demonstrates the time-varying mapping + `HDI(sum) ≠ sum(HDI)`.

## [0.3.0] — 2026-06-21

Hardening release (Epic 4) — the first-round consumer-review findings.
No new surface beyond a time-aware mapping; correctness, typing, and scale.

### Changed (breaking, pre-1.0)
- **`cross_level_align` / `aggregate_distributions` mappings are now keyed by
  `(time, unit)`** (`Mapping[tuple[int, int], int]`), not `unit` alone — ADR-014's
  mapping is time-varying (a cell's country changes by month) and the static shape
  could not express it (register C-20). The remap is vectorized (void-viewed keys +
  `searchsorted`) and fails loud on the old unit-only shape or a missing key.

### Added
- `assert_cross_level_alignment_law` in `views_frames.conformance` — the time-varying
  cross-level law (one cell, two months → two target units).
- `SpatioTemporalIndex.has_unique_rows()` + a documented `(time, unit)` row-uniqueness
  stance (duplicates allowed; same-level joins assume uniqueness — register C-21).
- `index` on the `SpatioTemporalIndexed` protocol (a consumer typing to the abstraction
  can reach `.index`/`cross_level_align` — register C-23/F4).
- `py.typed` markers in both packages (the package is now seen as typed — register C-23).
- A CI **`type-floor`** job pinning `numpy==1.26.4`; `mypy --strict` is green at the
  declared floor (was 14 `[type-arg]` errors hidden behind numpy 2.x — register C-19).
- `examples/quickstart.py` (a runnable end-to-end example) + an in-repo synthetic
  grid-adapter proxy test (`tests/test_proxy_adapter.py`, register F15 in-repo).

### Performance
- `map_estimate` and `hdi` are vectorized over the trailing axis (no per-row Python
  loop); `map_estimate` runs a **row-blocked** batched histogram that caps peak memory
  at `O(block × bins)` and stays identical to v0.2.0 to float32 precision —
  bit-exact on numpy ≥ 2.0, ~1 ulp on the 1.26 floor (register C-22/#181, C-24).
  A `tracemalloc` scale guard asserts memory does not scale with `rows × bins`.

### Fixed
- Doc↔code drift: README version header, the nonexistent `align` op (§4.3), and the
  `collapse` glossary entries (§13a.2/§14 — `collapse` lives in the sibling package).

## [0.2.0] — 2026-06-21

Two-package release: the leaf is now a pure data contract; sample-axis summarization
moved to a sibling package (ADR-017).

### Added
- `views_frames_summarize` — a second package (numpy-only, depends on `views_frames`)
  for sample-axis posterior summarization over frames:
  - `collapse(frame, reducer)` — generic point fold (statistic injected) → `(N,…,1)` frame.
  - `map_estimate(frame)` — histogram-peak MAP with a zero-mass→0 rule → frame.
  - `hdi(frame, mass)` — shortest-interval HDI → `(N,…,2)` index-aligned array.
  - `quantiles(frame, qs)` → `(N,…,len(qs))` index-aligned array.
  - `aggregate_distributions(frame, mapping, level)` — conservation-correct joint-sampling
    cross-level aggregation (`HDI(sum) ≠ sum(HDI)`), reusing the leaf's injected mapping.
  - `views_frames_summarize.conformance.assert_summarizer_contract`.

### Changed (breaking, pre-1.0)
- **Removed `collapse` (and `SUPPORTED_AGGREGATE_METHODS`) from the leaf frames** and
  from the `Sampled` protocol; the leaf keeps only the structural `sample_count`/
  `is_sample`. All sample-axis reduction is now in `views_frames_summarize` (ADR-017).
- The import-enforcement test is now a two-package DAG: `views_frames` imports no
  `views_*`/pandas (so never the summarize package); `views_frames_summarize` imports
  only `views_frames` + numpy.

## [0.1.0] — 2026-06-21

First implemented release — the leaf is functional and releasable (Epic 2).

### Added
- `SpatioTemporalIndex` — immutable `{time, unit, level}` row index with pure-numpy
  same-level alignment (`intersect`, `reindex`/`searchsorted`, `is_superset_of`,
  `argsort`) and `cross_level_align(mapping, target_level)` with a **consumer-injected**
  mapping (ADR-014).
- `SpatialLevel` — cm/pgm identifier vocabulary, time-first index names (ADR-015).
- The frame family (separate siblings, no shared base — ADR-011): `PredictionFrame`
  `(N, S)`, `FeatureFrame` `(N, F, S)` (+ `from_2d` shim), `TargetFrame` `(N, 1)`.
  The sample axis is always an explicit trailing axis (ADR-012).
- `FrameMetadata` — typed, optional-extensible provenance header (ADR-013).
- Protocols `Frame` / `SpatioTemporalIndexed` / `Sampled` / `Persistable`.
- `io/npz` (native, mmap-capable) and `io/arrow` (flat-columnar parquet; the `[arrow]`
  extra). Object-dtype / list-in-cell is banned.
- `views_frames.conformance` — the published conformance suite + the conformance
  floor (ADR-016, `GOVERNANCE.md`).
- Construction is fail-loud and numpy-only; structural (not temporal) validation.

### Notes
- Resolves register concerns C-07 (copy-vs-view), C-09 (generic io state),
  C-11 (structural-not-temporal), C-14 (injected cross-level mapping), C-17
  (numpy-only `PredictionFrame`).
- Out of scope (Epic 3): consumer adoption (re-export shims in pipeline-core /
  datafactory; pandas migration).
