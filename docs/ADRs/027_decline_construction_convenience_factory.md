# ADR-027: Frame construction stays two-step — the convenience factory is declined

**Status:** Accepted
**Date:** 2026-07-31
**Deciders:** VIEWS platform maintainers
**Consulted:** expert-code-review (2026-06-24, GH #113, all eight lenses); pipeline-core owner exchange; `review-rr prioritize` (2026-07-31, Epic #208 / S1 #209)
**Informed:** views-pipeline-core, views-baseline, views-hydranet, views-datafactory

---

## Context

Constructing a `PredictionFrame` takes two steps: build the index, then build the frame.

```python
index = SpatioTemporalIndex(time=months, unit=grid_cells, level=SpatialLevel("pgm"))
frame = PredictionFrame(predictions, index)
```

**#113** (filed 2026-06-24, during the platform-wide views-frames adoption) asked the leaf to
collapse that into one step — a free function `build_prediction_frame(y_pred, time, unit, level,
metadata=None)` — so engine repos would not each have to know that a separate index object exists,
and so views-baseline's local duplicate (`views_baseline/model/helpers.py`) could be retired.

The **shape** was settled and the **need** was not. Register disagreement **D-09** rejected the
free-function form in favour of a `@classmethod PredictionFrame.from_arrays(...)` — matching the
leaf's only construction-helper convention (`from_2d`, `load`), single-homing construction, the
smaller frozen surface, the canonical Factory Method — and recorded the free-function alias as
*strictly dominated*. Implementation was then deprioritized behind the engine migration
(views-hydranet #137, views-baseline #21) and never happened.

Thirteen months of evidence accumulated in the meantime:

- **Nobody was blocked.** #113's own text states engines *"can migrate today by constructing
  `SpatioTemporalIndex` directly (the hydranet/baseline issues do this)"* — and they did.
- **The cost of the two-step form is one line and one import**, at the end of a model run. It is not
  a correctness hazard, a performance cost, or an ergonomics cliff.
- **The cost of the one-step form is permanent.** Under **ADR-018** the v1 surface is frozen:
  anything added can only be removed by a platform-wide MAJOR. A convenience method is a permanent
  commitment bought with a transient inconvenience.
- **Three register concerns existed solely to guard a thing that was never built** — C-52
  (construction-convenience accretion, the "camel's nose" ADR-001 names as this leaf's #1 existential
  failure mode), C-53 (two frozen construction paths can diverge), C-54 (#113's Definition-of-Done,
  read literally, pulls views-baseline's `value_fn` + entity×time grid loop — an ADR-001 consumer
  edge — into the leaf). All three read *"awaiting the #113 decision"*.

A decision of this kind — *should the frozen public surface gain a new permanent method* — belongs in
an ADR. Until now it lived only as a disagreement entry in the risk register, which is why it could
sit undecided: nothing forced it to conclude.

## Decision

**Decline #113. Frame construction stays two-step.** No `build_prediction_frame`, no
`PredictionFrame.from_arrays`, no `src/views_frames/factory.py`. The frozen surface does not grow.

`SpatioTemporalIndex` is not an implementation detail to be hidden — it is the identifier contract,
and constructing it explicitly is the caller stating which rows their values correspond to. That is
the one thing a data-contract leaf should make callers say out loud (**ADR-003**: declaration over
inference).

**The design survives this decision.** If the need is ever receipted, the answer is already worked
out and does not need re-litigating — D-09's form, under binding constraints:

- a `@classmethod` on `PredictionFrame`, **never** a free function and **never** a `factory.py`;
- **zero own logic** — pure delegation to `SpatioTemporalIndex(...)` + `__init__`, so a future
  additive identifier (ADR-013) flows through without a signature edit (this is what neutralises C-53);
- **singular** — `PredictionFrame` only; no reflexive symmetry onto `Feature`/`TargetFrame`
  (ISP/CRP, and ADR-011's honesty-over-symmetry);
- keyword-only `time`/`unit`/`level`; no alias.

**What would reopen this:** a consumer presenting a concrete site where the two-step form is
genuinely inadequate — not merely longer. Verbosity alone is not a receipt. This mirrors the
receipt-first posture ADR-026 took on bounded-memory densification and ADR-024 on principled
reconciliation.

## Alternatives considered

- **Ship `PredictionFrame.from_arrays` now** (D-09's settled form) — rejected on cost/benefit, not on
  design: the design is sound, the need is absent. Shipping it would add a permanent symbol, make the
  pending release a functional MINOR rather than a patch, and leave C-52's accretion pressure live
  (the first follow-up request — accept a dict, infer the level, take a DataFrame — is what the guard
  exists for). Declining is **reversible**; shipping is not.
- **Ship the free function `build_prediction_frame`** (#113 as filed) — rejected already by D-09 and
  rejected again here: it does not single-home construction, it is the larger frozen surface, and
  every consumer already imports `PredictionFrame`.
- **A `src/views_frames/factory.py` collecting construction helpers** — rejected permanently. C-52's
  trigger names this file explicitly; an open module accretes loosely-related helpers in a way a
  classmethod does not (ADR-001's "convenience abstractions that hide meaning" non-entity).
- **Leave #113 open and undecided** — rejected. This is the status quo that produced three register
  entries in indefinite limbo. An undecided proposal is not free: it consumes governance attention on
  every review cycle and makes the register report work that will never happen.
- **Retire views-baseline's local helper into the leaf** (#113's DoD read literally) — rejected;
  that helper is a **domain grid-builder** (loops a `value_fn` over entity×time), an ADR-001 consumer
  edge. It stays in views-baseline. Only its innermost two-line construction was ever in scope, and
  that is exactly what is being declined.

## Consequences

- **Consumers keep the two-line form.** No migration, no deprecation, no consumer action of any kind —
  the outcome is that nothing changes.
- **Register C-52, C-53 and C-54 resolve** (2026-07-31, this ADR). The concerns were guards on an
  unbuilt thing; with the thing declined, the guards have nothing to guard. C-52's *trigger* survives
  in spirit through this ADR's "what would reopen this" clause.
- **The frozen surface does not grow**, and the accretion pressure ADR-001 warns about is answered
  with a written precedent rather than a case-by-case judgment. Future construction-convenience
  requests can be closed by citing this ADR.
- **views-baseline keeps its helper.** Cross-repo, owner-only; nothing in this decision obliges any
  sibling repo to change (D-04's boundary discipline).
- **The decision is now findable.** It was previously reachable only through a register disagreement
  entry; a contributor asking "why can't I build a frame in one line?" now gets an answer from the
  ADR index instead of rediscovering the debate.
- Docs-only; no `src/` change; `CONFORMANCE_FLOOR` stays `1.0.0`.
