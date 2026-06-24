
# ADR-017: Posterior / sample summarization is a sibling package, not the leaf

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Consulted:** views-faoapi, views-reporting (the two consumers of record for HDI/MAP)
**Informed:** views-evaluation, views-pipeline-core, views-postprocessing

---

## Context

`views-frames` v0.1.0 carried a `collapse(method="arithmetic_mean")` on the frames —
a string-keyed statistics registry inside the maximally-stable leaf. Two consumers
(faoapi, reporting) independently asked for richer sample-axis reduction (MAP, HDI,
quantiles). A read-only trace of the real code established the facts:

- **It is a per-row reduction of a `PredictionFrame`'s sample axis that produces a
  frame** — same `(time, unit)` index, samples replaced by `{map, hdi_lower,
  hdi_upper, …}`. It touches **no actuals**; it summarizes the prediction's own
  posterior.
- **It is not evaluation.** views-evaluation scores predictions *against actuals*
  (every metric requires `y_true` and `y_pred`); it contains zero HDI/MAP. Putting
  posterior summarization there is a category error.
- **It is duplicated and subtle.** faoapi (`data/statistics.py` +
  `data/handlers.py`, ~500–600 LOC) and reporting (`statistics/`, ~400 LOC) each
  re-derive the same algorithm: histogram-peak MAP with a zero-mass→0 rule;
  shortest-interval HDI with nesting/MAP-containment; quantiles; and a
  joint-sampling cross-level aggregation where `HDI(sum) ≠ sum(HDI)`.
- **It is volatile** — "the way we collapse uncertainty will change and expand."

Volatile, expanding statistical logic does not belong in the most-pinned package
(SAP, README §8). But it *is* worth centralizing once (correctness is hard and it is
re-implemented in 2→3 repos). A separate repo is rejected (microservice sprawl);
coupling it into views-postprocessing is rejected (you could not summarize a frame
anywhere without importing a heavy downstream dependency).

---

## Decision

Sample-axis summarization lives in a **second package in this repo**,
`views_frames_summarize` (the `src/views_frames_*` multi-package pattern used by
views-datafactory). It depends on `views_frames` + numpy only; `views_frames`
**never** imports it (enforced by `tests/test_import_enforcement.py`).

`collapse` and the statistics registry are **removed from the leaf**. The leaf keeps
only the *structural* sample-axis facts (`sample_count`, `is_sample`).

### Charter (bounded — this is what prevents back-door bloat)

`views_frames_summarize` **may** contain: sample-axis **point** estimators
(`collapse(frame, reducer)`, `map_estimate`) returning a `(N, …, 1)` frame;
**interval** estimators (`hdi`, `quantiles`) returning numpy arrays aligned to the
input frame's index; and conservation-correct **cross-level aggregation** of sample
distributions (using the leaf's injected-mapping `cross_level_align` for the index
side). It **must not** contain: IO, domain/geographic data, actuals or scoring
(that is views-evaluation), reconciliation/redistribution, plotting, or any
`views_*` import except `views_frames`.

> **Extended by ADR-019 (v1.1.0):** the charter's point/interval categories were
> extended additively with the coherent-tower estimators (`hdi_tower`, `tower_point`,
> `summarize_tower`) and a new **per-row diagnostic-flag** output class (`bimodality`,
> a `(N, …, 1)` 0/1 array). All remain within the bounds above (sample-axis only; no IO,
> domain data, scoring, or foreign `views_*`).

---

## Rationale

This is "what changes together stays together" applied correctly: the **data
contract** is one closure group (stable → `views_frames`); the **summarization
statistics** are another (volatile → `views_frames_summarize`). Same repo means they
version and test together (a frame change breaks the summarizer's CI immediately) with
no cross-repo brittleness; the import-DAG keeps the leaf provably pure; CRP holds
(a contract-only consumer never imports the summarizer). One correct, tested
implementation replaces the duplicated ~500-LOC re-derivations.

---

## Considered Alternatives

### Alternative A: keep `collapse`/HDI/MAP in the leaf
- **Pros:** ergonomic; one install.
- **Cons:** volatile statistics in the most-pinned package (every new statistic = a
  release everyone eats); the leaf becomes "frames + a stats library" — the exact
  drift the package exists to avoid.
- **Reason for rejection:** breaks SAP and the leaf's identity.

### Alternative B: put it in views-evaluation
- **Cons:** category error — evaluation scores pred-vs-actual; HDI/MAP is pred-only.
- **Reason for rejection:** confirmed by the code (zero HDI/MAP in views-evaluation).

### Alternative C: put it in views-postprocessing / a new repo
- **Cons:** can't summarize a frame without a heavy downstream import; postprocessing
  must know frame internals (brittle); a new repo is microservice sprawl.
- **Reason for rejection:** both fail the "quick, safe, low-maintenance" goal.

---

## Consequences

### Positive
- The leaf is provably pure (import-DAG enforced); stays maximally stable.
- One tested home for the dangerous statistical code; consumers can stop reinventing it.
- No new repo, no microservice, no heavy coupling.

### Negative
- Two packages to maintain (mitigated: same repo, one CI, numpy-only, bounded charter).
- Consumers must import a second package for summaries (acceptable: it is `views_frames_summarize`, numpy-light, not a downstream service).

---

## Implementation Notes

- `src/views_frames_summarize/` added to `[tool.hatch.build.targets.wheel] packages`
  (one wheel, two importable packages).
- `tests/test_import_enforcement.py` encodes the DAG: leaf imports no `views_*`;
  summarize imports only `views_frames` + numpy.
- Algorithms ported faithfully (numpy-only) from faoapi/reporting and golden-tested.
- **Consumer adoption (faoapi/reporting deleting their copies) is out of scope and
  user-driven — no sibling repo is modified by this work.**

---

## Validation & Monitoring

- The import-DAG test is the guardrail: if `views_frames` ever imports
  `views_frames_summarize`, CI fails.
- Golden-value tests reproduce the consumers' behavior (zero-mass MAP, shortest HDI +
  nesting, `HDI(sum) ≠ sum(HDI)`).
- Failure mode to watch: any non-summary concern (IO, domain data, scoring) appearing
  in `views_frames_summarize` — reject per the charter.

---

## Open Questions

- The exact home for *interval* outputs if a consumer wants them frame-attached
  (currently index-aligned arrays) — revisit only if a real consumer needs it.

---

## References

- README §0/§6 (two-package layout); `docs/ADRs/011`–`016`.
- Evidence: `views-faoapi/.../data/statistics.py`, `.../data/handlers.py`
  (`calculate_hdi_map`, `_aggregate_distributions`); `views-reporting/.../statistics/`.
- Issues #38, #39; Epic #46.
