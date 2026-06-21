# Governance — views-frames

`views-frames` is the VIEWS platform's leaf data-contract package: many repos
import it, so a breaking change is expensive. This document records the ownership
and release governance required of a keystone (ADR-016).

## Owner

**Keystone owner:** VIEWS platform maintainers. The owner is accountable for the
contract — reviewing every change against the ADRs/CICs, cutting releases, and
driving any cross-repo MAJOR bump.

## Conformance floor

The published conformance suite ships with the package as `views_frames.conformance`
(`assert_frame_contract`, `assert_index_alignment_laws`,
`assert_cross_level_alignment_law`). Every consumer runs it in CI against its own
adapter output.

- **Conformance-floor version:** `1.0.0` (`views_frames.conformance.CONFORMANCE_FLOOR`).
- The floor is a **single governed version every consumer runs regardless of its
  runtime pin** — this is what makes the suite test "all consumers agree," not
  "my adapter vs my pin" (closes register C-10). The floor is bumped deliberately,
  as a governance act, not implicitly by a consumer upgrading.
- **What the floor tracks (register C-27):** the **whole published conformance
  surface** — both the structural frame contract and the published laws
  (`assert_index_alignment_laws`, `assert_cross_level_alignment_law`, and the
  summarizer's `assert_summarizer_contract`). It is bumped whenever a **breaking**
  change is made to any of them, so reading `CONFORMANCE_FLOOR` tells a consumer
  exactly which contract version its CI asserts. Additive surface (a new law or
  method) is MINOR and does **not** bump the floor.

## Versioning (SemVer for a contract)

- **MAJOR** — removing/renaming a field, changing a dtype or axis meaning, adding a
  **required** identifier, tightening an invariant.
- **MINOR** — a new frame type, a new **optional** metadata field or identifier, a
  new method, a new `io/` format.
- **PATCH** — bug/doc fixes with an identical contract.

**Pre-1.0 (before the freeze below):** because no consumer had pinned the package,
breaking changes were allowed in a **MINOR** bump (each one labelled "Changed
(breaking, pre-1.0)" in `CHANGELOG.md`). The `(time, unit)` `cross_level_align`
re-key (v0.3.0) was the last such change. This pre-1.0 latitude **ends at v1.0.0.**

## Stability — the v1.0 freeze

**v1.0.0 freezes the public API.** From v1.0.0 on, the SemVer rules above are
binding without the pre-1.0 latitude: any breaking change to the frozen surface is
a **MAJOR** bump and follows the cross-repo process below. What v1.0.0 locks (the
surface a consumer may safely pin) is recorded in **ADR-018**:

- the frames (`FeatureFrame`/`PredictionFrame`/`TargetFrame`), their constructor
  shapes, `identifiers`, `values`, `metadata`, `save`/`load`, `with_metadata`,
  `select`/`reindex`;
- `SpatioTemporalIndex` (`{time, unit, level}`, same-level alignment, the
  `(time, unit)`-keyed time-aware `cross_level_align`/`cross_level_align_arrays`,
  the row-uniqueness stance);
- the `Frame`/`SpatioTemporalIndexed`/`Sampled`/`Persistable` protocols;
- the published conformance suite and laws;
- the `views_frames_summarize` estimator surface (`collapse`/`map_estimate`/`hdi`/
  `quantiles`/`aggregate_distributions`).

New surface remains additive (MINOR). The bar to a MAJOR bump is deliberately high
(see the closing note); reaching v1.0 with no pinned consumer is intentional — it
gives the first adopters a stable target to pin against.

## Cross-repo MAJOR-bump process

A MAJOR change is never a silent break:

1. Propose it as an ADR (the decision + the migration).
2. Land it behind `from_legacy_*` shims where a consumer format changes.
3. Bump the conformance floor and coordinate a merge-train across consumers.

If the package needs frequent MAJOR bumps, it is not abstract/stable enough —
push the volatility out into consumer adapters (SAP).
