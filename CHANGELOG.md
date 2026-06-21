# Changelog

All notable changes to `views-frames` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/) as governed in `GOVERNANCE.md`.

## [0.3.0] — 2026-06-21

Hardening release (Epic 4) — the round-01 review findings (`perspectives/round01/`).
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
