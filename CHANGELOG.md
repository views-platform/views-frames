# Changelog

All notable changes to `views-frames` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/) as governed in `GOVERNANCE.md`.

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
