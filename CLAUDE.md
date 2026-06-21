# views-frames

The VIEWS platform's **data-contract layer**: small, stable, abstract, immutable
array+identifier value objects (`FeatureFrame`, `PredictionFrame`, `TargetFrame`,
and anticipated siblings) at the **root of the platform dependency DAG**. numpy
only; depends on nothing internal; every other repo depends *toward* it.

> **Status:** **implemented — v0.1.0** (Epic 2). `src/views_frames/` realises the
> contract (index, frames, io, conformance suite). Consumer adoption (re-export
> shims, pandas migration) is Epic 3.

## Architecture

**Two packages** under `src/` (datafactory multi-package pattern), strict one-way
dependency `views_frames_summarize → views_frames`, enforced by
`tests/test_import_enforcement.py`:

**`src/views_frames/`** — the pure data contract (numpy-only; depends on nothing):

- `index.py` — `SpatioTemporalIndex` (`{time, unit, level}` + same-level numpy alignment).
- `spatial_level.py` — `SpatialLevel` (cm/pgm identifier vocabulary; labels only).
- `protocols.py` — `Frame` / `SpatioTemporalIndexed` / `Sampled` (`sample_count`/`is_sample` only) / `Persistable`.
- `_validation.py` — shared construction-time invariants.
- `feature_frame.py`, `prediction_frame.py`, `target_frame.py` — sibling frames (no shared base; ADR-011 Option C).
- `io/` — `npz` (native) + `arrow` (flat-columnar). **The only place `pyarrow` may be imported.**

**`src/views_frames_summarize/`** — sample-axis posterior summarization *over* frames
(ADR-017; numpy-only; depends on `views_frames`). Point estimates
(`collapse(frame, reducer)`, `map_estimate`) return a `(N,…,1)` frame; intervals
(`hdi`, `quantiles`) return arrays aligned to the frame's index. **Never** owns IO,
domain data, scoring, or reconciliation.

## Tooling (uv + hatchling)

Always invoke via `uv run`:

```bash
uv sync                 # install deps + the package (editable)
uv run pytest           # tests (incl. import-enforcement + falsification stubs)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy src/        # type check (strict)
uv build                # build wheel + sdist
```

## Design principles (the hard constraints)

1. **numpy only in the core.** Never import `pandas`, `polars`, `geopandas`,
   `wandb`, `viewser`, `torch`, or any `views_*` package. `pyarrow` is allowed
   *only* under `io/`. Enforced by `tests/test_import_enforcement.py` (ADR-002).
2. **Immutable value objects.** Operations return new frames; structural ops share
   the buffer (zero-copy); only reductions allocate (ADR-013, register C-07).
3. **Fail loud at construction.** Invariants raise `ValueError`/`TypeError`; the
   guarantee is *structural*, not temporal (`time` is opaque; register C-11).
4. **No shared frame base.** Frames are separate siblings (ADR-011); cm/pgm is a
   `SpatialLevel` *value*, never a class axis.
5. **No domain data.** Cross-level cm↔pgm alignment is a protocol with a
   consumer-injected mapping; the leaf never embeds/fetches it (ADR-014).
6. **One concept per file**; explicit `__init__.py` re-exports (no `import *`).

## Governance

Constitutional ADRs 000–010, project ADRs 011–016, CIC infrastructure, contributor
protocols, and standards live in `docs/`. The technical risk register is
`reports/technical_risk_register.md`. Run `bash docs/validate_docs.sh` to check
documentation consistency. Build *against* the README design bible — if code and
README disagree, reconcile before merging.
