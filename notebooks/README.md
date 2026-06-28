# `views-frames` notebooks

Runnable, synthetic-data showcases of the three packages in this repo — what the frames
**are** and what they can do, the **summaries** you can read off a posterior, and how
**reconciliation** works. They double as living, public-API-only demos for consumer-repo
authors migrating from pandas DataFrames onto frames.

> **Status: all three built.** `01_frames`, `02_summaries` and `03_reconciliation` are
> built and runnable — public frozen API only, synthetic data, *Run All* < 1 min each.
> Built via the notebook epics [#148](../../../issues/148) / [#156](../../../issues/156) /
> [#166](../../../issues/166). The optional non-blocking `nbmake` CI check is the one
> remaining item ([#151](../../../issues/151)).

## The three notebooks

| Notebook | Package | Shows |
|---|---|---|
| [`01_frames.ipynb`](01_frames.ipynb) ✅ | `views_frames` | The frames as a typed storage contract — `SpatioTemporalIndex`, the three sibling frames, immutability/zero-copy, cross-level alignment, `save`/`load` (npz + arrow), fail-loud construction. |
| [`02_summaries.ipynb`](02_summaries.ipynb) ✅ | `views_frames_summarize` | Posterior summaries over the sample axis — MAP, the HDI tower, quantiles, exceedance, expected-shortfall, the bimodality flag — swept over a **zoo of distribution shapes**, with **calibration/coverage checks**, ET-vs-HDI, **failure modes**, a **toy-lattice map view**, and a decision-relevance framing (panel additions, register C-59/C-61). |
| [`03_reconciliation.ipynb`](03_reconciliation.ipynb) ✅ | `views_frames_reconcile` | Reconciling grid forecasts to country totals — `reconcile_proportional` + `ReconciliationModule`, with conservation / zero-preservation / joint-sampling, plots/animation, the **reconciliation-literature context** (proportional vs MinT/probabilistic; bit-identity ≠ method-quality) and a **does-it-help** check (panel additions, register C-60). |

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

## Running them

The notebooks need plotting/jupyter deps the package itself does not. These live in the
**optional `[docs]` extra**, never the runtime dependencies (the core stays numpy-only):

```bash
uv sync --extra docs          # matplotlib, scipy, jupyterlab, + the [arrow] extra for parquet
uv run jupyter lab notebooks/
```

The `[docs]` extra self-references `[arrow]`, so a single `--extra docs` also enables the
parquet round-trip demo in `01_frames.ipynb`. The `notebooks/` tree is excluded from the
lint/coverage gate (`[tool.ruff] extend-exclude`), so it never touches the frozen core or the
import-DAG.

## Setup decisions (resolved during the build)

- [x] Add the optional `[docs]` dependency group to `pyproject.toml` (matplotlib, scipy, jupyter, …). — #149
- [x] Exclude `notebooks/` from the lint/coverage gate (as `research/` is) — they are not gated src. — #149
- [x] **`nbmake` CI check** — adopted and **wired** as a **non-blocking** job
      (`.github/workflows/notebooks.yml`: `pytest --nbmake notebooks/`, `continue-on-error: true`) so it
      catches frozen-API drift without ever blocking the core gate. `nbmake` rides in the `[docs]` extra. — #151
- [x] Confirm the per-notebook roadmaps — all three built and runnable.

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
