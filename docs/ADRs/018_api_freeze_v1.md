# ADR-018: API freeze at v1.0.0

**Status:** Accepted (amended 2026-08-18 — see *Amendment* below)
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers (keystone owner)
**Consulted:** two rounds of consumer review
**Informed:** all `views_frames` consumers

> **Amendment (2026-08-18, ADR-028 / register C-13).** **The freeze has been broken once,
> deliberately, in 2.0.0** — the first MAJOR since this ADR was written.
>
> What changed: the three frames' constructors now reject an `index` argument that is not a
> `SpatioTemporalIndex`. That is a **tightening of an invariant** on the constructor shapes
> frozen below, and therefore a MAJOR under `GOVERNANCE.md`. Before 2.0.0 the constructors
> read one attribute off `index` — `n_rows` — so a frame, or any object with an `n_rows`,
> was accepted; the published `assert_summarizer_contract` then certified the result.
>
> Shipping alongside it, as riders on the same bump: `frame.values` is now write-protected
> (register C-66, the enforce ADR-025 deferred), the same-level alignment ops raise
> `TypeError` rather than leaking a private attribute, and `map_estimate` rejects non-finite
> draws (register C-57). `CONFORMANCE_FLOOR` moved `1.0.0` → `2.0.0`, its first move.
>
> **The frozen list below is otherwise unchanged** — no name was removed, renamed or
> re-signatured, and no consumer passing a real `SpatioTemporalIndex` is affected. What
> narrowed is the set of inputs that were never valid. ADR-028 carries the decision, the
> full migration table and the reasoning; read it before treating this as licence for a
> second MAJOR.

---

## Context

`views-frames` is the leaf of the platform dependency DAG: every other repo depends
*toward* it, so its stability is the whole point. Through v0.1.0–v0.3.0 the contract
was deliberately allowed to make **breaking changes in MINOR bumps** (the pre-1.0
latitude in `GOVERNANCE.md`), because no consumer had pinned it yet. Two rounds of
consumer review validated the design — **no ADR was
challenged** — and the remaining findings were correctness/polish, now resolved
(register C-19…C-27). Two of those changes touched the *published* surface: the
`(time, unit)`-keyed time-aware `cross_level_align` (C-20, a breaking re-key) and the
documented row-uniqueness stance (C-21).

The consumer reviews asked, repeatedly, for **a stable target to pin** and for the
breaking-change rationale to live in the decision record, not only in `git log`. That
target is now needed: the next milestone is real consumer adoption, and a consumer
cannot adopt a contract that may break in a MINOR.

---

## Decision

**v1.0.0 freezes the public API of `views-frames`.** From v1.0.0, the pre-1.0
breaking-in-MINOR latitude **ends**: any breaking change to the frozen surface is a
**MAJOR** bump and follows the cross-repo MAJOR-bump process in `GOVERNANCE.md`.

**In scope (frozen — the surface a consumer may pin):**

- The frames `FeatureFrame` `(N, F, S)`, `PredictionFrame` `(N, S)`, `TargetFrame`
  `(N, 1)`: their constructor shapes, `values`, `identifiers`, `metadata`, `n_rows`,
  `sample_count`/`is_sample`, `with_metadata`, `select`/`reindex`, `save`/`load`; plus
  `FeatureFrame`'s `feature_names`, `n_features` and `from_2d` — `feature_names` is the
  attribute that distinguishes a feature frame at all (ADR-013), and `from_2d` is ordinary
  supported surface for unsampled `(N, F)` input, not a deprecated shim (register C-76).
- `SpatialLevel` (ADR-015): the cm/pgm identifier vocabulary. **Required** to construct a
  `SpatioTemporalIndex` — passing anything else raises `TypeError` — so no consumer can
  build a frame without it.
- `FrameMetadata` (ADR-013): the typed provenance header. Optional at construction
  (`metadata=None` builds an empty one), but it is the type `.metadata` **returns**, so any
  consumer reading or writing provenance depends on its field set and on
  `to_dict`/`from_dict`.
- `SpatioTemporalIndex`: the `{time, unit, level}` identity, same-level alignment
  (`intersect`/`reindex`/`searchsorted`/`is_superset_of`/`argsort`/`select`), the
  **`(time, unit)`-keyed, time-aware** `cross_level_align` and the columnar
  `cross_level_align_arrays`, the `has_unique_rows` helper, and the **row-uniqueness
  stance**: duplicate `(time, unit)` rows are *allowed* (cross-level produces them);
  same-level joins *assume* uniqueness.
- The protocols `Frame` / `SpatioTemporalIndexed` / `Sampled` / `Persistable`.
- The published conformance suite and its laws **as they stood at v1.0.0**
  (`assert_frame_contract`, `assert_index_alignment_laws`,
  `assert_cross_level_alignment_law`, `assert_summarizer_contract`), governed at
  `CONFORMANCE_FLOOR = "1.0.0"`. Three more have been published since — see the forward
  pointer below; `GOVERNANCE.md` carries the current full table.
- The `views_frames_summarize` estimator surface: `collapse`, `map_estimate`, `hdi`,
  `quantiles`, `aggregate_distributions`, `aggregate_distributions_arrays`.

> **Additive since v1.0.0 (forward pointer):** v1.1.0 added the coherent posterior
> summary — `hdi_tower` / `tower_point` / `bimodality` / `summarize_tower` (+ the
> `TowerSummary` bundle) — **additively** under this freeze (ADR-019); the frozen v1.0
> estimators above are unchanged. The published conformance suite correspondingly grew
> (`assert_summarizer_contract` now also runs the tower laws). The `CONFORMANCE_FLOOR`
> stays `1.0.0` because additive surface does not break a consumer pinned at the floor.
> The threshold **exceedance** estimators (`exceedance` / `exceedance_reducer`, `P(Y > c)`)
> are likewise additive under this freeze (ADR-021, target v1.5.0); the floor stays `1.0.0`.
> The worst-case **expected shortfall** estimator (`expected_shortfall`, the tail mean) is likewise
> additive under this freeze (ADR-022, target v1.6.0); the floor stays `1.0.0`.
>
> **Three more additions were shipped without being recorded here, and are recorded now**
> (register C-85, 2026-08-17). This section exists to track post-freeze growth, so an
> omission in it is the same failure as an omission in the frozen list above:
>
> - **v1.4.0** — `views_frames.conformance.assert_frame_envelope`, the shared frame
>   envelope factored out as one written authority for a non-spatiotemporal sibling to
>   validate against (ADR-020; the shipped half of register C-46).
> - **v1.7.0** — the whole **`views_frames_reconcile`** package (ADR-023): `ReconciliationModule`,
>   `ReconciliationResult`, `reconcile_proportional`, the `POINT_BROADCAST` / `ALIGNED_DRAWS`
>   mode constants and `METHOD_PROPORTIONAL`, plus `conformance.assert_reconcile_contract`.
>   v1.8.0 added the native point-country broadcast within it. A third package joined the
>   wheel and this ADR did not say so.
> - **v1.10.0** — the dense-grid family (ADR-026): `frame.reindex_fill(other, *, fill_value)`
>   on all three frames, `SpatioTemporalIndex.cartesian`, and the published
>   `assert_reindex_fill_law`.
>
> All are additive; the floor stays `1.0.0` throughout, because additive surface does not
> break a consumer pinned at the floor.

**Out of scope (NOT frozen, may still evolve additively or remain deferred):**

- New surface remains **additive (MINOR)** — a new frame type, optional metadata
  field, method, or `io/` format does not break the freeze.
- Deferred items stay deferred by design: `MetricFrame` / a non-spatiotemporal key
  protocol (out of the leaf — views-evaluation owns eval output), provenance fields
  on `FrameMetadata` (additive when needed).
- Private/underscore modules (`_typing`, `_validation`, `_common`, `_batched_map`,
  `ROW_BLOCK`, `block_rows` internals) are **not** part of the frozen contract.

---

## Rationale

A keystone's value is stability for N consumers; that stability is only real once it
is *declared and enforced*, not merely intended. Freezing at v1.0 — before the first
consumer pins — is deliberate: it gives adopters a fixed target and converts the
SemVer rules from advisory to binding. The breaking changes that needed making
(C-20's time-aware re-key) were made *while* breaking was cheap; the surface has now
been exercised by two review rounds without a design challenge, so the risk of a
forced MAJOR soon after 1.0 is low. Recording the frozen surface here (not in commit
messages) answers the second-round governance finding and gives a future agent the
breaking-change rationale from the decision record.

---

## Considered Alternatives

### Alternative A: stay at 0.x indefinitely
- **Pros:** keeps breaking-in-MINOR latitude.
- **Cons:** no consumer can safely pin; the leaf's whole identity (stability) stays
  aspirational; reviewers explicitly asked for a 1.0 signal.
- **Reason for rejection:** the next milestone *is* adoption, which needs a stable pin.

### Alternative B: a new ADR per frozen decision (separate ADRs for the re-key, the uniqueness stance, select/reindex)
- **Pros:** finest-grained record.
- **Cons:** scatters one coherent decision (the freeze) across many ADRs; ADR-014
  already carries the cross-level note.
- **Reason for rejection:** the freeze is one decision; this ADR references the others.

---

## Consequences

### Positive
- Consumers get a fixed, pinnable contract; adoption can proceed.
- The SemVer rules become binding; breaking changes are now visible (MAJOR + process).
- The frozen surface is discoverable from the decision record.

### Negative
- Future breaking changes cost a MAJOR bump + cross-repo merge-train (intended).
- Anything missed before the freeze that later needs a breaking fix pays that cost —
  mitigated by the two review rounds and the pre-freeze cleanups in this epic.

---

## Implementation Notes

- `GOVERNANCE.md`: the "Stability — the v1.0 freeze" section enumerates the frozen
  surface and ends the pre-1.0 latitude; the conformance floor is `1.0.0` and tracks
  the whole published surface (register C-27).
- `CONFORMANCE_FLOOR = "1.0.0"` (`src/views_frames/conformance/__init__.py`); the
  pinning test asserts it.
- `pyproject.toml` version `1.0.0`; tag `v1.0.0`.
- ADR-014's Implementation Notes already record the `(time, unit)` re-key as the
  final form; this ADR marks it frozen.

---

## Validation & Monitoring

- The conformance suite + the `floor` CI job (mypy **and** pytest at `numpy==1.26.4`)
  must stay green — a consumer pins against exactly this.
- Failure mode that would trigger reconsideration: a real consumer cannot express a
  needed operation without a breaking change — that is a MAJOR (v2) conversation,
  handled by the cross-repo process, not a silent break.

---

## Open Questions

- Whether `MetricFrame` / a non-spatiotemporal key protocol ever enters the leaf is a
  deliberate v2 question, reopened only if a consumer proves the need (still out).
  **Settled by ADR-020 (2026-06-24, GH#109):** `MetricFrame` is hosted in views-evaluation
  on the views-frames substrate (the leaf stays spatiotemporal; v1 index unchanged); the v2
  index generalisation is reopened only if a *second* non-`(time, unit)` frame-like type is
  independently needed.

---

## References

- Epic 5 PRs (test-portability, summarizer-memory, select-reindex, cross-level-arrays,
  freeze-and-release); register C-19…C-27.
- The first- and second-round consumer-review syntheses.
- ADR-014 (cross-level), ADR-016 (conformance floor + ownership).
