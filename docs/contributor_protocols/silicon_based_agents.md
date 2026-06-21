
# Silicon-Based Agent Protocol  
*(For contributors composed primarily of silicon, statistics, and confidence)*

**Status:** Active  
**Applies to:** All automated or AI-assisted code modification of `views-frames`  
**Authority:** ADR-007 (Silicon-Based Agents as Untrusted Contributors)

---

## Purpose

This document defines **mandatory operational constraints** under which **silicon-based
agents** (e.g. LLM-based assistants such as **Claude Code**, code generators, refactoring
tools) may interact with this repository.

Silicon-based agents are powerful but unsafe by default. This protocol exists to prevent
silent semantic corruption, architectural erosion, responsibility laundering, and
hard-to-detect partial failures. It is binding for all silicon-assisted changes.

> **Project-specific note.** This repository's documentation scaffold was itself generated
> with a silicon-based agent, and standing the leaf up is a contract-preserving relocation
> (moving `PredictionFrame` out of views-pipeline-core and `FeatureFrame` out of
> views-datafactory, **rewriting `PredictionFrame`'s identifier validation numpy-only** —
> it currently imports pandas; README §10.2). That is precisely the scenario the
> Anti-Truncation Rule below exists to guard. Treat every full-file operation on those
> sources as high-risk, and never carry the pandas import the rewrite is meant to drop.

---

## Threat Model

Silicon-based agents are assumed to:

- optimize for local plausibility, not global correctness,
- infer intent when it is not explicitly declared (e.g. assume `time` is a month_id epoch),
- collapse abstractions for convenience (e.g. invent a `_BaseFrame` the frames extend),
- silently omit or truncate content due to token or buffer limits,
- produce outputs that *look valid* while being semantically incomplete.

Silicon-based agents are therefore treated as **untrusted contributors**.

---

## Global Rules (Non-Negotiable)

Silicon-based agents:

- ❌ are not authoritative
- ❌ do not own intent
- ❌ do not establish or infer semantics
- ❌ do not override ADRs or intent contracts
- ❌ do not introduce silent failure modes

All silicon-based agent–assisted changes must comply with:

- ADR-001 (Ontology)
- ADR-002 (Topology)
- ADR-003 (Authority of Declarations & Fail Loud)
- ADR-005 (Testing as Critical Infrastructure)
- ADR-006 (Intent Contracts for Non-Trivial Classes)
- ADR-007 (Silicon-Based Agents as Untrusted Contributors)

---

## Allowed Operations

Silicon-based agents **may**:

- Perform *local*, scoped refactors within a single class or file
- Add or update tests that reflect **declared intent**
- Implement changes explicitly requested and scoped by a carbon-based agent
- Make mechanical changes (renaming, formatting) with no semantic impact
- Propose changes (via diffs or suggestions) without applying them

All allowed operations remain subject to carbon-based agent review.

---

## Forbidden Operations

Silicon-based agents **must not**:

- Introduce or modify semantics without updating intent contracts
- Infer behavior from naming conventions, file structure, or heuristics
- Cross architectural boundaries (ADR-002) — **in particular, never add a `views_*` import or pandas/polars/geopandas/wandb/viewser/torch to the numpy-only core**
- Remove validation, checks, or fail-loud behavior (the construction-time invariants are load-bearing)
- Convert explicit errors into warnings or fallbacks
- Refactor multiple architectural layers in a single change
- Modify the ontology implicitly (ADR-001) — **never embed the cross-level mapping, add the grid, or invent a `_BaseFrame` god-class**
- Make “helpful” assumptions when required information is missing

If a silicon-based agent cannot proceed without guessing, it must stop.

---

## Mandatory Safety Rule: The Anti-Truncation Rule

### Background

Silicon-based agents are known to silently truncate files when performing
full-file rewrites, due to:
- token limits,
- output buffer limits,
- streaming or tooling constraints.

Such truncation may preserve syntactic validity at the top of a file while silently
deleting critical logic at the bottom (“silent lobotomy”). For this leaf, the
highest-stakes example is dropping an identifier-validation branch or a `collapse`/`align`
invariant while relocating a frame. This is an **unacceptable failure mode**.

---

### Rule: Create-Only / Edit-In-Place Separation

Silicon-based agents must follow a strict separation of file operations:

1. **Create-only operations**
   - May be used **only** to create *new* files.
   - Must not target existing file paths.
   - Overwriting an existing file is forbidden unless explicitly confirmed
     by a carbon-based agent and documented as an intentional reset.

2. **Edit-in-place operations**
   - Must be used for modifying existing files.
   - Changes must be scoped to **specific, minimal regions**.
   - Full-file rewrites of existing files are forbidden.

---

### Required Workflow

When modifying an existing file, silicon-based agents must:

1. Read the file first
2. Identify a precise, unique edit location
3. Apply a targeted replacement
4. Leave all unrelated content untouched

If a safe, targeted edit cannot be identified, the agent must stop
and request carbon-based agent guidance.

---

### Rationale

The cost of a single silent truncation event far exceeds the cost of
a cautious, multi-step edit workflow.

Reliability takes precedence over speed.

---

## Required Artifacts for Silicon-Based Agent–Assisted Changes

Every silicon-based agent–assisted change must include:

- A brief summary of *what the agent believes it changed*
- References to relevant ADRs and/or intent contracts
- Explicit declaration of uncertainty, if any
- Confirmation that no forbidden operations were performed

Absence of these artifacts is grounds for rejection.

---

## Review Posture

Silicon-based agent–generated code must be reviewed with **heightened scrutiny**.

Reviewers should assume:
- intent may be misunderstood,
- semantics may have been altered unintentionally,
- safety checks may have been weakened.

“The silicon-based agent did it” is not an acceptable justification.

Responsibility remains fully with the carbon-based agent reviewer.

---

## Enforcement

- Violations of this protocol are treated as violations by carbon-based agents
- Silicon-based agent–assisted changes may be blocked solely on protocol grounds
- Known failure modes without protocol coverage must be added explicitly

This protocol is a living document and may evolve as tools and risks change.

---

## Final Note

Silicon-based agents are tools, not collaborators.

They are powerful accelerators — and powerful failure multipliers.

This protocol exists to ensure that  
**automation never outruns understanding**.
