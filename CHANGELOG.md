# Changelog

All notable changes to `views-frames` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/) as governed in `GOVERNANCE.md`.

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
