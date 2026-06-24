
# Class Intent Contract: views_frames_summarize

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-24
**Related ADRs:** ADR-002, ADR-008, ADR-009, ADR-011, ADR-012, ADR-014, ADR-017, ADR-019, ADR-021

> The `views_frames_summarize` package (functions, not a class). Implemented in
> v0.2.0; the coherent-tower surface (`hdi_tower`/`tower_point`/`bimodality`/
> `summarize_tower`, ADR-019) was added additively in v1.1.0. Depends on `views_frames`
> + numpy only.
>
> **Amendment (2026-06-24, ADR-021, register C-49/C-50/D-07/D-08).** Adds the threshold
> **exceedance** surface (`exceedance`/`exceedance_reducer`) — per-row `P(Y > c)`. **Shipped
> additively in v1.5.0** (`src/views_frames_summarize/exceedance.py`,
> `tests/test_summarize_exceedance.py`; register C-49/C-50 Resolved). The §3/§4/§6/§8–§11
> entries marked *(ADR-021)* describe the live contract.
>
> **Amendment (2026-06-25, ADR-022, register C-55/C-56/D-10).** Adds the **worst-case** surface
> `expected_shortfall` (the tail mean / CVaR) — per-row mean of the worst `⌈t·S⌉` draws. **Ratified
> here; ships additively in v1.6.0.** Best-case ships **no code** (a low quantile + `exceedance(0)`).
> The §3/§4/§6/§8–§11 entries marked *(ADR-022)* describe the **intended** contract ahead of the code.

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
- **No threshold *policy* (ADR-021)** — `exceedance` evaluates caller-supplied thresholds; the
  package ships **no default or named thresholds and no risk tiers**. Which thresholds (per
  stakeholder / per level) is the consumer's, in the API repos. The canonical VIEWS sets
  (`25/100/1000` country, `5/25` grid) are documentation only, never an executable default.
- **No worst-case *policy*, and never `max` (ADR-022)** — `expected_shortfall` evaluates
  caller-supplied tail levels; the package ships **no default tail level**. `max` (the single
  worst draw) is **not offered** at all — it is the high-variance, non-reproducible summary this
  surface exists to replace. Which tail counts as "worst case" is the consumer's.
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
- `aggregate_distributions_arrays(frame, map_keys, map_vals, level)` → the **columnar**
  form of the above: the `(time, unit) → target_unit` mapping as parallel arrays rather
  than a dict, so a producer holding a grid-scale mapping stays vectorized end-to-end
  (register C-26).
- Point estimates return frames; interval estimates return index-aligned arrays
  (ADR-017).

### Coherent posterior summary — the constrained-nested HDI tower (ADR-019)

- `hdi_tower(frame, masses)` → `(N, …, M, 2)` array aligned to `frame.index`: the
  requested masses' HDIs, read off a **fixed canonical tower** built **outside-in** so each
  floor is the shortest interval *contained in* its wider parent. **Guarantees:** nested
  **by construction** (resolves C-33); **robust to minority duplicated draws** (resolves
  C-44 — an outlier shed by the wide floors cannot be re-selected by a narrower one); a
  mass's interval is **independent of the other requested masses** (pinned to the fixed
  grid, never inserted — the reproducibility law). **Distribution-agnostic** (C-45): no
  magnitude zeroing by default — works for counts, continuous, normal, and `[0,1]`
  (rate/probability) targets; if the optional `zero_cutoff` is set, `max <= cutoff` rows
  collapse to `(0, 0)`. **Caveat (the nesting trade-off):** a tower band is *coherent and
  nested*, **not** the unconstrained per-mass shortest interval — the containment cascade
  can shift a band's *location* (≈ up to ~20% of its width on right-skewed data; the width
  is near-identical) off the true highest-density region. For the exact single-mass shortest
  HDI with no nesting constraint, use the frozen `hdi`; use the tower when you need a
  *coherent, reproducible* family of bands.
- `tower_point(frame)` → a `(N, …, 1)` frame: the **tower tip**, the median of the
  configurable **`tip_mass`** floor (default 0.5 — the shorth). Zero-inflation is read off
  that floor's density (a zero-majority row reads 0; the optional `zero_cutoff` magnitude
  rule is off by default — C-45). Unbinned and median-based, so it carries **none** of
  `map_estimate`'s histogram tie-break bias (mitigates C-32) **and** is robust to minority
  duplicates (C-44).
  It is **not** a consistency-guaranteed mode; pair it with `bimodality`. **Caveat (the
  semantic shift — read before adopting over a histogram MAP):** on right-skewed /
  zero-inflated / multi-cluster posteriors `tower_point` returns the **densest** mode, which
  is often *much lower* than a histogram MAP that lands on a sparse high bin — that
  disagreement is largely the C-32 bias being **corrected**, not an error. And because
  `bimodality` flags only *clearly separated* modes (C-34, conservative), a *spread*
  heavy-tailed cell whose dense mode differs sharply from its histogram MAP may **not** be
  flagged: the single returned point is the dense mode **by design**, not a hidden second
  peak. Consumers replacing an incumbent MAP must expect — and validate — this downward,
  density-following shift on real data.
- `bimodality(frame)` → a `(N, …, 1)` array of `0.0`/`1.0`: a **deliberately conservative**
  multi-mode flag (zero false positives on skewed/zero/active posteriors; fires only on
  clearly separated modes). It is a heuristic, not a formal test.
- `summarize_tower(frame, masses)` → `TowerSummary(point, intervals, bimodal, masses)`: a
  single-pass bundle deriving all three from one sort; **provably equal** to the trio.

### Threshold exceedance probabilities (ADR-021)

- `exceedance(frame, thresholds)` → `(N, …, K)` numpy array aligned to `frame.index`: the per-row
  **empirical survival fraction** `P(Y > c_k)` for each of the `K` caller-supplied thresholds — the
  fraction of sample-axis draws **strictly** greater than `c_k`. Same shape/role family as
  `quantiles` (an index-aligned array; the caller holds the index), vectorized and block-applied.
  **Guarantees:** values in `[0, 1]`; **non-increasing in threshold**; `P(> −inf) = 1`,
  `P(> +inf) = 0`. **Distribution-agnostic** (a counting reducer — no histogram, no config, no
  unimodality assumption), so it is robust where the tower is weakest (C-34). The flagship is
  `P(Y > 0)` = probability of *any* activity (onset).
- `exceedance_reducer(threshold)` → a `collapse`-compatible reducer, so a single-threshold
  exceedance as a `(N, …, 1)` **frame** is `collapse(frame, exceedance_reducer(c))`. It shares
  `exceedance`'s one direction/NaN policy — consumers never re-roll `np.mean(samples > c)`.
- **Strict `>` is a fixed contract, not a knob** — for integer counts wanting `P(Y ≥ k)`, pass
  `k − 1`. **Geography-blind / per-row only:** "unit" is a row; country exceedance =
  `aggregate_distributions(...)` **then** `exceedance` (compose; the estimator never aggregates).

### Worst-case scenario — expected shortfall (ADR-022)

- `expected_shortfall(frame, tails)` → `(N, …, K)` numpy array aligned to `frame.index`: for each
  upper-tail fraction `t` in `tails`, the per-row **mean of the worst `⌈t·S⌉` draws** (the average of
  the worst-case scenarios). Same shape/role family as `quantiles`/`exceedance`, vectorized and
  block-applied. **Guarantees:** `min ≤ ES(t) ≤ max`; **non-decreasing as the tail deepens**
  (`ES(t₁) ≥ ES(t₂)` for `t₁ ≤ t₂`); `ES(t) ≥ the (1 − t) quantile`. A **coherent** (subadditive)
  risk measure, and the conditional-magnitude companion to `exceedance` ("given a bad scenario, how
  bad on average").
- **Upper tail only; `max` is never offered.** Averaging a *set* of tail draws is what makes the
  worst-case robust; a single extreme order statistic (`max`) is the high-variance summary this
  replaces. **Geography-blind / per-row only:** country worst-case = `aggregate_distributions(...)`
  **then** `expected_shortfall` (compose; the estimator never aggregates).
- **Caveat — extremeness vs stability:** the deeper the tail, the fewer draws support it, so a `t`
  so small that `⌈t·S⌉` selects only a handful of draws re-approaches `max`'s volatility. **Pick
  `t ≳ 5/S`.** The level is the consumer's (no default).

### Best-case scenario — no estimator (ADR-022)

- **Best case ships no code.** For fatalities the lower bound is `0` by construction, so a **low
  quantile** (`quantiles(frame, [0.005])`) returns it; the genuinely informative "the model puts no
  mass at zero" case is the low quantile being `> 0` **and** `exceedance(frame, [0])` (`P(Y > 0)`)
  being ≈ 1. Pairing a best-case symbol with the worst-case is rejected (CRP).

---

## 4. Inputs and Assumptions

- Inputs are `views_frames` frames with a trailing sample axis (ADR-012).
- `reducer` reduces the trailing axis; `mapping` is injected by the caller.
- Tower-family tunables (the canonical grid, `tip_mass`, the optional `zero_cutoff`, the
  bimodality thresholds, the row-block) come from `config.TOWER_CONFIG` — a fail-loud single
  source with **no silent defaults** (ADR-008/009); `zero_cutoff` is read live. `masses` is
  the only per-call tunable; the frozen estimators (ADR-018) are out of scope of the config.
- **Consumer owns the zero policy (C-45).** The leaf does **no** magnitude zeroing by
  default — it is distribution-agnostic. A consumer with a **count** target that wants
  "sub-1 ⇒ 0" sets `config.TOWER_CONFIG["zero_cutoff"]` to a float (e.g. `1.0`), *or*
  applies its own zero policy downstream (e.g. faoapi's `mass_at_zero` rule). The leaf
  never imposes a count-domain magnitude assumption on rate/probability/continuous targets.
- **`exceedance` thresholds (ADR-021)** are a **required** per-call argument, with **no default
  and not in config** — they are an *input* (*what* you ask of the distribution), like
  `quantiles`' `qs`, not an algorithm *tunable*. They are in the **frame's own units**
  (grid thresholds for a grid frame, country thresholds for a country frame); level-dependence is
  handled by passing different thresholds per single-level frame. `exceedance` reads no config.
- **`expected_shortfall` tails (ADR-022)** are likewise a **required** per-call argument in `(0, 1]`,
  with **no default and not in config** — the tail fraction is *what* you ask of the distribution
  (e.g. `0.01` = "the worst 1%"), the consumer's policy. `expected_shortfall` reads no config.

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
- A **missing tower-config key** raises `ValueError` naming it (ADR-009 completeness) — the
  estimators cannot run on an incomplete config, by design.
- **Out-of-contract input is localized, not guarded:** `NaN` draws are out of contract
  (frames do not ban them); the tower behaves deterministically and confines the effect
  to the offending row — it neither crashes nor corrupts other rows, but the result for a
  NaN row is undefined.
- **`exceedance` is the exception — it fails *loud* on NaN (ADR-021, register C-50):** a naive
  `np.mean(v > c)` would count `NaN > c` as `False` and silently deflate the probability — worst on
  the `P(Y > 0)` onset flagship — so `exceedance` **raises `ValueError`** on any NaN in a reduced row
  rather than return a quietly-wrong probability. Empty `thresholds` likewise raises (no silent
  `(N, …, 0)`). It is deliberately stricter than the tower's localized-NaN posture (ADR-008).
- **Aggregate exceedance carries an unguarded correctness obligation (register C-49):** per-row
  `exceedance` is correct for a level only if each row's `S` samples are the *true joint posterior*
  for that unit. `P(Σ > C)` is **unrecoverable** from per-cell `P(Yᵢ > c)`, so country exceedance
  must be computed on an already-aggregated frame (`aggregate_distributions` → `exceedance`), and is
  correct only when the summed samples are jointly drawn (shared-draw-index / sample-space
  reconciliation). The estimator **cannot** verify this — it is an upstream guarantee.
- **`expected_shortfall` fails *loud* on NaN (ADR-022, register C-56):** numpy sorts NaN **last**, so
  a naive top-`⌈t·S⌉` mean would silently select the NaNs and return a NaN/garbage worst-case — so it
  **raises `ValueError`** on any NaN in a reduced row. Empty `tails`, or any `t ∉ (0, 1]`, likewise
  raise (a tail with no samples). Same fail-loud posture as `exceedance` (ADR-008).
- **Aggregate worst-case carries the same obligation as exceedance (register C-55):** the tail **mean**
  of a country total must be computed on an already-aggregated frame (`aggregate_distributions` →
  `expected_shortfall`); it is correct only when the summed samples are jointly drawn, and a tail mean
  is *more* sensitive to the cross-cell dependence than a tail probability. The estimator cannot verify
  it — an upstream guarantee.
- **`bimodality` is a conservative heuristic, not a loud failure (register C-34):** it is
  biased toward *not* flagging — it will read an ambiguous/overlapping mixture, an
  unequal-weight split (minority mode below `min_mass`), or a tall-narrow-beside-spread pair
  as unimodal. Its job is to catch a *clearly* separated future regime change, not to
  adjudicate every heavy tail.

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

# threshold exceedance (ADR-021): caller-supplied thresholds, in the frame's units
from views_frames_summarize import exceedance, exceedance_reducer, collapse
ep = exceedance(grid_pf, thresholds=(0, 5, 25))   # (N, 3) array; P(Y>0), P(Y>5), P(Y>25)
onset = collapse(grid_pf, exceedance_reducer(0))  # (N, 1) frame — P(Y>0) as a frame

# country exceedance = aggregate the samples first, THEN reduce per row
country_pf = aggregate_distributions(grid_pf, mapping, level="country")
country_ep = exceedance(country_pf, thresholds=(100, 1000))   # P(country total > c)

# worst-case scenario (ADR-022): the tail mean, NOT max
from views_frames_summarize import expected_shortfall, quantiles
worst = expected_shortfall(grid_pf, tails=(0.05, 0.01))   # (N, 2) — mean of worst 5% / worst 1%

# best-case scenario: no function — a low quantile + the onset probability
best = quantiles(grid_pf, [0.005])        # (N, 1) — 0 in a zero-inflated cell, >0 if no zero mass
no_zero_mass = exceedance(grid_pf, [0])   # P(Y>0) ≈ 1 ⟺ even the best case is violent
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: scoring against actuals — that is views-evaluation
crps(pf, actuals)

# WRONG: embedding the priogrid->country geography here — inject it
aggregate_distributions(pf, level="country")   # mapping is required

# WRONG: treating a tower band as the exact shortest single-mass HDI. It is a
# coherent *nested* band and may sit off the true HDI by ~20% of its width on
# skewed data (the nesting trade-off). Use the frozen `hdi` for that:
hdi_tower(pf, masses=(0.9,))            # nested-coherent band, NOT the bare 90% HDI
hdi(pf, mass=0.9)                       # RIGHT: the unconstrained shortest 90% interval

# WRONG: expecting tower_point to reproduce an incumbent histogram MAP. On
# right-skewed / spread cells it returns the *densest* (often much lower) mode by
# design, and bimodality only flags *clearly separated* peaks — a sharp drop vs a
# MAP is the C-32 bias being corrected, not a hidden second mode. Validate the shift.
tower_point(pf)                         # the robust dense mode (may be << a histogram MAP)

# WRONG: recovering aggregate exceedance from per-cell exceedances (register C-49).
# P(country total > C) is NOT a function of the grid cells' P(Y>c) — aggregate the
# SAMPLES first, then reduce:
exceedance(grid_pf, (1000,)).mean()                 # WRONG: meaningless
exceedance(aggregate_distributions(grid_pf, mapping, "country"), (1000,))  # RIGHT

# WRONG: expecting the package to supply default thresholds / risk tiers. Thresholds are
# required and caller-supplied; policy lives in the consumer (ADR-021).
exceedance(pf)                          # TypeError — thresholds are required, no default

# WRONG: using max for the worst case. It is a single extreme order statistic — highest
# variance, not reproducible. Use a tail mean (ADR-022):
collapse(pf, np.max)                    # WRONG: volatile worst-case
expected_shortfall(pf, tails=(0.01,))   # RIGHT: robust, coherent worst-case

# WRONG: a tail so small it selects ~1 draw — that IS max again (caveat: pick t ≳ 5/S).
expected_shortfall(pf, tails=(1e-4,))   # with small S, ⌈t·S⌉ → 1 → reapproaches max's volatility

# WRONG: recovering aggregate worst-case from per-cell ES (register C-55) — aggregate first:
expected_shortfall(aggregate_distributions(grid_pf, mapping, "country"), (0.01,))  # RIGHT
```

---

## 10. Test Alignment

- **Green:** collapse/map shape + identifier preservation; quantile ordering; the tower
  laws (nesting by construction, tip-in-`tip_mass`-floor, the reproducibility law,
  bundle==trio) and vectorized==per-row reference (`tests/test_summarize_tower.py`).
- **Beige:** HDI shortest-interval + nesting; index-aligned interval outputs; tower edges
  (S=1, tiny-S median floor, tail pinning to 0.99, FeatureFrame leading axes).
- **Red:** `HDI(aggregate(...)) ≠ sum(per-cell HDI)` (the C-70 joint-sampling guard);
  the C-44 truth table A–L + real faoapi cells (a minority duplicate must not capture the
  tip/bands); the duplicate-count sweep; bad reducer / out-of-range mass / missing config
  key all fail loud; the zero-cutoff boundary; `tower_point` independent of the frozen
  `map_estimate`; NaN/inf stays localized; the import-DAG test keeps the leaf pure
  (`tests/test_summarize_tower.py`, `tests/test_summarize_config.py`).
- **Exceedance (ADR-021; `tests/test_summarize_exceedance.py`, v1.5.0):**
  *Green* — known fraction above `c` → exact `P`; in `[0,1]`; non-increasing across a threshold
  sweep; `exceedance(frame,[c])` ≡ `collapse(frame, exceedance_reducer(c))` value; **distribution-agnostic
  onset — `P(Y > 0)` on a zero-inflated / multimodal cell equals the nonzero-draw fraction**
  (substantiates the §3 "robust where the tower is weakest" claim, C-34). *Beige* — `S=1`; threshold
  below min → `1.0`, above max → `0.0`; FeatureFrame leading axes; **integer-count `P(Y ≥ k)` via
  `pass k−1`**. *Red* — threshold exactly equal to a draw pins **strict `>`** (the tie is excluded); a
  NaN draw **raises**; empty thresholds raise; `P(>−inf)=1`, `P(>+inf)=0`; **aggregate composition
  (C-49) — `exceedance` on an `aggregate_distributions(...)` frame yields `P(Σ > c)`, and naive per-cell
  exceedances do NOT recover it (the analogue of the tower's `HDI(aggregate) ≠ sum(HDI)` joint-sampling
  guard).**
- **Expected shortfall (ADR-022; `tests/test_summarize_expected_shortfall.py`, v1.6.0):**
  *Green* — known tail mean → exact value (e.g. worst-1-of-4 draws); `min ≤ ES ≤ max`; **non-decreasing
  as the tail deepens**; `ES(t) ≥ the (1 − t) quantile`; `ES(t=1)` == the mean of all draws. *Beige* —
  `S=1` (ES == that draw); `⌈t·S⌉` rounding (e.g. `t=0.01, S=100 → k=1 == max`, the documented
  small-tail caveat); FeatureFrame leading axes + TargetFrame parity. *Red* — a NaN draw **raises** (not
  a NaN/garbage worst-case, C-56); empty `tails` and any `t ∉ (0,1]` **raise**; **aggregate composition
  (C-55) — `expected_shortfall` on an `aggregate_distributions(...)` frame yields the worst-case of the
  *summed* posterior, and is not recoverable from per-cell ES.**

---

## 11. Evolution Notes

- New estimators are additive. The charter (ADR-017) bounds what may be added — reject
  IO, domain data, scoring, reconciliation, plotting.
- The canonical tower grid (ADR-019) is a **fixed constant, not a parameter** — a
  different grid would be a *new* function, never a tunable density (which would break the
  reproducibility law). A fully-consistent convergent mode remains #89.
- **v1.3.0 (register C-45):** the tower summary is **distribution-agnostic** — the
  count-domain `max <= 1` magnitude zeroing was removed as a default (zero-inflation is read
  off the `tip_mass`-floor density), leaving an **optional, off-by-default** `zero_cutoff`
  opt-in for count consumers. The zero policy is the consumer's, not a leaf default.
- **Threshold exceedance (ADR-021):** `exceedance`/`exceedance_reducer` shipped additively in
  v1.5.0; `CONFORMANCE_FLOOR` stays `1.0.0`. Deliberately deferred, reversible extensions — an
  `inclusive`/`≥` flag (D-08), a `nan_policy='skip'` (D-07), and **relative/reference-frame
  thresholds** (the "exceed the baseline / last period" deterioration story) — to be added only when
  a concrete consumer proves the need.
- **Worst-case expected shortfall (ADR-022):** `expected_shortfall` ships additively in v1.6.0;
  `CONFORMANCE_FLOOR` stays `1.0.0`. It lives in its **own module** (`expected_shortfall.py`), written
  explicitly — *not* refactored into a shared "tail reducer" with `quantiles`/`exceedance` (the
  duplication is shallow and the concerns change independently — WET before DRY; CCP/CRP). Best-case
  ships **no code** (low quantile + `exceedance(0)`). Deferred, reversible extensions — a
  lower-tail/`side` mode, an `expected_shortfall_reducer`, `cvar`/`tail_mean` synonyms (D-10).

---

## End of Contract

This document defines the **intended meaning** of `views_frames_summarize`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
