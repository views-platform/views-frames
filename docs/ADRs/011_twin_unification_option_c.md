
# ADR-011: Twin-unification model — Option C (separate siblings, shared index)

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Consulted:** views-datafactory lead (ratified the datafactory perspective, 2026-06-21)
**Informed:** views-pipeline-core, views-faoapi, views-reporting

---

## Context

`views-frames` exists to de-duplicate two diverging transport types — `PredictionFrame`
(`views-pipeline-core/.../data/prediction_frame.py`) and `FeatureFrame`
(`views-datafactory/src/datafactory_adapters/feature_frame.py`) — plus a third drifted
fork in `views-faoapi`. The README originally framed them as "near-1:1 twins," but the
falsification audit showed they diverge on **≥6 structural axes** (sample-axis position,
`feature_names`/`metadata`, identifier NaN-check, `collapse`/`mmap`, save footprint, and
`PredictionFrame`'s pandas import) — see **C-16**, **C-03**. "Unify the twins" is therefore
ambiguous: unify *what*, exactly? This must be decided before either class is relocated,
because it determines whether a shared base class exists at all.

---

## Decision

Unify **only** the genuinely-reused core: `SpatioTemporalIndex`, the shared `_validation`
helper, the protocols (`Frame`/`SpatioTemporalIndexed`/`Sampled`/`Persistable`), and `io/`.
Relocate `FeatureFrame` and `PredictionFrame` (and later `TargetFrame`) into the leaf as
**separate sibling classes** that each compose the shared index and satisfy the shared
protocols.

- **In scope:** one shared index + one validation path + one protocol surface + one release
  cadence (both classes now live in one repo).
- **Out of scope:** a shared concrete `_BaseFrame`. There is **no** frame base class. The
  cm/pgm distinction is a `SpatialLevel` *value* on the index, never a class axis.

---

## Rationale

The README §4.3 itself argues the *index* is the reused core, not the frame classes. Option C
takes that seriously: it captures ~80% of the de-duplication value (shared index, validation,
protocols, single cadence) at the lowest churn and with zero god-class risk. A shared base
that must carry `feature_names`/`metadata`/feature-axis to serve both twins would re-create the
`_ViewsDataset` god class (pipeline-core C-36) the package exists to escape. Honesty about the
asymmetry (C-16) beats forcing a false symmetry.

---

## Considered Alternatives

### Alternative A: shared concrete base `_BaseFrame`
- **Pros:** maximal code sharing; one validation path and one save/load.
- **Cons:** the base accretes every frame's fields (`feature_names`, `metadata`, feature axis,
  sample axis) → a god-class; recreates `_ViewsDataset`/C-36.
- **Reason for rejection:** explicitly banned by README §5; the anti-pattern the package exists
  to kill. **Rejected in writing.**

### Alternative B: composition + a shared typed metadata header
- **Pros:** no fat base; frames compose a header object; new frames drop in via OCP.
- **Cons:** the "small `_validation`/header helper" can quietly become a god-class through the
  back door; the discipline that prevents A must be actively enforced.
- **Reason for rejection (for v1):** premature — no third frame yet proves the header is
  reused. **Deferred**, not rejected: adopt B if/when a third frame demonstrates a genuinely
  shared header.

### Alternative C: separate siblings, shared index only — **chosen.**

---

## Consequences

### Positive
- No god-class; lowest-churn v1; the real shared primitive (index) is de-duplicated.
- The twins can evolve their own surfaces without dragging each other.
- Directly closes C-03 (no under-specified shared base) and de-risks C-16.

### Negative
- The "diverging twins (REP)" pain is only *partly* solved — two classes still exist (now both
  in the leaf) and can drift their class surface, though not their index. Accepted: the index +
  conformance suite are the guard.
- If a third frame later proves a shared header, a migration to Option B is a follow-up.

---

## Implementation Notes

- Enforce in `src/views_frames/`: `feature_frame.py` and `prediction_frame.py` are independent
  classes; neither imports the other; both compose `SpatioTemporalIndex` and call `_validation`.
- A lint/review guard: reject any PR introducing a `_BaseFrame`/`Frame` *concrete* base that the
  frames extend (the protocol `Frame` is fine; a concrete base is not).
- Relocation of each twin is governed by ADR-012 (sample axis) and ADR-013 (metadata) and is
  **not verbatim** for `PredictionFrame` (C-17).

---

## Validation & Monitoring

- Conformance suite asserts each frame satisfies the protocols without a shared base.
- Failure mode that would trigger reconsideration: a third frame appears whose metadata header
  is provably identical to the existing ones — that is the signal to adopt Option B.

---

## Open Questions

- When (if ever) to graduate to Option B — gated on a third frame proving header reuse.

---

## References

- README §5, §13a.1; `critiqus/critique_01.md` §4 (worked A/B/C analysis), `critiqus/critique_03.md` P1.
- Risk register: **C-16**, **C-03**, **C-17**; disagreement **D-03** (resolved).
- Issue #2; Epic #13.
