# ADR-021: Threshold exceedance-probability estimator (`exceedance`)

**Status:** Accepted
**Date:** 2026-06-24
**Deciders:** VIEWS platform maintainers
**Consulted:** views-faoapi (grid consumer; `_tower_collapse` consumption pattern), views-reporting (the forthcoming country+grid twin); an eight-lens engineering review (expert-code-review, 2026-06-24, register C-49/C-50/D-07/D-08)
**Informed:** views-evaluation, views-models, views-pipeline-core

> This ADR ratifies the **design** of a new `views_frames_summarize` estimator. No estimator
> code ships with it; the implementation (TDD, `src/views_frames_summarize/exceedance.py` +
> conformance laws + tests) is a separate follow-up epic that conforms to this record.

---

## Context

Downstream consumers turn a posterior into a **decision**, and the decision-relevant summary
is rarely the point estimate — it is a **threshold exceedance probability**: *what is the
chance this cell exceeds a level I act on?* A humanitarian planner pre-positions where
`P(Y > 25)` is high; a contingency-fund manager sizes reserves against `P(country total >
1000)`; an early-warning analyst triages on `P(Y > 0)` — the **onset** probability of *any*
violence. None of these is expressible with the current surface (`map_estimate`, `hdi`,
`quantiles`, `tower_*`), and `P(Y > 0)` is robust exactly where the tower MAP/HDI is weakest:
zero-inflated and multimodal posteriors (register C-34).

**"Exceedance probability" is overloaded.** The source corpus spans four distinct estimators:

1. **Threshold / survival** — `EP(c) = P(Y > c) = 1 − F(c)`. *Book of Statistical Proofs* P466
   (`cdf-probexc`); the catastrophe-modeling Occurrence/Aggregate EP curves (Humphreys/CAS,
   *Exceedance Probability in Catastrophe Modeling*). **This is what we are building.**
2. **Set / "which is the max"** — `φ(Xᵢ) = P(Xᵢ = max over a set)`. *Book* D103 (`prob-exc`);
   Stephan et al. 2009 (NeuroImage, eq. 16); Soch & Allefeld 2016 (Dirichlet EP). A *different*
   cross-entity estimator (argmax over a set), **explicitly out of scope** here.
3. **Exceed-the-maximum (NPI)** — `P(future obs > largest observed)`, distribution-free, censored
   (Mahnashi, Coolen & Coolen-Maturi). A modeling technique, not a posterior summary. Out of scope.
4. **Parameter-estimate EP** — `P(a parameter estimate > c)`, a p-value alternative (Segal 2018).
   Out of scope.

For a platform emitting posterior **predictive samples** per `(time, unit)`, sense (1) is the
operationally dominant one and a natural per-row sample-axis reduction — the same *kind* of value
as a quantile (`quantile = F⁻¹`; `exceedance = 1 − F`). It belongs alongside `hdi`/`quantiles` in
the `views_frames_summarize` sibling (ADR-017), never in the leaf, and stays numpy-only and
distribution-agnostic.

The consumption pattern is already fixed: views-faoapi (`handlers.py` `_tower_collapse`) and
views-reporting (`dataset_statistics.py`) both wrap raw `(N, S)` sample arrays in an ephemeral
`PredictionFrame`, reduce per-row, and serialise scalar columns. Exceedance drops in as
`{var}_prob_exceed_{c}` columns with no new plumbing. Country-level exceedance is *not* a new
operation: build a country frame by summing samples (`aggregate_distributions`), then reduce per
row — `aggregate` *then* `exceedance`.

---

## Decision

Add two public symbols to `views_frames_summarize`, **additively (MINOR)** under the v1 freeze
(ADR-018); `CONFORMANCE_FLOOR` stays `1.0.0`.

- **`exceedance(frame, thresholds, *, block_rows=ROW_BLOCK) -> NDArray[np.float32]`** — per-row
  empirical survival fraction `P(Y > c_k)` for each of `K` thresholds, over the trailing sample
  axis, shape `(N, …, K)`. An **index-aligned numpy array** (the caller holds the index), computed
  vectorized in row-blocks — the same shape and memory discipline as `quantiles` (`interval.py`).
- **`exceedance_reducer(threshold) -> Reducer`** — a factory returning a `collapse`-compatible
  reducer, so the single-threshold → `(N, …, 1)` **frame** path is
  `collapse(frame, exceedance_reducer(c))`. One private core carries the direction/NaN policy;
  both symbols use it, so a consumer never re-implements `np.mean(samples > c)` and the `>`/NaN
  convention cannot diverge across repos.

**Geography-blind, per-row only.** "Unit exceedance" is a *row*; whatever a frame's rows represent
(grid cell or country) is the level. The estimator never aggregates. **Country exceedance =
`aggregate_distributions(frame, mapping, target_level)` → `exceedance` per row** — composition of
existing pieces; no aggregate variant and no occurrence-vs-aggregate fork in the estimator
(ADR-014 keeps geography out of the summarizer).

### Decided properties (source of truth)

- **Thresholds are a REQUIRED per-call argument, with no default, and are not in config.** They are
  an **input** (*what* the caller asks of the distribution), not an **algorithm tunable** (*how* the
  reduction behaves) — the same line `config.py` already draws for `masses`. The precedent is
  `quantiles(frame, qs)`, whose `qs` is likewise default-free. *(Note, stated honestly: the frozen
  estimators are not uniformly default-free — `hdi(mass=0.9)` and
  `map_estimate(bins=100, zero_mass_threshold=0.3)` carry algorithm-parameter defaults. We match
  `quantiles` specifically, because thresholds are an input, not a tunable.)* Thresholds are expressed
  in the **frame's own units**; level-dependence (`P(>25)` means different things at grid vs country)
  is handled by passing different thresholds per single-level frame — a single global default
  structurally could not.
- **Strict `>`** (settles D-08). The survival-function convention `1 − F(c) = P(X > c)`; it makes
  `P(Y > 0)` = "any violence" well defined (`≥ 0` would be the useless `1`). A **fixed contract, not a
  config knob** — a tunable direction would let two callers silently disagree on what "exceed" means.
  For integer counts wanting `P(Y ≥ k)`, pass `k − 1`. An `inclusive`/`≥` flag is **deferred** (a
  reversible MINOR if a consumer needs it).
- **NaN: fail loud** (settles D-07; mitigates C-50). Any NaN in a reduced row raises `ValueError`. A
  naive `np.mean(v > c)` evaluates `NaN > c` as `False` and would silently count NaN draws as
  "not exceeding," biasing `P(Y > 0)` *downward* on the flagship metric. This is deliberately stricter
  than the lax NaN posture of `hdi`/`quantiles`, because exceedance's failure is a silent wrong
  *probability*, not a visibly-NaN bound. A `nan_policy='skip'` (skip-and-renormalise) is **deferred**.
- **No default or named thresholds, ever, and no risk tiers.** The package ships the *mechanism*; the
  *policy* (which thresholds, per stakeholder/level) lives in the consumer/API repos. The canonical
  VIEWS sets — **25 / 100 / 1000** fatalities at country level, **5 / 25** at grid — are recorded here
  and in the CIC as **documentation / reference only**, never an executable default. (cf. ADR-017
  "it is not evaluation"; and the C-45 lesson — a count-magic-number does not belong in a
  domain-agnostic leaf.)
- **Conformance laws** (added with the implementation): for any frame, `exceedance ∈ [0, 1]`;
  **non-increasing in threshold**; `P(> −inf) = 1`; `P(> +inf) = 0`.

---

## Rationale

`P(Y > c)` is a posterior **summary** of the same kind as a quantile — a point on the survival
curve — so it is in-charter for `views_frames_summarize` (ADR-017) and out-of-charter only if it
acquires *policy* (default thresholds, named risk tiers), which it deliberately does not. Keeping it
geography-blind and aggregation-free is the *simple* (un-braided) design: threshold-evaluation is not
complected with aggregation or with geography, and country exceedance falls out of composing the
existing `aggregate_distributions`. Two of the contested decisions are *contract*, not implementation
— strict `>` and fail-loud NaN — so they are fixed here, where they are cheap, rather than discovered
as breaking changes after the wire format is in use. Everything else (an `≥` flag, a `nan_policy`,
per-row/relative thresholds, an EP-curve helper) is a reversible additive MINOR and is deferred.

---

## Considered Alternatives

### Alternative A: thresholds live in the views-frames config (a default triple)
Put `25 / 100 / 1000` in `TOWER_CONFIG` (or a sibling), overridable downstream.
- **Pros:** matches the fail-loud, no-magic-numbers config discipline; a bare call "just works".
- **Cons:** thresholds are a *domain input*, not an *algorithm tunable* — the category `config.py`
  explicitly keeps out (`masses`). It re-introduces a **count-magic-number into a domain-agnostic
  leaf** — the exact mistake removed in v1.3.0 (register C-45). And a single global default
  **cannot** be both grid-appropriate (`5/25`) and country-appropriate (`100/1000`) at once, so it
  fails the very level-variation it is meant to serve.
- **Reason for rejection:** wrong home for the value; required-no-default (the `quantiles(qs)` form)
  is the stronger expression of "no silent default," and the canonical numbers live as documentation
  plus per-API config.

### Alternative B: build aggregation into the estimator (`exceedance(..., level=)`)
Have `exceedance` aggregate to a target level itself.
- **Reason for rejection:** complects geography + aggregation + summary into one function; violates
  ADR-014 (geography injected, not embedded). Composition (`aggregate_distributions` → `exceedance`)
  is decomplected and reuses an existing primitive.

### Alternative C: no new function — callers pass their own reducer to `collapse`
`collapse(frame, lambda v, axis=-1: np.mean(v > c, axis=axis))`.
- **Reason for rejection:** there is then **no canonical home** for the direction (`>`) and NaN
  policy, so each consumer re-rolls it and they drift — precisely the silent-onset-deflation footgun
  (C-50) and the "consumers diverge on convention" failure the typed contracts exist to prevent. The
  `exceedance_reducer` factory keeps the `collapse`-to-frame ergonomics *with* one shared policy.

### Alternative D: ship an `inclusive`/`≥` flag now · Alternative E: ship a `nan_policy='skip'` now
- **Reason for rejection (both):** YAGNI for v1 and fully reversible — each is a non-breaking additive
  MINOR if a concrete consumer proves the need. Shipping them now widens the contract before it is
  exercised. Deferred, not foreclosed.

---

## Consequences

### Positive
- The decision-relevant summary (onset and threshold risk) is finally expressible, distribution-agnostic
  and robust where the tower is weakest (C-34); it drops into the existing `(N,S)`-frame consumption
  pattern as scalar columns with no new plumbing.
- Country/aggregate exceedance needs **no new estimator** — `aggregate_distributions` → `exceedance`.
- The leaf-family stays a transport/summary layer: mechanism here, policy (thresholds, tiers) in the
  consumer.

### Negative
- Exceedance is **strictly less composable** than HDI: `P(Σ > C)` is unrecoverable from per-cell
  `P(Yᵢ > cᵢ)`, so it *must* be computed on an already-aggregated frame. Documented as a CIC
  failure-mode (C-49); the joint-sample correctness obligation lands on `aggregate_distributions`
  and the consumer, which the estimator cannot verify.
- A second contract surface to maintain, and two public symbols rather than one (accepted — they share
  one policy core).

---

## Implementation Notes

- **Family & files:** a new `src/views_frames_summarize/exceedance.py`; export `exceedance` and
  `exceedance_reducer` from `__init__.py` `__all__`. It joins the `hdi`/`quantiles` family
  (per-call args, **no config**), not the tower family.
- **Reuse:** `_common.py` `block_apply` + `ROW_BLOCK` for memory-bounded blocking (register C-25);
  `rebuild` via `collapse` for the frame path. Mirror `quantiles`' structure in `interval.py`
  (`vals[..., :, None] > thr`, mean over the sample axis, float32 cast, blocked).
- **Fail-loud guards:** raise `ValueError` on any NaN in the reduced values (C-50) and on empty
  `thresholds` (no silent `(N, …, 0)`); ADR-008/009.
- **Conformance:** extend `assert_summarizer_contract` (`conformance.py`) with the `[0,1]` / monotone /
  `±inf` laws.
- **Versioning:** additive ⇒ MINOR (target 1.5.0); `CONFORMANCE_FLOOR` unchanged at `1.0.0`.
- **No sibling-repo changes.** Threshold policy and any aggregate-coherence check live in the
  consumer/API repos.

---

## Validation & Monitoring

- **C-49 (aggregate tail / joint samples):** the watch-item. Per-row exceedance is correct for a level
  only if each row's `S` samples are the true joint posterior for that unit — automatic for a
  natively-modeled level; for a level synthesised by summing a finer one it requires jointly-drawn
  (shared-draw-index) samples, which sample-space reconciliation preserves. The estimator does not
  verify this; it is an upstream guarantee, contracted on the aggregation boundary and the consumer.
- **C-50 (silent NaN onset deflation):** mitigated by the fail-loud NaN guard above; an implementation
  test must assert it raises rather than returning a deflated probability.
- **Failure mode that would reopen this ADR:** a consumer demonstrates a need that the per-call,
  caller-supplied-threshold, strict-`>`, fail-loud design cannot express without a breaking change
  (e.g. an unavoidable `≥` or `nan_policy` requirement) — handled by the deferred additive extensions,
  not a redesign.

---

## Open Questions

- The `≥`/`inclusive` flag (D-08 deferred half), `nan_policy='skip'` (D-07 deferred half), and
  **relative/reference-frame thresholds** (the "exceed the baseline / last period" deterioration story)
  are deferred additive MINORs — to be activated only when a concrete consumer proves the need.
- Whether a published **EP-curve** helper (a dense threshold sweep returning the survival curve) is
  worth a named symbol, or remains "pass many thresholds." Deferred.

---

## References

- **Corpus (sense 1 — what we build):** *The Book of Statistical Proofs*, P466 `cdf-probexc`
  (`Pr(X>x) = 1 − F_X(x)`); "Exceedance Probability in Catastrophe Modeling" (Casualty Actuarial
  Society — Occurrence/Aggregate EP curves).
- **Corpus (out of scope — distinct senses):** *Book* D103 `prob-exc`, Stephan et al. 2009 (NeuroImage,
  eq. 16), Soch & Allefeld 2016 (Dirichlet EP) — the "which is the max" set sense; Mahnashi, Coolen &
  Coolen-Maturi (NPI exceed-the-maximum); Segal 2018 (parameter-estimate EP).
- **views-frames:** ADR-017 (summarisation is a sibling; "it is not evaluation"), ADR-014 (geography
  injected, not embedded), ADR-018 (v1 freeze; additive = MINOR), ADR-019 (the tower family + the
  `masses` input-not-tunable line), register **C-45** (no count-magic-number in the leaf), **C-49**
  (aggregate tail / joint samples), **C-50** (silent NaN onset deflation), **D-07** (NaN policy),
  **D-08** (threshold direction); `src/views_frames_summarize/{interval,collapse,aggregate,_common}.py`.
- **Consumers:** views-faoapi `handlers.py` (`_tower_collapse`); views-reporting
  `dataset_statistics.py`; estimator-coherence cluster GH #89.
