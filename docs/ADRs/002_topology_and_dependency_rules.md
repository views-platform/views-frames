# ADR-002: Topology and Dependency Rules

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

The entire point of `views-frames` is to fix a dependency problem. Today the same data
contract is duplicated and diverging across repos (`PredictionFrame` in
views-pipeline-core, `FeatureFrame` in views-datafactory, a third fork in views-faoapi),
and views-pipeline-core ↔ views-reporting form an **import cycle** (one direction
declared, the other hidden behind `try/except ImportError`; reporting #113). The design
bible's target is a clean **DAG**: `views-frames` is the leaf at the root, depends on
nothing internal, and every consumer depends *toward* it (README §2).

That inter-repo discipline only holds if the leaf's *internal* topology is also
controlled. Without explicit dependency rules, the frames can start importing the `io/`
layer, the validation helper can reach back into a frame, or the core can re-acquire a
`views_*` dependency (the exact mistake — `PredictionFrame` importing pandas — that the
relocation must undo). A clear rule is required to define **who may depend on whom**,
both inside the package and across the platform.

---

## Decision

This repository enforces a strict, directional dependency structure, at two levels.

> Dependencies must follow declared architectural direction.
> No component may depend on a layer above it.

**Inter-repo (the platform DAG):**
- `views-frames` depends only on `numpy` (and `pyarrow` behind `io/`). It must **never**
  import `views-pipeline-core`, `views-datafactory`, `views-evaluation`, `views-reporting`,
  or **any `views_*` package**. If it ever needs to, the boundary is wrong (README §2).
- Consumers depend *toward* `views-frames`. This is what makes it impossible for the leaf
  to participate in a cycle (ADP — it breaks reporting #113) and safe to depend on from
  everywhere (SDP).
- **Two-leaves rule:** `views-frames` and its sibling leaf `views-appwrite` are both roots
  of the DAG. **They never import each other** — there is no edge between the two leaves;
  each is depended *toward*, never sideways.

**Intra-package (the module layers):**
- `index`, `spatial_level`, `protocols`, `_validation` are the lowest layer (depend only
  on numpy / each other minimally; `index` composes `spatial_level`).
- the frame classes (`feature_frame`, `prediction_frame`, `target_frame`, …) depend on
  the index, protocols, and `_validation`.
- `io/` (`io/npz`, `io/arrow`) sits at the top, imports the frames to serialize them, and
  changes for *its own* reasons (a new disk format), not when a frame's schema changes.
- Nothing lower may import `io/`. A frame must not know how it is serialized.

Dependency direction must remain acyclic. Violations are architectural defects.

---

## Layering Principle

Where layers exist, the following invariant applies:

- Higher-level modules may depend on lower-level modules (`io/arrow` → `prediction_frame` → `index`).
- Lower-level modules must not depend on higher-level modules (`index` must not import a frame; a frame must not import `io/`).
- Cross-layer shortcuts are forbidden (a frame must not re-implement alignment instead of delegating to `SpatioTemporalIndex`; `io/` must not bypass the frame's public surface).

Dependency direction must remain acyclic.

---

## Architectural Boundaries

Each component must:

- Declare its responsibility zone (see ADR-001),
- Respect dependency direction (this ADR),
- Avoid implicit cross-layer coupling.

This ADR governs **structural dependency direction only**.

> The definition and validation of boundary contracts (the published protocols,
> construction-time invariant validation, the `cross_level_align(index, mapping)`
> injected-mapping boundary, the `io/` round-trip) are governed separately by ADR-009.

Topology defines *who may depend on whom*.  
ADR-009 defines *what must be true at the boundary*.

---

## Forbidden Patterns

Examples of architectural violations specific to this leaf:

- Any module under `views_frames` importing a `views_*` package (re-acquiring pandas via a `views-pipeline-core` import is the canonical example to avoid).
- Importing `pandas`/`polars`/`geopandas`/`wandb`/`viewser`/`torch` anywhere in the core.
- `index.py` or `_validation.py` importing a frame, or a frame importing `io/`.
- Embedding the cross-level `priogrid→country` mapping in the leaf instead of accepting it as an injected argument (ADR-009).
- An edge between the two leaves: `views-frames` importing `views-appwrite` or vice versa.

If a dependency feels "convenient but wrong," it probably is.

---

## Consequences

### Positive

- The platform DAG is preserved: the twins are de-duplicated, the reporting #113 cycle is broken (ADP), and the leaf is safe to depend on from everywhere (SDP).
- The numpy-only floor (CRP) means a model that wants a `PredictionFrame` does not transitively install the pandas/reporting world.
- Internal layering keeps the evolving `io/arrow` format from contaminating the stable frame/index contract.

### Negative

- Consumers must inject what they previously imported (e.g. pass the time-varying `priogrid→country` mapping into `cross_level_align`).
- May require additional adapters at the consumer boundary (the pandas/forecasts edges that used to live inline now live in consumer repos).

These costs are accepted intentionally.

---

## Notes

This ADR defines structural direction of dependencies.

It does not define:

- boundary contract validation (ADR-009),
- semantic authority (ADR-003),
- or testing obligations (ADR-005).

Topology governs structure.  
Contracts govern interaction.
