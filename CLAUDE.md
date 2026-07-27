# views-frames

The VIEWS platform's **data-contract layer**: small, stable, abstract, immutable
array+identifier value objects (`PredictionFrame`, `TargetFrame`, `FeatureFrame`)
at the **root of the platform dependency DAG**, plus two sibling operation packages
in the same wheel. numpy only; depends on nothing internal; every other repo
depends *toward* it.

> **Status:** **released — v1.10.x on PyPI**, public API **frozen since v1.0.0**
> (ADR-018; everything after is additive, `CONFORMANCE_FLOOR` stays `1.0.0`).
> Consumers install `views-frames` and validate against the published conformance
> suite (`views_frames.conformance`, ADR-016). See `CHANGELOG.md` for the release
> history and `README.md` §status for the version chronicle.

## Architecture

**Three packages** under `src/` (one wheel), strict one-way dependencies
`views_frames_summarize → views_frames` and `views_frames_reconcile → views_frames`
(siblings never import each other), enforced by `tests/test_import_enforcement.py`:

**`src/views_frames/`** — the pure data contract (numpy-only; depends on nothing; frozen):

- `index.py` — `SpatioTemporalIndex` (`{time, unit, level}`; same-level numpy alignment +
  consumer-injected cross-level remap; identifier arrays write-protected).
- `spatial_level.py` — `SpatialLevel` (cm/pgm identifier vocabulary; labels only).
- `protocols.py` — `Frame` / `SpatioTemporalIndexed` / `Sampled` (`sample_count`/`is_sample`
  only) / `Persistable` (four small segregated protocols).
- `metadata.py` — `FrameMetadata` (typed, frozen, generic-only provenance; ADR-020).
- `_validation.py` — shared construction-time invariants.
- `feature_frame.py`, `prediction_frame.py`, `target_frame.py` — sibling frames
  `(N,F,S)` / `(N,S)` / `(N,1)` (no shared base; ADR-011 Option C).
- `io/` — `npz` (native, mmap-capable) + `arrow` (flat-columnar parquet codec,
  module-level by decision D-11). **The only place `pyarrow` may be imported.**
- `conformance/` — the published suite consumers run in *their* CI
  (`assert_frame_contract`, `assert_frame_envelope`, alignment laws; `CONFORMANCE_FLOOR`).

**`src/views_frames_summarize/`** — sample-axis posterior summarization *over* frames
(ADR-017; numpy-only; depends on `views_frames`). Point estimates (`collapse`,
`map_estimate`, `tower_point`) return `(N,…,1)` frames; intervals/arrays (`hdi`,
`quantiles`, `hdi_tower`, `exceedance`, `expected_shortfall`, `bimodality`) return
index-aligned arrays; `aggregate_distributions[_arrays]` sums sample distributions
across levels (joint sampling). Fail-loud config for the tower family (ADR-019).
**Never** owns IO, domain data, scoring, or reconciliation.

**`src/views_frames_reconcile/`** — top-down proportional reconciliation of pgm grid
forecasts to cm country totals (ADR-023; numpy-only; depends on `views_frames`).
`ReconciliationModule(map_keys, map_vals)` with the geography **injected** (never
fetched); `reconcile` / `reconcile_result` (the latter reports the
`point-broadcast`/`aligned-draws` **mode** — returned, never stamped on the leaf
header, D-12). The per-draw method is a documented approximation; the principled
joint upgrade is designed and deferred (ADR-024, register C-62).

## Tooling (uv + hatchling)

Always invoke via `uv run`:

```bash
uv sync                 # install deps + the package (editable)
uv run pytest           # tests (incl. import-enforcement + falsification suites)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy src/        # type check (strict; also check with --python 3.11 before pushing)
uv build                # build wheel + sdist
```

CI additionally gates 100% line+branch coverage
(`uv run pytest --cov --cov-fail-under=100`) and a numpy-floor job.

## Design principles (the hard constraints)

1. **numpy only in the core.** Never import `pandas`, `polars`, `geopandas`,
   `wandb`, `viewser`, `torch`, or any foreign `views_*` package. `pyarrow` is allowed
   *only* under `io/`. Enforced by `tests/test_import_enforcement.py` (ADR-002).
2. **Immutable value objects.** Operations return new frames; structural ops share
   the buffer (zero-copy); only reductions allocate (register C-07). Enforced for the
   *index*; **by convention** for the value buffer (writeable on purpose to preserve
   zero-copy/mmap — mutating `.values` in place is unsupported; ADR-025, C-66 rider).
3. **Fail loud.** Invariants raise `ValueError`/`TypeError` at construction and at
   every validation guard; the guarantee is *structural*, not temporal (`time` is
   opaque; register C-11).
4. **No shared frame base.** Frames are separate siblings (ADR-011); cm/pgm is a
   `SpatialLevel` *value*, never a class axis.
5. **No domain data.** Cross-level cm↔pgm alignment takes a consumer-injected
   mapping; the leaf and siblings never embed/fetch it (ADR-014/ADR-023).
6. **One concept per file** (test-enforced: ≤1 public class per module); explicit
   `__init__.py` re-exports (no `import *`).
7. **Frozen surface + WET before DRY.** The v1 public surface only grows additively
   (removal/tightening = MAJOR + cross-repo coordinated bump, GOVERNANCE.md);
   deliberate duplication recorded in ADRs is a choice, not debt.

## Governance

Constitutional ADRs 000–010, project ADRs 011–026, CICs for every non-trivial
surface (7 active incl. the package-level `Summarize.md` and `Reconcile.md`),
contributor protocols, and standards live in `docs/`. The technical risk register
(`reports/technical_risk_register.md`) is the curated concern/decision log. Run
`bash docs/validate_docs.sh` to check documentation consistency. Build *against*
the README design bible — if code and README disagree, reconcile before merging.
Releases: dev→main via **merge commit** (never squash — main carries squash release
commits dev lacks), then `gh release create vX.Y.Z` triggers the PyPI publish
(Trusted Publishing; see `docs/guides/publishing-to-pypi.md`).
