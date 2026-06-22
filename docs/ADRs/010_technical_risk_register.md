
# ADR-010: Technical Risk Register as a Governance Artifact

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

`views-frames` is currently a **design repository**: a README design bible for a
not-yet-built leaf data-contract package, plus consumer-review findings, design
critiques, and falsification stubs. The pre-code design surfaced real
forward-looking risks (twin drift, the list-in-cell memory blow-up, the cross-level
mapping boundary, the conformance/version-coordination paradox), but these are mostly
**latent and trigger-conditioned** — they become acute only when the leaf is stood up or
when a consumer pins it — and several reference code in *external* repos.

Such risks have no natural home in the codebase (there is none yet) and would otherwise be
rediscovered rather than tracked. They need a durable, structured place that survives the
gap between the design bible and the implementation.

This ADR is numbered **ADR-010** to sit after the constitutional ADRs (000–009) introduced
by the documentation-governance framework.

---

## Decision

Establish a technical risk register as the single, authoritative record of technical
risk for this repository, maintained as an internal governance artifact. All
audit-derived findings (repo-assimilation,
expert-code-review, test-review, falsification, persona-critique, etc.) are funnelled into
it through the `register-risk` skill, which enforces deduplication, tier assignment, and
trigger-quality gating. The register is curated and prioritised via the `review-rr` skill.

### Concern format

Each entry has: an **ID** (`C-xx` for concerns, `D-xx` for disagreements; permanent, never
reused — gaps indicate merged/resolved entries), a **Tier** (1–4), a **Source** + date, an
actionable **Trigger**, a **Location**, and a grounded **Narrative**.

### Tier definitions

| Tier | Severity | Criteria |
|------|----------|----------|
| 1 | Critical | Silent data corruption or output incorrectness with no error signal. |
| 2 | High | Structural fragility that causes failures under realistic change scenarios. |
| 3 | Medium | Maintainability or coupling issues that increase cost of change. |
| 4 | Low | Code-quality observations with no correctness or reliability impact. |

Header counts (Total / Open / Resolved) are maintained manually on every change.
Resolution moves an entry to the Resolved section; the ID is never reused.

---

## Rationale

This ADR makes the risk register a first-class governance artifact rather than an ad-hoc
note. It complements the constitutional ADRs: where ADR-003/008 mandate fail-loud and
ADR-009 mandates validated boundaries, the register tracks the *known gaps* against those
principles until they are closed. It is the operational counterpart to the design bible's
own "Risk-register & decisions" section (README §12), with enforced structure and
triggers.

---

## State at Creation: Empty

The register is created **empty** — no seeded concerns. This is a deliberate greenfield
choice: the design bible's resolved decisions (README §13a) already settled the major
pre-code questions, and the prior **critique and falsification findings are held as
internal artifacts**. Those can be registered via
`register-risk` when a maintainer chooses to track them formally — for example when the
leaf is stood up and the external-repo locations they reference become concrete. Until
then the register stands ready with Total / Open / Resolved = 0.

---

## Consequences

### Positive
- Forward-looking risks survive the design→implementation gap and are re-checked when their triggers fire.
- Deduplication and tiering keep the register honest and prioritisable.
- The register is the seed of future project-specific ADRs (011+) when a risk graduates into a ratified decision.

### Negative
- Many future entries will reference external repos (views-pipeline-core, views-datafactory, views-faoapi, views-reporting) because this leaf de-duplicates code not yet relocated; those locations must be confirmed when the package is stood up.
- Requires discipline: entries are removed only by resolution, not silent deletion.

---

## Implementation Notes

- The register is maintained as an internal governance artifact (created empty 2026-06-21).
- Add risks via the `register-risk` skill; curate/prioritise via `review-rr`.
- Prior findings to consider registering are held as internal critique and falsification artifacts.

---

## References

- The technical risk register (internal governance artifact).
- `README.md` (design bible §12 "Risk-register & decisions this resolves / informs")
- Internal critique and falsification findings.
