# ADR-020: The `MetricFrame` evaluation-output contract lives in views-evaluation, on the views-frames substrate

**Status:** Accepted
**Date:** 2026-06-24
**Deciders:** VIEWS platform maintainers
**Consulted:** views-reporting (GH views-frames#109; register C-108; ADR-018 render-from-given-data mandate); views-evaluation (emit-side, views-evaluation#21); an eight-lens engineering review (expert-code-review, 2026-06-24)
**Informed:** views-pipeline-core, views-evaluation, views-reporting

---

## Context

views-reporting acquires evaluation metrics by scraping WandB at **render time**
(`get_latest_run().summary`). That fetch-time inversion caused a confirmed production
failure: for a 25-constituent ensemble, 22/25 constituents rendered "not calculated"
because the newest-*created* run was selected rather than the run carrying the metrics.
The cure (views-reporting's ADR-018) is to **receive** a typed evaluation-output contract
through an injected adapter rather than fetch it. views-evaluation is ready to emit such a
contract — a `MetricFrame` — but no such type exists, and GH#109 asks where it should live.

This question was already answered in principle by **C-01** (resolved by-decision) and
**ADR-016/ADR-018**: `MetricFrame`/`EvaluationFrame` are *out of the leaf*; the leaf defines
only the structural index/key protocol such types conform to, and "views-evaluation owns
eval-output vocab" (README §4.2). This ADR **ratifies and operationalises** that boundary
under the new GH#109 driver, specifies the contract's shape and substrate, and records the
two residual risks the decision creates (register **C-46**, **C-47**).

The crux is that a `MetricFrame` is **not** a `(time, unit)` frame. It is keyed by
`(eval_type, target, metric, group_id, partition, level)` — string axes (`target`, `metric`),
an evaluation-granularity axis, and partition/level that are not a spatiotemporal cell. The
leaf's whole spine — `SpatioTemporalIndex` (ADR-012), sibling frames with no base (ADR-011),
injected geography (ADR-014), a frozen v1 surface (ADR-018) — is spatiotemporal by design.

## Decision

**`MetricFrame` is hosted in `views-evaluation`, reusing the views-frames *substrate*
(Option B).** views-frames is **not** generalised to host it.

- `views-evaluation` defines and owns the `MetricFrame` type and its evaluation-specific
  vocabulary (`eval_type, target, metric, group_id, partition, level`), wrapping its existing
  structured `EvaluationReport`.
- views-frames provides the reusable **substrate**: the `FrameMetadata` provenance header
  (ADR-013), the published conformance suite and IO patterns (ADR-016), and the structural
  value-object discipline (float32 values, fail-loud construction, serialise→load round-trip).
- The cross-repo chain — views-frames (substrate) → views-evaluation (emit `MetricFrame`) →
  views-reporting (consume via injected adapter) — is unblocked **without** a v2 change to the
  leaf. The dependency direction is preserved: views-evaluation depends *on* views-frames,
  never the reverse, and the leaf takes on no sibling dependency and stays numpy-only and
  spatiotemporal-scoped.

## Decided properties (the source of truth)

- **No generalised index in the leaf (v1 stays frozen).** ADR-018 freezes the `(time, unit)`
  index surface; generalising it to a non-spatiotemporal key protocol is a MAJOR (v2) change.
  This ADR does **not** open it. Generalising spatiotemporal indexing and evaluation indexing
  into one protocol would complect two genuinely different concerns for one type's benefit.
- **Provenance is split by concern (resolves the C-47 guard).** The evaluation-of-record needs
  provenance `FrameMetadata` lacks. When the extension is made, only **generic** provenance —
  `run_id`, `data_version` — is added to the leaf's `FrameMetadata`, as **optional/MINOR**
  (ADR-013); these are meaningful for `PredictionFrame`/`TargetFrame` too. **Evaluation-specific**
  provenance — `scoring_code_version`, a full-precision `evaluation_timestamp` — stays in
  `views-evaluation`'s `MetricFrame` metadata, so evaluation semantics never leak into the
  generic header (ADR-014/ADR-017).
- **The shared "frame-like envelope" gets one written, versioned authority (mitigates C-46).**
  To prevent the leaf's invariants and views-evaluation's re-asserted ones from drifting, the
  shared envelope (float32 discipline, round-trip identity, optional-only metadata) is captured
  as (i) a reusable, consumer-runnable conformance checker exported by views-frames (the
  conformance suite is already a public artifact, ADR-016), and (ii) an explicit wire schema
  with a `schema_version` marker that both emit and consume validate against. The contract is
  thereby validated against one written specification, not agreed by convention.
- **`CONFORMANCE_FLOOR` stays `1.0.0`.** Nothing in the published structural contract changes;
  the only leaf-side code is the additive `FrameMetadata` extension (a future MINOR), made when
  views-evaluation forces it (ADR-013: add the axis when a concrete consumer needs it).

## Considered Alternatives

### Alternative A — Generalise the index, host `MetricFrame` in the leaf (v2 / MAJOR)

Introduce a non-spatiotemporal `EvaluationIndex` and a generalised `Frame`/index protocol so
`MetricFrame` is a true leaf sibling.

- **Reason for rejection:** disproportionate and irreversible for *this* driver. The proven
  need is for a typed contract to inject, not specifically for a *leaf-hosted generalised-index*
  frame. A breaks the frozen v1 index surface (ADR-018), forces a `CONFORMANCE_FLOOR` bump and a
  coordinated multi-repo merge train (pipeline-core, datafactory, evaluation, reporting, model
  repos) — the class of partially-upgraded-DAG outage that is hardest to roll back — and the
  generalised "index protocol" is likely a shallow over-abstraction whose two implementations
  (integer spatiotemporal alignment vs string-keyed evaluation lookup) share little real
  behaviour. **Revisit-trigger:** reopen A only if a *second* genuinely non-`(time, unit)`
  frame-like type is independently needed across the platform; A remains available then (B does
  not foreclose it).

### Alternative C — Coerce metrics to a `(time, unit)` frame

- **Reason for rejection:** metrics are keyed by `(target, metric, step, …)`, not by a
  spatiotemporal cell; forcing them into `(time, unit)` discards the evaluation semantics. Listed
  for completeness.

## Consequences

### Positive
- Lowest coupling; the leaf keeps a narrow, deep spatiotemporal interface and its frozen v1
  surface; no cross-repo merge train; the production failure's root (fetch-time run selection)
  is removed by a typed, injected boundary.
- The decision is additive and **reversible** — A can still be taken later if a real second
  non-spatiotemporal frame proves the need.

### Negative
- A **second "frame-like" type** exists in the ecosystem (`MetricFrame` is not a `views_frames.*`
  symbol), and the envelope invariants are re-asserted in views-evaluation — registered as
  **C-46** and mitigated by the published checker + versioned wire schema above.
- The provenance split creates **two metadata surfaces** a consumer reconstructing full
  provenance must merge — accepted as the price of keeping evaluation semantics out of the
  generic header (the alternative, one fat header, is worse — ADR-014).

## Implementation Notes

- **In views-frames (this repo):** this ADR; (deferred, on a concrete views-evaluation need) the
  additive `FrameMetadata` fields `run_id`, `data_version` (optional/MINOR, ADR-013); export of
  the conformance/round-trip checker + the published wire schema with `schema_version`. No code
  ships in this ADR beyond the decision record.
  - **Update (v1.4.0, 2026-06-24):** the first two leaf-side pieces shipped — the generic
    `FrameMetadata` provenance fields `run_id`/`data_version` (eval-specific provenance kept out:
    register **C-47 → Resolved**) and the reusable `assert_frame_envelope` checker factored out of
    `assert_frame_contract` as the single written authority for the shared envelope (**C-46
    partially mitigated**). `CONFORMANCE_FLOOR` stays `1.0.0` (additive surface). The versioned wire
    schema (`schema_version`) + the cross-repo round-trip contract test remain the open half of C-46.
- **In views-evaluation (not this repo):** define `MetricFrame` and its eval-specific metadata,
  wrapping `EvaluationReport`; emit it; validate against the published checker/schema
  (views-evaluation#21).
- **In views-reporting (not this repo):** consume `MetricFrame` via an injected adapter; stop
  scraping WandB (ADR-018; register C-108/C-48).
- **No sibling-repo changes are made from views-frames.** The leaf must not depend on any sibling.

## Validation & Monitoring

- A cross-repo emit→consume **round-trip contract test** that calls the published checker and
  validates the `schema_version` is the standing guard against C-46 drift.
- The `FrameMetadata` extension, when made, must add only generic provenance to the leaf
  (C-47 guard); eval-specific fields landing in `FrameMetadata` is a scope violation to reject.

## References

- **views-frames:** README §4.2 (`MetricFrame` out of the leaf); ADR-011 (sibling frames),
  ADR-012 (sample axis), ADR-013 (optional-additive metadata/identifier rule), ADR-014 (geography
  injected), ADR-016 (conformance floor / published suite), ADR-017 (summarisation is a sibling;
  "it is not evaluation"), ADR-018 (v1 freeze; deferred-`MetricFrame` v2 note); `FrameMetadata`
  (`src/views_frames/metadata.py`); register **C-01** (resolved — the original home decision),
  **C-46**, **C-47**, **D-02**.
- **Cross-repo:** GH views-frames#109 (this decision), views-evaluation#21 (emit side),
  views-reporting ADR-018 + register C-108/C-48 (consume side).
