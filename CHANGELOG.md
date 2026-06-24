# Changelog

All notable changes to `views-frames` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/) as governed in `GOVERNANCE.md`.

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
