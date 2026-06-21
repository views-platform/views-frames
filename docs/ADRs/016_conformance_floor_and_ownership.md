
# ADR-016: Conformance-floor and ownership / release cadence

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Informed:** all consuming repos (views-pipeline-core, views-datafactory, views-faoapi, views-reporting, views-evaluation, model repos)

---

## Context

`views-frames` is load-bearing for ~12 risk-register items across 3+ repos and `PredictionFrame`
is the platform's #1 coupling hub. A leaf this central has two governance gaps the design
otherwise under-specifies: (1) the conformance suite (the cross-repo safety net, README §9) ships
*with* the leaf and consumers pin *different* versions — so it tests "my adapter vs my pin," not
"all consumers agree" (the version-coordination paradox, **C-10**); and (2) there is no named
owner or process for the day a MAJOR bump must land across N repos at once (**C-05**, **C-13**).
SemVer mechanics (README §8) are necessary but not sufficient — coordination, not code, is the
real cost.

---

## Decision

1. **Conformance floor.** Publish the conformance suite as an **importable, installable artifact**
   (a subpackage / pytest plugin), and govern a single **conformance-floor version** that *every*
   consumer runs in CI **regardless of its runtime pin**. The floor is bumped deliberately, as a
   governance act, not implicitly by a consumer upgrading.
2. **Ownership + release cadence.** Name a keystone **owner** accountable for the contract, a
   regular release cadence, and an explicit **cross-repo MAJOR-bump process**: a MAJOR change is
   proposed as an ADR, lands behind `from_legacy_*` shims, and is coordinated as a merge-train
   across consumers — never a silent break.

This ADR carries the scope the deferred **ADR-004** (Evolution & Stability) will formally activate
when `v0.1.0` ships and the first consumer pins the package.

---

## Rationale

A conformance suite only closes the cross-repo contract-test gap (pipeline-core C-30) if all
consumers test the *same* contract; a governed floor is the only way to guarantee that. And a
leaf N repos import is a single point of coordination failure (C-13) unless an owner and a
bump process exist — otherwise the first contested MAJOR change stalls every dependent effort.
This makes the package's stability claim operational rather than aspirational.

---

## Considered Alternatives

### Alternative A: each consumer runs its own pinned conformance version
- **Pros:** zero central coordination.
- **Cons:** consumers test divergent contracts; drift between consumers is exactly what is *not*
  caught — the paradox (C-10).
- **Reason for rejection:** defeats the suite's purpose.

### Alternative B: no named owner (rely on SemVer + goodwill)
- **Pros:** no process overhead.
- **Cons:** the first cross-repo MAJOR bump has no driver; the leaf becomes a stall point (C-13).
- **Reason for rejection:** coordination is the dominant cost; it must be owned.

---

## Consequences

### Positive
- The conformance suite actually closes the cross-repo gap (a single floor).
- A coordinated, shimmed MAJOR-bump path exists before the first one is needed.
- Closes C-05, C-10, C-13.

### Negative
- Ongoing coordination overhead (the floor must be maintained; the owner must drive bumps).
  Accepted — it is cheaper than silent multi-repo breakage.

---

## Implementation Notes

- Package the conformance suite under `tests/conformance/` as an importable artifact (decide the
  exact mechanism — installable extra vs pytest plugin — during scaffold/Epic 2).
- Record the named owner and the conformance-floor version in this repo (e.g. a `GOVERNANCE.md`
  or the README) when `v0.1.0` is cut.
- The MAJOR-bump process reuses the strangler/shim discipline (README §10) and the merge-train
  pattern siblings already use.

---

## Validation & Monitoring

- Signal: every consumer's CI runs the floor version (auditable across repos).
- Failure mode to watch: a consumer skipping the floor, or a MAJOR change landing without an ADR
  + shims + coordination — either re-opens C-05/C-10.

---

## Open Questions

- The concrete packaging mechanism for the conformance suite (extra vs plugin) — resolved during
  the scaffold/Epic 2.
- Who, by name, owns the keystone — to be filled in at `v0.1.0`.
- Relationship to ADR-004 once it activates (this ADR may be partially folded into it).

---

## References

- README §9, §13b.4–5, §8; `critiqus/critique_01.md` §2.5/§3.4/§3.7, `critiqus/critique_03.md` P6.
- Risk register: **C-05**, **C-10**, **C-13**.
- Issue #7; Epic #13.
