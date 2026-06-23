
# Class Intent Contract: views_frames_summarize

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-23
**Related ADRs:** ADR-002, ADR-011, ADR-012, ADR-014, ADR-017, ADR-019

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
  rule. **Caveat (register C-32):** the densest-bin tie-break is lowest-index
  (deterministic; C-24), which biases the mode toward the left tail (zero) for
  right-skewed, zero-inflated, low-sample posteriors — **not a drop-in** for a
  production histogram-MAP on such data. A robust mode estimator is a separate effort
  (#89).
- `hdi(frame, mass)` → `(N, 2)` numpy array aligned to `frame.index`: shortest-interval
  highest-density interval.
- `quantiles(frame, qs)` → `(N, len(qs))` numpy array aligned to `frame.index`.
- `aggregate_distributions(frame, mapping, level)` → a coarser frame: element-wise sum
  of sample arrays across constituent cells **preserving sample index** (joint
  sampling), so `HDI(sum) ≠ sum(HDI)` holds.
- Point estimates return frames; interval estimates return index-aligned arrays
  (ADR-017).

### Coherent posterior summary — the constrained-nested HDI tower (ADR-019)

- `hdi_tower(frame, masses)` → `(N, …, M, 2)` array aligned to `frame.index`: the
  requested masses' HDIs, read off a **fixed canonical tower** built inside-out so each
  floor is the shortest interval *containing* the next-narrower one. **Guarantees:**
  nested **by construction** (resolves C-33); a mass's interval is **independent of the
  other requested masses** (requested masses are pinned to the fixed grid, never inserted
  — the reproducibility law). Quiet rows (`max <= 1`) collapse to `(0, 0)`.
- `tower_point(frame)` → a `(N, …, 1)` frame: the **tower tip**, the median of the
  narrowest canonical floor, with a raw-count zero short-circuit. Unbinned and symmetric,
  so it carries **none** of `map_estimate`'s histogram tie-break bias (mitigates C-32). It
  is **not** a consistency-guaranteed mode (fixed 5% smoothing); pair it with `bimodality`.
- `bimodality(frame)` → a `(N, …, 1)` array of `0.0`/`1.0`: a **deliberately conservative**
  multi-mode flag (zero false positives on skewed/zero/active posteriors; fires only on
  clearly separated modes). It is a heuristic, not a formal test.
- `summarize_tower(frame, masses)` → `TowerSummary(point, intervals, bimodal, masses)`: a
  single-pass bundle deriving all three from one sort; **provably equal** to the trio.

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
- **Silent caveat, not a loud failure (register C-32):** `map_estimate`'s lowest-index
  tie-break is statistically biased toward zero on right-skewed, zero-inflated, low-sample
  posteriors. It does not raise — it returns a defensible-but-biased mode; consumers must
  not treat it as a drop-in for a production MAP on such distributions (prefer
  `tower_point`; redesign for a convergent mode: #89).
- `hdi_tower` / `summarize_tower` raise `ValueError` on a mass outside `(0, 1)` — fail
  loud rather than silently pin a nonsense value to the nearest floor (ADR-008).
- **Out-of-contract input is localized, not guarded:** `NaN` draws are out of contract
  (frames do not ban them); the tower behaves deterministically and confines the effect
  to the offending row — it neither crashes nor corrupts other rows, but the result for a
  NaN row is undefined.
- **`bimodality` is a conservative heuristic, not a loud failure:** it is biased toward
  *not* flagging (it will read an ambiguous/overlapping mixture as unimodal). Its job is
  to catch a *clearly* separated future regime change, not to adjudicate every heavy tail.

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

# the coherent posterior summary (ADR-019): one sort, a nested reproducible tower
from views_frames_summarize import summarize_tower
s = summarize_tower(pf, masses=(0.5, 0.9, 0.99))
s.point          # (N, 1) frame — the tower tip
s.intervals      # (N, 3, 2) nested HDIs, aligned to pf.index
s.bimodal        # (N, 1) flag — where a single point is ambiguous
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

- **Green:** collapse/map shape + identifier preservation; quantile ordering; the tower
  laws (nesting by construction, tip-in-narrowest, the reproducibility law, bundle==trio)
  and vectorized==per-row reference (`tests/test_summarize_tower.py`).
- **Beige:** HDI shortest-interval + nesting; index-aligned interval outputs; tower edges
  (S=1, tiny-S median floor, tail pinning to 0.99, FeatureFrame leading axes).
- **Red:** `HDI(aggregate(...)) ≠ sum(per-cell HDI)` (the C-70 joint-sampling guard);
  bad reducer fails loud; out-of-range mass fails loud; the zero-cutoff boundary;
  `tower_point` independent of the frozen `map_estimate`; NaN stays localized; the
  import-DAG test keeps the leaf pure.

---

## 11. Evolution Notes

- New estimators are additive. The charter (ADR-017) bounds what may be added — reject
  IO, domain data, scoring, reconciliation, plotting.
- The canonical tower grid (ADR-019) is a **fixed constant, not a parameter** — a
  different grid would be a *new* function, never a tunable density (which would break the
  reproducibility law). A fully-consistent convergent mode remains #89.

---

## End of Contract

This document defines the **intended meaning** of `views_frames_summarize`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
