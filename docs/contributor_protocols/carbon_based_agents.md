
# Carbon-Based Agent Protocol  
*(For contributors composed primarily of carbon, caffeine, and responsibility)*

**Status:** Active  
**Applies to:** All human contributors to `views-frames` (VIEWS platform maintainers and consumer-repo authors)  
**Authority:** ADR-001 through ADR-009  

---

## Purpose

This protocol defines the responsibilities, expectations, and obligations of
**carbon-based agents** contributing to this repository.

`views-frames` is greenfield and currently maintained by a small group; this protocol
applies in full the moment additional contributors join or a consumer repo begins
relocating its twin into the leaf.

Carbon-based agents are entrusted with:
- intent,
- judgment,
- and architectural authority.

With that trust comes responsibility. This protocol exists to ensure that speed,
convenience, or tooling never outruns understanding, intent, or accountability — and, for
this leaf specifically, that the numpy-only, no-domain-logic data-contract boundary
(ADR-001) is never quietly eroded.

---

## Core Principle: Stewardship of Intent

Carbon-based agents are **stewards of intent**, not merely authors of code.

Stewardship means:
- preserving meaning over time,
- enforcing architectural boundaries,
- and preventing silent failure under pressure.

Code may change.  
**Intent must not drift silently.** The whole reason this leaf exists is that the twins'
intent drifted apart across repos; do not repeat that here.

---

## Ownership of Intent and Semantics

Carbon-based agents:
- own system intent and meaning,
- declare semantics explicitly,
- and are accountable for their correctness.

If a change alters the *meaning* of a component:
- its intent contract must be updated (ADR-006), or
- a new ADR must be written, or
- the change must not be merged.

“No one told me” and “it was implied” are not valid defenses. The canonical violation to
guard against: re-introducing pandas or a `views_*` import into the numpy-only core, or
embedding the cross-level mapping, because a consumer found it convenient.

---

## Fail-Loud Is a Moral Obligation

Silent failure is unacceptable.

Introducing:
- implicit behavior,
- fallback logic that hides errors,
- or ambiguity in decision-relevant semantics

is considered a defect, even if tests pass.

Carbon-based agents enforce the **fail-loud invariant** of ADR-003 (Authority of
Declarations Over Inference) and ADR-008 (Observability and Explicit Failure) — for this
leaf, that means invariants are checked at construction and raise immediately, never
returning a half-valid frame.

Professional discomfort is preferable to silent risk.

---

## Testing Is Part of the Change

Tests are not optional, and not a follow-up.

A change is incomplete if it:
- cannot be tested meaningfully,
- weakens existing tests without justification,
- or relies on “manual verification” or tribal knowledge.

Carbon-based agents must ensure appropriate coverage across:

- 🟥 **Red team tests** — adversarial and worst-case (NaN/`object`-dtype identifiers, missing `{time, unit}`, non-overlapping alignment)
- 🟫 **Beige team tests** — realistic, neutral, “boring but dangerous” usage (partial-overlap alignment, round-trip save/load, mutating-in-place mistakes)
- 🟩 **Green team tests** — correctness, robustness, and resilience (alignment-law property tests, the copy-vs-view memory property)

as defined in ADR-005.

Tests are the executable proof of intent.

---

## Interaction with Silicon-Based Agents

Using silicon-based agents (automated coding assistants) does **not**
reduce responsibility.

When carbon-based agents use silicon-based agents, they must:
- understand what the agent changed,
- verify changes against ADRs and intent contracts,
- ensure no forbidden operations occurred,
- and take full responsibility for the result.

Apply heightened care to the contract-preserving relocation of the twins: verify the
silicon-assisted move did not silently drop an invariant check and did not carry the
pandas import the rewrite was meant to remove (README §10.2).

“The silicon-based agent did it” is not justification.

Carbon-based agents remain fully accountable.

---

## Review Is an Architectural Act

Code review is not a cosmetic exercise.

Carbon-based agents reviewing changes are expected to assess:
- intent alignment,
- boundary integrity (ADR-002),
- semantic clarity (ADR-003),
- and test adequacy (ADR-005).

If a reviewer cannot explain what a change *means*, it should not be approved. The leaf's
review litmus test: *“Would this concept make sense to any consumer of an array aligned to
`(time, unit)`, with zero VIEWS-domain knowledge?”* If no, the change probably violates
ADR-001.

---

## Non-Negotiable Expectations

Carbon-based agents must not:
- merge changes they do not understand,
- normalize warnings or TODOs that hide failure,
- bypass tests under time pressure,
- defer intent clarification “until later”,
- or shift responsibility to tools or future contributors.

Speed does not justify ambiguity.

---

## Enforcement

This protocol is enforced socially through collaboration and review.

Violations may result in:
- blocked merges,
- requests for clarification or documentation,
- or escalation to architectural discussion.

These measures protect the system and its users.

---

## Gate Sequencing for Pre-Code Commits

Until the leaf's first code lands, the repository may legitimately hold failing tests:
falsification stubs (`tests/`) are TDD-red enforcement artifacts generated by `/falsify`
audits. Each stub encodes an unresolved finding and **must not be deleted to make a gate
pass**.

1. A falsification stub is expected-red until the finding it encodes is resolved; it turns
   green only by fixing that finding.
2. Commits touching only documentation/governance (no package code) may land with the
   pytest gate waived; the waiver must be recorded in the commit message.
3. From the first `src/` scaffold commit onward, ADR-005 applies in full: new code requires
   green tests and the CI gate must land in the same commit. Any remaining red stubs are
   then quarantined with an explicit expected-failure marker — never silently deleted.
4. Gate attach order at the scaffold commit: CI workflow → ADR-005 test obligations
   (including the published conformance suite) → CIC obligations (ADR-006) as each class is
   implemented.

---

## Final Note

Carbon-based agents are the **last line of defense**.

Tools can accelerate work.  
Automation can multiply mistakes.

This protocol exists to ensure that,  
even under pressure,  
**the system continues to mean what we think it means**.
