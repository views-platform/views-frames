# ADR-026: Dense-grid fill is a leaf primitive (`reindex_fill` + `cartesian`)

**Status:** Accepted
**Date:** 2026-07-27
**Deciders:** VIEWS platform maintainers
**Consulted:** expert-code-review (2026-07-27, design review of issue #203)
**Informed:** views-faoapi (ingestion, #242), views-pipeline-core, views-postprocessing

---

## Context

faoapi's ingestion still builds its dense forecast grid with pandas, and its docstring
names the reason explicitly: *"views-frames has no fill primitive"*
(`views-faoapi/.../forecast/ingestion/dense_grid.py:3`). That is the last hard blocker on
a pandas-free FAO ingestion edge (faoapi #242; filed here as #203). The operation itself —
align a sparse frame to a complete `(time × unit)` target index and fill absent cells —
is **same-level structural alignment**, the responsibility category `SpatioTemporalIndex`
already owns (`select`/`reindex`/`searchsorted`/`intersect`). It is not an adapter, not
geography, and not policy: it touches only values + identifier arrays.

The machinery half-exists: `searchsorted` returns **-1 for absent rows** (F4-hardened for
the empty index), and frame-level `reindex` is `select(searchsorted(other))` behind a
fail-loud superset guard. What is missing is the materialization of the -1 positions as a
fill — and that missing piece is a genuine silent-corruption hazard when consumers
hand-roll it: `values[pos]` with a -1 in `pos` silently selects the **last row** (numpy
negative indexing) for every absent cell.

## Decision

Two additive symbols (MINOR, v1.10.0; `CONFORMANCE_FLOOR` stays `1.0.0`):

1. **`frame.reindex_fill(other, *, fill_value)`** on all three sibling frames (WET per
   ADR-011). Align to `other`'s rows with **no superset requirement**: present rows come
   through **bit-exact**; absent rows get `fill_value` broadcast across the trailing
   axes. `fill_value` is **keyword-only and required** — no silent default (ADR-009); the
   caller states its policy (`0.0` vs `NaN`) aloud. The result's index **is** `other`
   (immutable, shared); metadata (and `feature_names`) are preserved. The C-21
   row-uniqueness stance is inherited unchanged: unique rows assumed in *self*,
   duplicates allowed in the target (a `cross_level_align` product is a legal target).

2. **`SpatioTemporalIndex.cartesian(times, units, level)`** — the dense product-index
   constructor, **time-major** order as contract (dense indices are canonical across
   consumers). **Explicit arrays only**: any rule for deriving them (faoapi's
   "units of the last time step" + dropped-entity check, their C-87) is consumer policy
   and never lives in the leaf. **Fails loud on duplicated inputs** — a duplicated
   product input manufactures duplicate `(time, unit)` rows, which make every same-level
   join undefined (C-21); in a product constructor that is always a caller bug.

3. **`assert_reindex_fill_law`** joins the published conformance suite (ADR-016): result
   index equals the target row-for-row; present rows bit-exact; absent rows equal the
   fill (NaN-safe); on a superset frame the fill degenerates to `reindex`.

## Alternatives considered

- **A `fill_value=None` kwarg on the frozen `reindex`** — rejected: one symbol, two
  contracts (fail-loud vs fill) is the mode-switch shape D-09 (#113) already rejected;
  under the ADR-018 freeze it could never be untangled.
- **Index-level only (consumers scatter themselves)** — rejected: it pushes the -1
  sentinel into every consumer *untested*; the wrap-to-last-row failure is silent wrong
  data, the class of bug this leaf exists to remove.
- **Decline (keep fill consumer-side)** — rejected: the need is receipted
  (`dense_grid.py:3`), blocks faoapi #242, and per-consumer numpy reimplementations
  would each carry the hazard above.
- **A derivation rule in `cartesian`** (e.g. "observed times × last-step units") —
  rejected permanently: that complects policy with structure (the C-52 accretion guard
  names exactly this camel's nose). If a "derive the dense grid" convenience is ever
  demanded, it belongs consumer-side.

## Consequences

- faoapi's `dense_grid.py` can delegate: build its entity set + C-87 check (policy,
  stays theirs), call `cartesian`, then `reindex_fill` — and drop pandas (verified in
  faoapi #242, acted on by the maintainers, never from this repo).
- Densification **allocates the full dense buffer** (`other.n_rows × …`): a full-pgm
  grid runs to tens of millions of rows, and at large S the values buffer alone can
  reach memory-breaking size. This is inherent to densifying, stated in both
  docstrings, and tracked in the register — the leaf does not guess a size guard
  (policy).
- Scalar fill only, deliberately minimal: a per-row/vector fill would be a future
  additive overload if a consumer ever receipts the need.
- The frozen surface grows by three symbols that can never be removed short of a MAJOR
  (ADR-018) — accepted on the receipted need and the silent-corruption argument.
