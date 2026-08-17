# ADR-002: Topology and Dependency Rules

**Status:** Accepted (amended 2026-08-17 — see *Amendment* below)  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

> **Amendment (2026-08-17, register C-82).** This ADR originally stated that `io/` *"sits at
> the top, imports the frames to serialize them"*, that *"nothing lower may import `io/`"*,
> and it listed *"a frame importing `io/`"* under **Forbidden Patterns**. **The code runs the
> other way, and the code is right.** `io/npz` and `io/arrow` import only `_typing`; all
> three frames import `io` and call `npz.save` / `npz.load`.
>
> The **decision** has not changed — dependency direction is still strictly one-way and
> acyclic (verified with `grimp`: 36 modules, 89 dependencies, zero cycles). What was wrong
> was this ADR's factual claim about which way `io/` runs. Three things fixed it:
>
> 1. **`Persistable` puts persistence on the frame.** `save`/`load` are frame methods, frozen
>    under ADR-018. Once persistence is a frame method the frame must reach the serializer.
> 2. **C-09 is the origin.** Resolving it (2026-06-21, v0.1.0) moved `io/npz` onto a generic
>    frame-**state** contract so the I/O layer would carry no per-frame schema. That is what
>    inverted the dependency; this ADR was never amended to match.
> 3. **The result serves this ADR's own goal better than its original prescription.** The
>    stated aim was that `io/` change *"for its own reasons, not when a frame's schema
>    changes."* `io/` never importing a frame is a stronger guarantee of that than `io/`
>    importing three of them.
>
> Correcting the code was not available: removing `save`/`load` from the frames is a MAJOR
> bump with a cross-repo merge train (GOVERNANCE.md), to fix a documentation error. The
> layering is now machine-enforced in the correct direction by the `import-linter` contracts
> in `pyproject.toml` (`uv run lint-imports`). The same claim in
> `docs/standards/physical_architecture_standard.md` was corrected in the same change.

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
controlled. Without explicit dependency rules, the codecs under `io/` can start importing
the frames, the validation helper can reach back into a frame, or the core can re-acquire a
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

**Intra-package (the module layers).** Ten modules, lowest layer first:

- `_typing`, `metadata`, `spatial_level` are the lowest layer: they depend only on numpy
  and the standard library. `_typing` has the highest fan-in in the leaf — every module
  that touches an identifier array imports `IntArray` from it.
- `_validation` and `io/` (`io/npz`, `io/arrow`) sit above them and import only `_typing`.
  Both operate on **raw arrays**, never on a frame: `_validation` checks dtype/shape/length,
  and `npz.save` takes `values`, `time`, `unit`, `level` and `metadata` as separate
  arguments. Neither imports a frame class, so a frame's schema cannot ripple into either.
- `index` (`SpatioTemporalIndex`) composes `spatial_level` and delegates its invariants to
  `_validation`.
- `protocols` sits above `index` (it references `SpatioTemporalIndex` in its type surface)
  and declares the four segregated protocols the frames satisfy structurally.
- the frame classes (`feature_frame`, `prediction_frame`, `target_frame`) are the top
  layer: they compose the index, validate through `_validation`, carry a `metadata`
  header, and **call down into `io/`** to serialize themselves.
- `conformance/` is also a top-layer consumer — it validates frames from outside and
  imports nothing internal at all (it duck-types against `Any`).

Dependency direction must remain acyclic. Violations are architectural defects.

> **Why the frames call `io/`, and not the reverse.** `Persistable` (`protocols.py`) places
> `save`/`load` **on the frame** — that is the published surface a consumer holds, and it is
> frozen under ADR-018. Once persistence is a frame method, the frame must reach the
> serializer. The decoupling this ADR wants is preserved by the *opposite* mechanism from
> the one originally written here: because `io/` never imports a frame, a change to a
> frame's schema cannot propagate into the codecs at all. See the Amendment above.

---

## Layering Principle

Where layers exist, the following invariant applies:

- Higher-level modules may depend on lower-level modules (`prediction_frame` → `index` → `spatial_level`; `prediction_frame` → `io/npz` → `_typing`).
- Lower-level modules must not depend on higher-level modules (`index` must not import a frame; `io/` must not import a frame).
- Cross-layer shortcuts are forbidden (a frame must not re-implement alignment instead of delegating to `SpatioTemporalIndex`; `io/` must not reach back into a frame's public surface — it is handed raw arrays).

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
- `index.py`, `_validation.py`, or anything under `io/` importing a frame. (A frame importing
  `io/` is **correct** — see the Amendment. It was listed here in error until 2026-08.)
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
