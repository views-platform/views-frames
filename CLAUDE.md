# views-frames

The VIEWS platform's **data-contract layer**: small, stable, abstract, immutable
array+identifier value objects (`PredictionFrame`, `TargetFrame`, `FeatureFrame`)
at the **root of the platform dependency DAG**, plus two sibling operation packages
in the same wheel. numpy only; depends on nothing internal; every other repo
depends *toward* it.

> **Status:** **released — v1.11.x on PyPI**, public API **frozen since v1.0.0**
> (ADR-018; everything after is additive, `CONFORMANCE_FLOOR` stays `1.0.0`).
> Consumers install `views-frames` and validate against the published conformance
> suite (`views_frames.conformance`, ADR-016). See `CHANGELOG.md` for the release
> history and `README.md` §status for the version chronicle.

## Maintenance mode

**This package is finished.** It is released, its public API has been frozen since v1.0.0,
and its governance documents have been checked against the code and are now asserted by CI.
Work here should be rare, small, and caused by something outside this repository.

**Do not run discovery tooling here.** `repo-assimilation`, `graphify`, `review-base-docs`
and `review-rr` return findings by construction. This repo carries roughly 9,400 lines of
governance prose against 3,700 lines of source, and prose that large is never perfectly
self-consistent. On a frozen package these tools *manufacture* work rather than reveal it —
that is how a one-line CI addition became a day-long sprint on 2026-08-17. Run them on a
repository that is still being designed.

**The register's open entries are a log, not a backlog.** Every one names an external
precondition — the next MAJOR bump, a sibling repo's type, a research result, a measured
receipt that has not arrived. Re-auditing them returns the answer their precondition already
gives. Do not reopen them; do not treat the count as debt to burn down.

**For a small change:** review it, ship it. If something adjacent looks wrong, say so in one
sentence and let the maintainer decide. Do not open an epic. A finding that is real and
unrelated goes in the register with its precondition and stops there.

**What legitimately reopens this repo:** a consumer reports a contract defect; a dependency
floor moves; a sibling repository needs an additive surface; a MAJOR bump is coordinated
across the platform. Everything else is optional, and optional work on a frozen leaf costs
more than it returns.

## Architecture

**Three packages** under `src/` (one wheel), strict one-way dependencies
`views_frames_summarize → views_frames` and `views_frames_reconcile → views_frames`
(siblings never import each other), enforced by `tests/test_import_enforcement.py` and,
in CI, by the `import-linter` contracts in `pyproject.toml` (`uv run lint-imports`):

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
uv run lint-imports     # import contracts ([tool.importlinter] in pyproject.toml)
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
