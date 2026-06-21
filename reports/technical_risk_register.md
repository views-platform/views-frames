# Technical Risk Register

| Register Info     | Details                              |
|-------------------|--------------------------------------|
| Project           | views-frames                         |
| Owner             | VIEWS platform maintainers           |
| Last Updated      | 2026-06-21                           |
| Total Concerns    | 0                                    |
| Open Concerns     | 0                                    |
| Resolved Concerns | 0                                    |

---

## Tier Definitions

| Tier | Severity | Description |
|------|----------|-------------|
| 1 | Critical | Silent data corruption or output correctness risk. Requires immediate attention. |
| 2 | High | Structural fragility that will cause failures under realistic change scenarios. |
| 3 | Medium | Maintainability or coupling issues that increase cost of change. |
| 4 | Low | Code quality concerns that do not affect correctness or reliability. |

---

## Open Concerns

_None. The register is empty._

`views-frames` is a design-only repository (a README design bible, consumer perspectives,
critiques, and falsification stubs — no `src/` yet). Prior critique and falsification
findings live in `critiqus/` and the `tests/` falsification stubs; register them here via
the `register-risk` skill when a maintainer chooses to track them formally — for example
when the leaf is stood up and the external-repo locations they reference become concrete.

---

## Disagreements

_None recorded._

---

## Resolved Concerns

_None._

---

## Register Conventions

- **ID format:** `C-xx` for concerns, `D-xx` for disagreements. IDs are permanent — gaps in numbering indicate merged or resolved entries.
- **Sources:** `repo-assimilation`, `expert-review`, `test-review`, `falsification-audit`, `persona-critique`, `clean-architecture-review`, `pr-review`, `tech-debt-audit`, `incident`, `manual`.
- **Resolution:** Move to "Resolved Concerns" with resolution date and summary when addressed.
- **Header counts:** Manually maintained — update whenever a concern is added or resolved.
- **Note:** Future concerns will often reference locations in external repos (`views-pipeline-core`, `views-datafactory`, `views-faoapi`, `views-reporting`) because this leaf de-duplicates a data contract not yet relocated. Confirm those locations when the package is stood up.
- **Governed by:** ADR-010 (`docs/ADRs/010_technical_risk_register.md`).
