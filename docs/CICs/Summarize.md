
# Class Intent Contract: views_frames_summarize

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-21
**Related ADRs:** ADR-002, ADR-011, ADR-012, ADR-014, ADR-017

> The `views_frames_summarize` package (functions, not a class). Implemented in
> v0.2.0; depends on `views_frames` + numpy only.

---

## 1. Purpose

Sample-axis **posterior summarization over frames**: reduce a frame's trailing sample
axis to point estimates and credible intervals, and aggregate sample distributions
across spatial levels. One tested home for the HDI/MAP logic faoapi and reporting each
re-derive (ADR-017).

---

## 2. Non-Goals (Explicit Exclusions)

- **No IO** (serialization is `views_frames.io`).
- **No domain/geographic data** — cross-level aggregation takes the
  consumer-**injected** mapping (the same one `cross_level_align` takes); it embeds no
  geography.
- **No scoring / actuals** — comparing a prediction to truth is views-evaluation.
- **No reconciliation/redistribution, no plotting.**
- **No `views_*` import except `views_frames`** (enforced by the import-DAG test).

---

## 3. Responsibilities and Guarantees

- `collapse(frame, reducer)` → a `(N, …, 1)` frame: applies `reducer(values, axis=-1)`,
  rebuilds a valid same-type frame preserving index + metadata.
- `map_estimate(frame)` → a `(N, …, 1)` frame: histogram-peak MAP with a zero-mass→0
  rule.
- `hdi(frame, mass)` → `(N, 2)` numpy array aligned to `frame.index`: shortest-interval
  highest-density interval.
- `quantiles(frame, qs)` → `(N, len(qs))` numpy array aligned to `frame.index`.
- `aggregate_distributions(frame, mapping, level)` → a coarser frame: element-wise sum
  of sample arrays across constituent cells **preserving sample index** (joint
  sampling), so `HDI(sum) ≠ sum(HDI)` holds.
- Point estimates return frames; interval estimates return index-aligned arrays
  (ADR-017).

---

## 4. Inputs and Assumptions

- Inputs are `views_frames` frames with a trailing sample axis (ADR-012).
- `reducer` reduces the trailing axis; `mapping` is injected by the caller.

---

## 5. Outputs and Side Effects

- New frames (point) or numpy arrays (interval). No IO, no global state.

---

## 6. Failure Modes and Loudness

- A reducer producing the wrong shape fails loud via the rebuilt frame's validation.
- `aggregate_distributions` without a mapping is an error (mirrors `cross_level_align`).

---

## 7. Boundaries and Interactions

- Depends **only** on `views_frames` + numpy. `views_frames` never imports this package
  (import-DAG test). Consumers (faoapi, reporting) call these functions instead of
  re-deriving HDI/MAP.

---

## 8. Examples of Correct Usage

```python
from views_frames_summarize import collapse, map_estimate, hdi
point = collapse(pf, np.mean)        # (N, 1) frame
mode  = map_estimate(pf)             # (N, 1) frame
lo_hi = hdi(pf, mass=0.9)            # (N, 2) array aligned to pf.index
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: scoring against actuals — that is views-evaluation
crps(pf, actuals)

# WRONG: embedding the priogrid->country geography here — inject it
aggregate_distributions(pf, level="country")   # mapping is required
```

---

## 10. Test Alignment

- **Green:** collapse/map shape + identifier preservation; quantile ordering.
- **Beige:** HDI shortest-interval + nesting; index-aligned interval outputs.
- **Red:** `HDI(aggregate(...)) ≠ sum(per-cell HDI)` (the C-70 joint-sampling guard);
  bad reducer fails loud; the import-DAG test keeps the leaf pure.

---

## 11. Evolution Notes

- New estimators are additive. The charter (ADR-017) bounds what may be added — reject
  IO, domain data, scoring, reconciliation, plotting.

---

## End of Contract

This document defines the **intended meaning** of `views_frames_summarize`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
