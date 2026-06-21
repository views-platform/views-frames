# Instantiation Checklist

Use this checklist when bootstrapping a new project from base_docs templates. Boxes are
checked to reflect the `views-frames` adaptation completed on 2026-06-21.

---

## Before You Start

- [x] Decide which adoption phase you're targeting (see `ADRs/README.md` — Recommended Adoption Order)
- [x] Identify your project's ontological categories (Spatiotemporal Index, Identifier Vocabulary, Frames, Protocols, Metadata Header, Construction Validation, Serialization Adapters — ADR-001)

---

## ADR Adaptation

### All adopted ADRs
- [x] Update Status from the template placeholder to `Accepted` (ADR-004 intentionally left `Deferred`)
- [x] Fill in Date (2026-06-21), Deciders (VIEWS platform maintainers), Informed fields

### Per-ADR adaptation notes
- [x] **ADR-000:** Path reference set to `docs/ADRs/`; grounded in the design-bible-first state
- [x] **ADR-001:** Ontology overwritten with the approved closed category set + explicit non-entities
- [x] **ADR-002:** Leaf-at-root DAG, two-leaves rule, intra-package layering defined
- [x] **ADR-003:** Forbidden-inference examples grounded (typed metadata, opaque `time`, injected mapping)
- [x] **ADR-004:** Left **Deferred**; metadata fixed; activation note (v0.1.0 / consumer pin) added
- [x] **ADR-005:** Red/beige/green grounded; conformance suite + property/copy-vs-view + falsification stubs
- [x] **ADR-006:** Grounded; first CIC subjects = `SpatioTemporalIndex`, the frames, the protocols
- [x] **ADR-007:** Tooling = Claude Code; anti-truncation rule kept; no hardened-protocol reference
- [x] **ADR-008:** Fail-loud at construction; minimal runtime logging for a value-object leaf
- [x] **ADR-009:** Protocols as published contract; construction validation; injected-mapping boundary; `io/` round-trip; uv+hatchling packaging
- [x] **ADR-010 (created):** Technical Risk Register ADR — register created empty (greenfield)

---

## CICs

- [x] Set Active Contracts in `CICs/README.md` to "No contracts yet" (no phantom contract files listed)
- [ ] Create intent contracts for non-trivial classes (deferred until `src/` exists)
- [x] `CICs/cic_template.md` left verbatim (not modified)

---

## Contributor Protocols

- [x] Reviewed and adapted `contributor_protocols/silicon_based_agents.md` (tooling = Claude Code; ADR-007 cross-ref verified)
- [x] Reviewed and adapted `contributor_protocols/carbon_based_agents.md` (solo/greenfield; gate-sequencing section added)
- [ ] Hardened protocol template — **not included** in this scaffold; no reference to it anywhere (skipped)

---

## Standards

- [x] Reviewed `standards/logging_and_observability_standard.md` — scope narrowed to a numpy-only value-object library; ADR-008 cross-ref verified
- [x] Reviewed `standards/physical_architecture_standard.md` — directory ontology rewritten to the actual `src/views_frames/` layout (README §6); one-concept-per-file enforced

---

## Governance Reports

- [x] `reports/technical_risk_register.md` created — empty register (Total/Open/Resolved = 0), tier definitions + conventions

---

## Final Verification

- [x] No files still carry the unfilled template status marker (ADR-004 is intentionally `Deferred`)
- [x] No phantom references to non-existent files (no `hardened_protocol_template.md`, no missing CIC files)
- [x] All cross-ADR references resolve correctly (000–010 exist)
- [x] Run `validate_docs.sh` to check internal consistency (PASSED)
