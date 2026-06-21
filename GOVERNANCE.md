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
(`assert_frame_contract`, `assert_index_alignment_laws`). Every consumer runs it in
CI against its own adapter output.

- **Conformance-floor version:** `0.1.0` (`views_frames.conformance.CONFORMANCE_FLOOR`).
- The floor is a **single governed version every consumer runs regardless of its
  runtime pin** — this is what makes the suite test "all consumers agree," not
  "my adapter vs my pin" (closes register C-10). The floor is bumped deliberately,
  as a governance act, not implicitly by a consumer upgrading.

## Versioning (SemVer for a contract)

- **MAJOR** — removing/renaming a field, changing a dtype or axis meaning, adding a
  **required** identifier, tightening an invariant.
- **MINOR** — a new frame type, a new **optional** metadata field or identifier, a
  new method, a new `io/` format.
- **PATCH** — bug/doc fixes with an identical contract.

## Cross-repo MAJOR-bump process

A MAJOR change is never a silent break:

1. Propose it as an ADR (the decision + the migration).
2. Land it behind `from_legacy_*` shims where a consumer format changes.
3. Bump the conformance floor and coordinate a merge-train across consumers.

If the package needs frequent MAJOR bumps, it is not abstract/stable enough —
push the volatility out into consumer adapters (SAP).
