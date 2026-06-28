
# ADR-024: Principled joint probabilistic reconciliation — design direction & deferral

**Status:** Accepted (design direction; implementation deferred)
**Date:** 2026-06-27
**Deciders:** VIEWS platform maintainers
**Consulted:** views-models (the country/grid model owner), views-postprocessing (the C-37 lineage)
**Informed:** views-pipeline-core, views-evaluation

---

## Context

`views_frames_reconcile.reconcile_proportional` makes grid (`pgm`) forecasts sum to their
country (`cm`) total by **top-down proportional disaggregation, applied per posterior draw**:
within draw `s`, each grid cell keeps its relative share and the cells are rescaled so they
sum to draw `s` of the country total. It is a *faithful, parity-proven port* and the right
**pragmatic baseline** — but its own docstring names it "a pragmatic per-draw approximation,
not principled joint probabilistic reconciliation."

Two things make it an approximation, and they are *not* fixed by more samples:

1. **No shared draw identity.** Pairing grid-draw `s` with country-draw `s` is only meaningful
   if the two are *the same scenario*. When the grid and country models are trained
   **independently** (the current platform reality — `rusty_bucket` and a separate country
   model), draw index `s` carries **no shared meaning** across them; the pairing is arbitrary,
   even though the arithmetic runs and the output looks reasonable.
2. **Dependence is discarded.** Proportional rescaling ignores the cross-cell error structure
   a principled reconciler exploits (MinT) and does not reconcile the *joint* distribution
   (probabilistic reconciliation) — so the reconciled joint tails (the thing FAO-style
   decisions key on) are not guaranteed calibrated.

This matters **now** because the reconciliation path is live (pipeline-core #233 wired the
frames-native ensemble) and a UN/FAO deliverable consumes reconciled grid→country draws. We
need the upgrade path *written down* — what "principled" requires and when it's worth
building — so the known approximation is **planned debt, not silent debt**. This ADR is the
design; it deliberately ships **no code**.

---

## Decision

1. **The draw-identity contract is the gate.** Principled joint reconciliation requires a
   defined notion of *"grid-draw `s` and country-draw `s` are the same scenario."* That holds
   only when the grid and country posteriors come from a **shared generative process** — shared
   ensemble members / shared seeds, or an explicit **copula coupling**. Absent a declared
   shared draw-identity, per-draw pairing is not principled and must not be presented as such.

2. **When built, it is a new sibling module, not a change to `proportional`.** Consistent with
   ADR-023's open question, the principled method (probabilistic reconciliation —
   Panagiotelis et al. 2023; or MinT — Wickramasuriya et al. 2019) lands as a **new module in
   `views_frames_reconcile`** behind the existing injected-mapping interface. `proportional`
   stays the documented baseline; nothing about its parity-frozen behaviour changes.

3. **Implementation is deferred** until *both* preconditions hold: (a) a consumer needs
   calibrated **joint** country tails (proportional's marginal-rescale is demonstrably
   insufficient for its decision), **and** (b) the country model can **supply what the method
   needs** — either draws carrying a declared shared draw-identity, or a covariance/coupling the
   reconciler can consume. Until then, per-draw proportional remains the shipped method,
   labelled as the approximation it is (the `reconcile_result` mode `aligned-draws`, D-12).

**In scope:** the design direction, the draw-identity contract, and the deferral preconditions.
**Out of scope:** any implementation; choosing the *specific* method (that is the future epic's
call, driven by what the country model can supply); the country model's own changes
(views-models); changing `proportional`.

---

## Rationale

Correctness-of-method is a *country-model-shaped* problem, not a reconciler-shaped one: the
reconciler cannot manufacture a joint distribution that the upstream models never shared. So the
honest, lowest-regret move is to **name the precondition** (draw-identity / coupling) and defer
until it can be met, rather than ship a more elaborate method that still pairs independent draws
and merely *looks* principled. WET-before-DRY's sibling logic applies again: keep the baseline,
add the principled method beside it only when its inputs exist — never by mutating the
parity-frozen `proportional`.

---

## Considered Alternatives

### Alternative A: keep proportional as the only method (status quo)
- **Pros:** simplest; parity-proven; no new inputs required.
- **Cons:** information-losing; per-draw pairing of independent draws is not principled; joint
  tails not guaranteed calibrated.
- **Revisit when:** a consumer's decision provably needs calibrated joint country tails.

### Alternative B: MinT (trace-minimization; Wickramasuriya 2019)
- **Pros:** minimum-variance unbiased *linear* reconciliation; well-established.
- **Cons:** needs an estimate of the base-forecast **error covariance** the platform does not
  currently produce; still a point/linear view, not a full joint posterior.
- **Revisit when:** reconciliation residuals / a covariance estimate become available.

### Alternative C: copula / shared-ensemble coupling
- **Pros:** models grid↔country dependence explicitly; can deliver a calibrated joint.
- **Cons:** heaviest; needs a fitted copula or a genuinely shared ensemble — a country-model
  contract change.
- **Revisit when:** the country and grid models share members, or a coupling is fitted upstream.

### Alternative D: marginal (non-per-draw) reconciliation
- **Pros:** honest when draws are *not* shared — reconcile the country **marginal**, don't fake
  per-draw identity.
- **Cons:** loses the per-draw coherence downstream summaries (joint `expected_shortfall`, etc.)
  rely on.
- **Revisit when:** a consumer wants marginal-only coherence.

---

## Consequences

### Positive
- The known approximation becomes **planned debt with a named precondition**, not a silent one.
- The upgrade path is fixed (new sibling module, injected interface unchanged) so a future epic
  is scoped, not exploratory.
- Keeps `proportional` parity-frozen and the leaf untouched.

### Negative
- No improvement now; per-draw proportional persists as the shipped method (documented).
- The hardest dependency (a shared draw-identity / coupling from the country model) is *upstream*
  and outside this repo's control — the deferral may be long.

---

## Implementation Notes

**No code in this ADR.** When the preconditions are met, a future implementation epic:
- adds a sibling module under `src/views_frames_reconcile/` (e.g. `probabilistic.py`) behind the
  same injected-mapping interface; does **not** modify `proportional`/`grouping`;
- requires the country model (views-models) to declare the draw-identity / supply the coupling —
  a cross-repo contract, gated there;
- ships its own parity/validation suite (below) and is additive/MINOR; `CONFORMANCE_FLOOR` stays
  `1.0.0`.

This ADR's only repo change is documentation: `proportional.py`'s docstring is corrected to point
at **this ADR** (the prior "tracked as C-37" was ambiguous — views-frames' own C-37 is an
*unrelated, resolved* protocol-conformance item; the principled-reconciliation lineage is
*views-postprocessing* C-37). Tracked as register **C-62**.

---

## Validation & Monitoring

A principled implementation must demonstrate what proportional cannot: **calibrated joint
coverage** — e.g. the reconciled country total's predictive intervals cover at their nominal
rate against held-out actuals, and the joint grid→country dependence is preserved (not just the
per-cell marginals). That coverage check (on synthetic data with a known joint truth) is the
acceptance gate for the future epic, and the signal that would justify lifting the deferral.

---

## Open Questions

- **Which method** (probabilistic reconciliation vs MinT vs copula) — undecided on purpose; it
  depends on what the country model can supply (draws + identity, or a covariance, or a coupling).
- **Where draw-identity is declared** — a country-model (views-models) contract; what does the
  reconciler require as its injected interface?
- **Is marginal reconciliation (D) a useful interim** for consumers that only need marginal
  coherence, shipped before the full joint method?

---

## References

- Wickramasuriya, Athanasopoulos & Hyndman (2019), *Optimal forecast reconciliation* (MinT).
- Panagiotelis, Gamakumara, Athanasopoulos & Hyndman (2023), *Probabilistic forecast
  reconciliation*.
- Hyndman et al. (2011), *Optimal combination forecasts for hierarchical time series*.
- `src/views_frames_reconcile/proportional.py` (the per-draw approximation / C-37 anchor);
  ADR-023 (reconciliation sibling; Open-Questions deferring this as a future sibling module).
- GH #145 (this story), #142 (epic); views-pipeline-core #233 / C-198 / C-200b; views-postprocessing
  C-37 (the cross-repo principled-reconciliation lineage); register C-62, D-12.
