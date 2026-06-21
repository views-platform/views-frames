
# ADR-007: Silicon-Based Agents as Untrusted Contributors

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

This repository is expected to be built and maintained with substantial help from
**silicon-based agents** (LLM-based coding assistants — the tooling in use is **Claude
Code**, and this governance scaffold itself was generated with one). Standing the leaf up
is a *relocation* task: move `PredictionFrame` out of views-pipeline-core and
`FeatureFrame` out of views-datafactory, **rewriting `PredictionFrame`'s identifier
validation numpy-only** (it currently imports pandas and uses `pd.isna`; README §10.2).
That is exactly the kind of contract-preserving rewrite where a silicon-based agent is
most prone to silent truncation or to "helpfully" porting the pandas import it was meant
to remove.

Silicon-based agents differ fundamentally from carbon-based agents:

- They optimize for local plausibility, not global correctness
- They lack understanding of system intent and architectural constraints
- They may infer, invent, or collapse semantics silently (e.g. re-introduce a `views_*`/pandas import into the numpy-only core)
- They may introduce partial or structurally valid failures (e.g. truncation that drops an invariant check)
- They do not experience uncertainty, responsibility, or risk

Without explicit guardrails, they introduce architectural, semantic, and safety risks
that are hard to detect post hoc.

---

## Decision

Silicon-based agents are treated as **untrusted contributors**.

They are permitted to assist in code modification **only under explicit,
documented constraints**, and **never as autonomous authorities**.

All silicon-based agent activity is subject to the same (or stricter)
architectural rules as carbon-based agents, including but not limited to:

- declared ontology (ADR-001) — must not re-introduce a domain concept, the grid, or a `_BaseFrame` god-class the leaf disclaims,
- enforced topology (ADR-002) — must not add a `views_*`/pandas import to the numpy-only core,
- explicit semantic authority and fail-loud behavior (ADR-003),
- mandatory testing obligations (ADR-005),
- intent contracts for non-trivial classes (ADR-006),
- explicit failure and observability requirements (ADR-008).

The concrete operational rules governing silicon-based agents are defined outside this ADR
in a dedicated **Silicon-Based Agent Protocol**
(`contributor_protocols/silicon_based_agents.md`) — note especially its anti-truncation
rule, directly relevant to the contract-preserving relocation of the twins.

---

## Scope

This decision applies to:

- LLM-based coding assistants
- AI-powered refactoring tools
- Code-generation, modification, or suggestion systems
- Any non-carbon-based agent that proposes or applies code changes

This ADR does **not** regulate:

- carbon-based agents (see `contributor_protocols/carbon_based_agents.md`)
- read-only analysis or explanation tools
- tooling that does not modify repository state

---

## Authority and Responsibility

Silicon-based agents:

- are not authoritative
- do not own intent
- do not establish semantics
- do not override architectural decisions

Carbon-based agents remain fully responsible for:

- the correctness of changes,
- adherence to ADRs and intent contracts,
- and the consequences of merging silicon-assisted code.

“No carbon-based agent reviewed it” is not an acceptable justification.

---

## Enforcement

- Silicon-based agent–assisted changes must comply with the Silicon-Based Agent Protocol (`contributor_protocols/silicon_based_agents.md`)
- Violations of architectural ADRs by silicon-based agents are treated as violations by carbon-based agents
- Reviewers are expected to apply **heightened scrutiny** to silicon-assisted changes — in particular, verifying that a relocated class did not silently lose an invariant check present in the source and did not carry the pandas import the rewrite was meant to drop

The absence of declared guardrails is grounds for rejecting such changes.

---

## Consequences

### Positive

- Prevents silent architectural erosion
- Preserves semantic integrity under automation
- Makes responsibility explicit and traceable
- Aligns automated modification with fail-loud and observability guarantees

### Negative

- Limits agent autonomy
- Requires carbon-based agents to actively constrain and review agent output
- Adds friction compared to unrestricted tool use

These trade-offs are accepted intentionally.

---

## Notes

This ADR establishes **that** silicon-based agents are constrained.

It does not define **how** they are constrained.

Operational rules, allowed actions, forbidden actions, and review requirements
are defined in the **Silicon-Based Agent Protocol**
(`contributor_protocols/silicon_based_agents.md`), which may evolve
independently as tools and risks change.

