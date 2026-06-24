# ADR-022: Worst-case scenario summary — the `expected_shortfall` tail mean

**Status:** Accepted
**Date:** 2026-06-25
**Deciders:** VIEWS platform maintainers
**Consulted:** the best/worst-case design discussion (2026-06-25); the exceedance precedent (ADR-021)
**Informed:** views-faoapi, views-reporting (consumers of `views_frames_summarize`)

> This ADR ratifies the **design** of a `views_frames_summarize` estimator. No estimator code
> ships with it; the implementation (TDD, `src/views_frames_summarize/expected_shortfall.py` +
> conformance laws + tests) is a separate follow-up epic (target v1.6.0) that conforms to this record.
>
> **Implemented in v1.6.0 (2026-06-25, Epic 10 / GH #122).** `expected_shortfall` shipped exactly as
> ratified — required no-default tail levels in `(0,1]`, upper-tail only, never `max`, fail-loud on
> NaN/empty/out-of-range, geography-blind, with the `[min,max]` / monotone-deepening / `ES ≥ (1−t)`
> quantile conformance laws. Register **C-55** and **C-56** Resolved; `CONFORMANCE_FLOOR` stays `1.0.0`.

---

## Context

Consumers want two scenario summaries the current surface does not name directly: a **best-case**
and a **worst-case** per cell. Both are ends of the per-cell posterior — i.e. a low and a high
quantile — so the question is never "how do we build min/max," but *which* points, and *how stable*.

**Best case needs no new estimator.** For fatalities the lower bound is **0 by construction** in the
common zero-inflated cell, so a low quantile (`quantiles(frame, [0.005])`) returns 0 — "best case is
no violence." The genuinely informative case — *the model puts no mass at zero* — is already
expressible two ways the platform has shipped: the low quantile is itself the signal (a `> 0` value
means "even the best case is violent here"), and **`exceedance(frame, [0])` = `P(Y > 0)`** says
directly whether zero is plausible. So best-case = a low quantile + the onset probability — no code.

**Worst case must not be `max`.** `max` is a single extreme **order statistic** — the highest
sampling variance of any summary, and worst for heavy-tailed posteriors built from *many* uncertainty
sources at once (MC-dropout × a distributional head × an ensemble all feed one sample axis). It does
not reproduce across re-samples; it is whichever single draw happened to be most extreme. A robust,
**coherent** worst-case is needed instead.

## Decision

Add **one** estimator, **`expected_shortfall`** (the tail mean / CVaR), to `views_frames_summarize`,
**additively (MINOR)** under the v1 freeze (ADR-018); `CONFORMANCE_FLOOR` stays `1.0.0`. **Best-case
ships no code** — it is documented guidance (a low quantile + `exceedance(frame, [0])`).

- **`expected_shortfall(frame, tails, *, block_rows=ROW_BLOCK) -> NDArray[np.float32]`** — for each
  upper-tail fraction `t` in `tails`, the **mean of the worst `⌈t·S⌉` draws** per row (the average of
  the worst-case scenarios). Shape `(N, …, K)`, an index-aligned numpy array (the caller holds the
  index), vectorized in row-blocks — the same shape/role family as `quantiles` and `exceedance`.

### Decided properties (the source of truth)

- **Upper tail only.** Worst-case = high fatalities = the right tail. No lower-tail / "best-case" mode
  (that is the low quantile + `exceedance(0)`, which ship already — CRP: do not force a best-case
  symbol no one reuses).
- **`tails` required, no default, not in config.** A stakeholder **input** in `(0, 1]` (e.g. `0.01` =
  "the worst 1% of scenarios"), exactly like `exceedance`'s thresholds and `quantiles`' `qs`. There is
  **no** baked-in "worst case = X%" (the level is policy, the consumer's — ADR-021's precedent).
- **Robust by construction.** Averaging a *set* of tail draws (one freak draw moves it by ~`1/k`, not
  fully) is the whole point; **`max` is never offered.** Expected shortfall is also a **coherent**
  (subadditive) risk measure — the worst-case of a sum is ≤ the sum of worst-cases — unlike `max` or a
  raw quantile, which matters for a risk platform.
- **Fail loud** on: empty `tails`; any `t ∉ (0, 1]` (a tail with no samples); any **non-finite** draw —
  NaN **or ±inf** (numpy sorts NaN/`+inf` last, so a naive top-`k` mean silently selects them and the
  tail mean is contaminated to NaN/`inf` — the C-56 guard, the C-50 lesson; the guard is `np.isfinite`,
  widened by the falsify audit 2026-06-25).
- **The documented caveat — the extremeness-vs-stability tradeoff.** The deeper the tail, the fewer
  effective samples support it, so *any* worst-case estimator gets shakier. A `t` so small that
  `⌈t·S⌉` selects only a handful of draws re-approaches `max`'s volatility. The CIC states "pick
  `t ≳ 5/S`"; the consumer chooses the level knowingly.
- **Conformance laws** (added with the implementation): `min ≤ ES(t) ≤ max`; **non-decreasing as the
  tail deepens** (`ES(t₁) ≥ ES(t₂)` for `t₁ ≤ t₂`); and `ES(t) ≥ the (1 − t) quantile` (the tail mean
  dominates its VaR).
- **`CONFORMANCE_FLOOR` stays `1.0.0`** — additive surface (ADR-018).

### WET before DRY (the structure)

`expected_shortfall` lives in its **own module** `src/views_frames_summarize/expected_shortfall.py`,
written **explicitly** — it does **not** share a "tail-reducer" abstraction with `quantiles` /
`exceedance`. It reuses only the genuinely-stable low-level primitives (`block_apply`, `ROW_BLOCK`,
`AnyFrame` from `_common.py`). Three estimators that each sort/reduce the sample axis is *not* a signal
to extract a shared reducer — the duplication is shallow and the concerns change independently (CCP /
CRP). One concept per file; the package keeps screaming its responsibilities.

## Considered Alternatives

### Alternative A — `max` (the literal worst draw)
- **Reason for rejection:** the highest-variance summary; not reproducible across re-samples; degenerate
  for the heavy-tailed, multi-source posteriors this platform produces. The exact problem this ADR exists
  to avoid (D-10).

### Alternative B — a high quantile via the existing `quantiles`, ship no new code
- **Pros:** robust, zero new surface; `quantiles(frame, [0.99])` already works.
- **Reason for rejection (as the *sole* answer):** a point quantile is more stable than `max` but **not
  a coherent risk measure**, and averaging the tail (ES) is strictly more stable at the same level. The
  high-quantile path is **documented as the lighter alternative**, not the principled worst-case.

### Alternative C — a named best/worst-case *pair* function
- **Reason for rejection:** best-case is a low quantile + `exceedance(0)` (both shipped); pairing it with
  the worst-case forces a symbol no consumer reuses (CRP) and conflates two unrelated stabilities.

### Alternative D — a `side`/lower-tail mode · an `expected_shortfall_reducer` · `cvar`/`tail_mean` synonyms
- **Reason for rejection:** YAGNI and reversible — each is a non-breaking additive MINOR if a concrete
  consumer proves the need. Deferred, not foreclosed.

## Consequences

### Positive
- A robust, coherent, reproducible-ish worst-case that pairs with `exceedance` (the conditional-magnitude
  companion to the threshold probability — the catastrophe-modeling OEP→AEP framing); best-case needs no
  code; the leaf-family stays mechanism, not policy (the level is the consumer's).

### Negative
- A tail mean is *more* sensitive to cross-cell dependence than a tail probability, so aggregate worst-case
  on incoherently-summed samples is silently wrong (**C-55**, mitigated by the geography-blind compose
  pattern + a documented joint-sample obligation).
- One more symbol on a frozen surface; accepted — it is the one genuinely-new worst-case statistic.

## Implementation Notes

- **Own module:** `src/views_frames_summarize/expected_shortfall.py`; export `expected_shortfall` from
  `__init__.py` `__all__`. It joins the `hdi`/`quantiles`/`exceedance` family (per-call args, **no
  config**).
- **Reduction:** per block, sort the sample axis, take the mean of the top `k = ⌈t·S⌉` draws → `(…, K)`;
  block-applied (`block_apply` / `ROW_BLOCK`, register C-25); float32; index-aligned.
- **Fail-loud guards:** raise `ValueError` on empty `tails`, on `t ∉ (0, 1]`, and on any non-finite
  value — NaN or ±inf — in the reduced values (`np.isfinite` guard, C-56; widened by the falsify audit
  2026-06-25).
- **Conformance:** extend `assert_summarizer_contract` with the `[min, max]` / monotone / `≥ (1−t)
  quantile` laws.
- **Versioning:** additive ⇒ MINOR (target v1.6.0); `CONFORMANCE_FLOOR` unchanged at `1.0.0`.
- **No sibling-repo changes.** Which tail level counts as "worst case" lives in the consumer/API repos.

## Validation & Monitoring

- **C-55 (aggregate tail / joint samples):** the watch-item — country worst-case = `aggregate_distributions`
  → `expected_shortfall`; correct only when the summed samples are jointly drawn (an upstream guarantee the
  estimator does not enforce). Proven by an ES aggregate-composition test.
- **C-56 (silent non-finite corruption):** mitigated by the fail-loud `np.isfinite` guard (NaN **and**
  ±inf; widened by the falsify audit 2026-06-25); `test_inf_draw_raises` / `test_nan_draw_raises` assert
  it raises rather than returning a NaN/`inf` worst-case.
- **Failure mode that would reopen this ADR:** a consumer demonstrates a worst-case need the per-call,
  upper-tail, caller-supplied-level design cannot express without a breaking change — handled by the
  deferred additive extensions (D), not a redesign.

## Open Questions

- A lower-tail/`side` mode, an `expected_shortfall_reducer` for the frame path, and `cvar`/`tail_mean`
  synonyms are deferred additive MINORs — activated only when a concrete consumer proves the need.

## References

- The best/worst-case design discussion (2026-06-25); register **C-55** (aggregate tail), **C-56** (NaN),
  **D-10** (worst-case statistic — `max` vs quantile vs ES).
- **views-frames:** ADR-017 (summarisation is a sibling; "it is not evaluation"), ADR-014 (geography
  injected, not embedded), ADR-018 (v1 freeze; additive = MINOR), **ADR-021** (the `exceedance` sibling
  — same per-call-policy, fail-loud, geography-blind pattern this ADR mirrors); `interval.py` (`quantiles`,
  the shape template), `_common.py` (`block_apply`/`ROW_BLOCK`).
- **Domain:** expected shortfall / CVaR as the coherent tail risk measure (catastrophe-modeling OEP/AEP).
