
# ADR-014: Cross-level (cm↔pgm) alignment — leaf owns the protocol, consumer injects the mapping

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Consulted:** views-faoapi (producer-materialised-metadata existence proof)
**Informed:** views-reporting, views-pipeline-core

---

## Context

The leaf's headline value is "giving arrays the label-alignment that today drags pandas back
in." For **same-level** alignment that is true and domain-free. But both downstream consumers
also ask the index for the **cross-level** cm↔pgm (country↔grid) join. A Popperian falsification
audit (5 hard falsifications) proved that join requires an external,
viewser-sourced, **time-varying** `priogrid→country` mapping — a cell's country assignment
changes by month (`previous_country_id`). Embedding that mapping breaks the leaf's no-domain
(§3/§11) and maximal-stability (§8) constraints; fetching it breaks no-`views_*`. This is the
single most load-bearing boundary decision in the package (C-14, C-15, D-01).

---

## Decision

Split alignment **logic** from alignment **data**:

- **Same-level alignment** (intersect / align / reindex / searchsorted over `(time, unit)` at a
  single `SpatialLevel`) lives in the leaf, pure-numpy, unconditionally.
- **Cross-level alignment** is exposed as a **protocol only**: the leaf owns the operation
  signature `cross_level_align(index, mapping)`. The time-varying `priogrid→country` **mapping**
  is **injected by the consumer** (or sourced from a separate reference package the leaf does not
  depend on). The leaf **never embeds, fetches, or versions** the mapping.

The mapping is **producer-materialised metadata** — the pattern `views-faoapi` already runs in
production (9 pre-joined metadata columns from the `un_fao` postprocessor).

---

## Rationale

This is the only configuration of the leaf that satisfies both conjuncts ("domain-free + stable"
**and** "delivers cross-level alignment"): the generic one-to-many expansion logic is domain-free
and stays in the leaf; the versioned geographic *data* stays with the consumer/producer that owns
it. It keeps the leaf maximally stable (it never changes when GAUL/priogrid metadata revises) and
keeps the no-domain boundary intact, while still giving consumers a single typed entry point for
the join.

---

## Considered Alternatives

### Alternative A: embed the `priogrid→country` mapping in the leaf
- **Pros:** the leaf could deliver the join with no consumer wiring.
- **Cons:** the mapping is time-varying reference data → the leaf MAJOR-bumps on metadata
  revisions, breaking §8 maximal stability; violates no-domain (§3/§11).
- **Reason for rejection:** falsified — self-defeating (the cross-level falsification audit).

### Alternative B: the leaf fetches the mapping from viewser
- **Pros:** always current.
- **Cons:** imports `viewser` into the core — directly forbidden by §3.1.
- **Reason for rejection:** breaks the leaf's defining constraint.

---

## Consequences

### Positive
- Both conjuncts of the thesis stay true; the leaf stays a leaf.
- Consumers get one typed `cross_level_align` entry point instead of N hand-rolled joins.
- Closes C-14 and C-15; resolves D-01.

### Negative
- The leaf does **not** "deliver" the cross-level join end-to-end — consumers must supply the
  mapping. The §4.3 pitch is correspondingly narrowed (documented). Accepted.

---

## Implementation Notes

- `index.py` / `protocols.py`: define `cross_level_align(index, mapping)` (or a `CrossLevelAligner`
  protocol). The `mapping` parameter is `(time, priogrid) → country` (time-aware), supplied by the
  caller. No `priogrid→country` constant ships in the leaf.
  - **v0.3.0 (register C-20):** `mapping` is concretely typed `Mapping[tuple[int, int], int]`,
    keyed by the `(time, unit)` tuple, and the remap is vectorized (void-viewed keys +
    `searchsorted`). The earlier `Mapping[int, int]` (unit-only) implementation could not express
    a cell whose country changes by month and is now a fail-loud error.
- The import-enforcement test (C2, ADR-002) guarantees no `viewser`/`views_*` import can sneak in.
- Producers (e.g. views-datafactory's area-majority GAUL work, ADR-044 there) materialise the
  mapping; consumers inject it.

---

## Validation & Monitoring

- Conformance property: `cross_level_align` requires a `mapping` argument and the leaf ships no
  embedded `priogrid→country` table (a test asserts absence).
- The pass-1 falsification stubs (`tests/test_falsification_domain_free_crosslevel.py`) guard the
  boundary in the README; keep them green.
- Failure mode to watch: any commit adding a static country/grid table or a `viewser` import.

---

## Open Questions

- The exact shape of the injected `mapping` object (array of `(time, priogrid, country)` vs a
  callable) — to be pinned in the `SpatioTemporalIndex` CIC (D1).

---

## References

- README §4.3, §13a.4, §3/§11/§8; the cross-level falsification audit (5 hard falsifications) and a
  follow-on falsification audit; faoapi's producer-materialised metadata as the existence proof.
- Evidence: `views-reporting/metadata/entity_metadata.py:10,45-75,147`, `views-reporting/reconciliation/reconciliation.py:15,74,96`.
- Risk register: **C-14**, **C-15**; disagreement **D-01** (resolved).
- Issue #5; Epic #13.
