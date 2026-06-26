# `views-frames` notebooks

Runnable, synthetic-data showcases of the three packages in this repo — what the frames
**are** and what they can do, the **summaries** you can read off a posterior, and how
**reconciliation** works. They double as living, public-API-only demos for consumer-repo
authors migrating from pandas DataFrames onto frames.

> **🚧 Status: roadmaps only — not built yet.** Each notebook currently holds a *plan*
> (markdown cells: section outline, reusable assets, open questions). We align on those
> roadmaps **before** the first content pass; code cells get filled in afterwards. Edit the
> markdown freely — those cells are the working design document for each notebook.

## The three notebooks

| Notebook | Package | Shows |
|---|---|---|
| [`01_frames.ipynb`](01_frames.ipynb) | `views_frames` | The frames as a typed storage contract — `SpatioTemporalIndex`, the three sibling frames, immutability/zero-copy, cross-level alignment, `save`/`load` (npz + arrow), fail-loud construction. |
| [`02_summaries.ipynb`](02_summaries.ipynb) | `views_frames_summarize` | Posterior summaries over the sample axis — MAP, the HDI tower, quantiles, exceedance, expected-shortfall, the bimodality flag — swept over a **zoo of distribution shapes**, with **calibration/coverage checks**, ET-vs-HDI, **failure modes**, a **toy-lattice map view**, and a decision-relevance framing (panel additions, register C-59/C-61). |
| [`03_reconciliation.ipynb`](03_reconciliation.ipynb) | `views_frames_reconcile` | Reconciling grid forecasts to country totals — `reconcile_proportional` + `ReconciliationModule`, with conservation / zero-preservation / joint-sampling, plots/animation, the **reconciliation-literature context** (proportional vs MinT/probabilistic; bit-identity ≠ method-quality) and a **does-it-help** check (panel additions, register C-60). |

## Conventions

- **Public, frozen API only** — so each notebook is also a contract demo. A cell that *wants* a
  convenience that doesn't exist (e.g. `frame.to_parquet`) is a **demand signal** to record (see
  register D-11), never a reason to reach into the leaf.
- **Synthetic data only** — fixed seeds, generated in-notebook; no `viewser`, no domain fetches,
  no `views_*` consumer imports (zero domain knowledge — ADR-001).
- **Un-gated dev artifact** — `notebooks/` sits beside `research/` and `scripts/`, outside `src/`;
  the package never imports it, so the import-DAG and the frozen core are untouched.
- **Light & reproducible** — small sample sizes that render fast; *Run All* should finish in well
  under a minute.

## Running them (planned)

The notebooks need plotting/jupyter deps the package itself does not. These will live in an
**optional extra**, never the runtime dependencies:

```bash
# (to be added in the build pass — not yet in pyproject)
uv sync --extra docs          # matplotlib, scipy, jupyterlab, + the [arrow] extra for parquet
uv run jupyter lab notebooks/
```

## Setup still to decide (in the roadmap discussion, before the first content pass)

- [ ] Add the optional `[docs]` dependency group to `pyproject.toml` (matplotlib, scipy, jupyter, …).
- [ ] Exclude `notebooks/` from the lint/coverage gate (as `research/` is) — they are not gated src.
- [ ] Decide whether to add a light **`nbmake`/papermill CI job** that just checks the notebooks
      still *run* end-to-end (catches API drift) — or leave them un-gated like `research/`.
- [ ] Confirm the per-notebook roadmaps (the open-questions cell in each).

## Source material

**Self-contained by rule:** each notebook generates its own synthetic data and renders its own
plots/animations from code in the notebook — it depends on **no file outside this repo**. Where
prior exploration exists (earlier HDI/tower or reconciliation prototypes), we **port the useful
logic into the notebook** during the build; we never reference notebooks or figures scattered
elsewhere on disk.

In-repo material we may adapt:

- `research/map_hdi/` — the synthetic distribution battery + tower/density plotting (notebook 02).
- `tests/fixtures/reconciliation_*.npz` — a realistic cm/pgm example if we want one (notebook 03).
- `scripts/verify_reconcile_parity.py`, `tests/test_reconcile_conformance.py` — drift/conservation
  + scenario-builder logic to borrow (notebook 03).
- `views-faoapi/notebooks/quickstart_*.ipynb` — in-platform tone/structure reference.
