
# ADR-013: Metadata and identifier model — typed header + fixed identifiers

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Informed:** views-reporting (C-48 consumer of record), views-evaluation, views-pipeline-core

---

## Context

Two questions decide how cheaply `views-frames` can evolve across the ~6 repos that import it:
(1) is per-frame `metadata` a typed schema or a free-form dict, and (2) can the per-row
identifier set grow beyond `{time, unit}`? README §8 names "adding a required identifier" as the
canonical breaking change — so the **most likely** future additions (provenance for reporting's
C-48, ensemble `origin`, evaluation `step`) are also the **most expensive** if modelled wrong
(C-08). The distinction that unlocks this is **identifier (per-row, participates in alignment)**
vs **metadata (per-frame, does not)**.

---

## Decision

**Metadata is a typed, optional-extensible header** — not a free-form `dict[str, Any]`. It
carries provenance (`model`, `run_type`, `timestamp`, `seed`) and `feature_names`, validated at
construction. New header fields are added as **optional** (MINOR).

**Identifiers are a fixed, required `{time, unit}`** for v1. Any future per-row axis (`step`,
`origin`, `scenario`) is added as an **optional** identifier (MINOR) — **never** as a required
identifier (which is the §8 MAJOR break). `time` remains an opaque integer (the leaf validates
structure, not epoch/range — see ADR-009 and C-11).

This typed header is the home for the run/eval identity that cures reporting's C-48 and the
#178 provenance work; selecting *the* run and *where* it is stored remains a cross-repo decision
(D-02) the leaf only provides a slot for.

---

## Rationale

A typed header puts the provenance contract *inside* the leaf, defined and validated once, so
consumers cannot diverge on key names (`run_type` vs `runType`) — divergence is precisely what
re-opens C-48 store-side. Fixing identifiers at `{time, unit}` keeps the alignment surface
minimal and predictable; making future axes *optional* keeps the common evolution a MINOR bump
instead of a coordinated N-repo MAJOR break (C-08). This separates the two concepts cleanly:
the index aligns rows; the header describes the frame.

---

## Considered Alternatives

### Alternative A: free-form `dict[str, Any]` metadata
- **Pros:** maximum flexibility; zero schema work.
- **Cons:** un-validatable; provenance keys diverge per consumer → C-48 returns store-side;
  `get_latest`/`search` filters cannot be relied on.
- **Reason for rejection:** re-opens the exact bug the header is meant to cure.

### Alternative B: open identifier set from v1
- **Pros:** `step`/`origin` are first-class join axes immediately.
- **Cons:** speculative generality; widens every join surface before a real consumer needs it.
- **Reason for rejection:** add the axis when a concrete consumer forces it, as an *optional*
  identifier; do not pre-build it.

---

## Consequences

### Positive
- Provenance has a reliable, typed home (cures C-48 from the frame side).
- The likely future additions are MINOR, not platform-wide MAJOR (closes C-08).
- Clean concept split (identifier vs metadata) prevents the junk-drawer dict.

### Negative
- A typed header is more upfront work than a dict and must itself be versioned carefully (new
  fields optional-only). Accepted.
- The full C-48 cure still needs a cross-repo run-selection/storage decision (D-02) outside this
  leaf.

---

## Implementation Notes

- Model the header as a frozen dataclass (`FrameMetadata`) with all-optional fields + validation;
  `feature_names` lives here for `FeatureFrame`.
- `_validation.py` enforces required identifiers `{time, unit}`; optional identifiers validated
  against that required subset.
- Serialization (ADR governing `io/`, and C-09): the header round-trips *with* the frame via a
  `__frame_state__`-style contract, not via `io/`-internal per-frame special cases.

---

## Validation & Monitoring

- Conformance property: adding an optional header field or optional identifier does not change
  the validation outcome for existing frames (back-compat).
- Signal to watch: any PR proposing a *required* new identifier — that is a MAJOR bump and must
  be escalated per ADR-016's cross-repo process.

---

## Open Questions

- The precise provenance key vocabulary (`model`, `run_type`, `timestamp`, `data_version`, …)
  must be specified precisely enough that every consumer maps it to store metadata identically
  (relates to C-10/C-48 store-side). Tracked with the views-reporting/views-evaluation work.

---

## References

- README §13a.3, §8, §13.5; the pre-code design audit.
- Risk register: **C-08**, **C-11**, **C-09**; disagreement **D-02**.
- Issue #4; Epic #13.
