
# ADR-015: `SpatialLevel` relocation — identifier vocabulary only, fix-don't-port

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Informed:** views-pipeline-core (current owner), views-datafactory, views-faoapi, views-reporting

---

## Context

`SpatialLevel` (today `views-pipeline-core/.../domain/spatial.py`) is the value object that
defines the cm/pgm vocabulary — `entity_column` and `index_names` (cm→`country_id`,
pgm→`priogrid_id`). It is a tiny, stdlib-`enum`-only object and is genuinely part of the
identifier vocabulary, so it belongs in the leaf. But the falsification audit found the current
implementation carries two latent defects, and "relocate verbatim" would ship both into the
keystone every repo imports (C-18, a falsification audit):

1. **C-65 — reversed index tuple:** `_INDEX_NAMES` is entity-first (`("priogrid_gid","month_id")`)
   while every real DataFrame is time-first `(month_id, entity)`.
2. **gid/id inconsistency:** `index_names` uses `priogrid_gid` (pre-rename) while `entity_column`
   uses `priogrid_id` (post-rename) — the same object disagrees with itself.

---

## Decision

Relocate `SpatialLevel` into `views-frames` (`src/views_frames/spatial_level.py`) as identifier
**vocabulary only**, and **fix, do not port**, both defects:

- index tuples become **time-first** `(month_id, entity)`;
- the `priogrid_gid`/`priogrid_id` naming is made internally consistent (single canonical name).

`SpatialLevel` carries level **labels** (`entity_column`, `index_names`) and nothing else — never
the cross-level mapping (ADR-014), never unit values, ranges, or the grid backbone. The cm/pgm
distinction is a **value** on the index, never a class axis (collapses the `CMDataset/PGMDataset`
hierarchy; pipeline-core D-33).

---

## Rationale

The label vocabulary is tiny and maximally stable — exactly what a leaf should own — and owning
it ends the bare-string `"cm"`/`"pgm"` sprawl and the `_ViewsDataset` private `_entity_id` reads
across three repos. But relocation is the moment to fix the two defects, not entrench them: a
wrong-order index contract or a self-inconsistent identifier name in the keystone is the worst
possible place for a latent bug. "Relocation ≠ cleanup" is the explicit lesson of the falsification audit.

---

## Considered Alternatives

### Alternative A: import `SpatialLevel` from a shared `views-domain` package
- **Pros:** a single home for all domain vocabulary.
- **Cons:** no such package exists; creating one is scope the leaf does not need, and the labels
  are small and stable enough to live here.
- **Reason for rejection (for now):** premature; revisit only if a `views-domain` package
  materialises for other reasons.

### Alternative B: relocate verbatim
- **Pros:** least immediate effort.
- **Cons:** ships C-65 + the gid/id inconsistency into the keystone.
- **Reason for rejection:** entrenches known bugs in the most-imported package.

---

## Consequences

### Positive
- One canonical, correct level vocabulary; ends bare-string sprawl and private `_entity_id` reads.
- Closes C-18; enables collapsing the cm/pgm class hierarchy into a value.

### Negative
- Fixing the index-tuple order is a (small) behaviour change for any current consumer that relied
  on the entity-first order — must be audited at relocation time and shimmed if needed. Accepted.

---

## Implementation Notes

- `spatial_level.py`: stdlib `enum` only (the import-enforcement test guarantees numpy/no-domain
  purity). Expose `entity_column` and time-first `index_names`.
- At relocation, grep consumers for reliance on the old entity-first tuple order and the
  `priogrid_gid` spelling; provide a `from_legacy_*`/shim where required.
- Document that `SpatialLevel` is *labels only* in its CIC (D1), with the cross-level mapping
  explicitly out (ADR-014).

---

## Validation & Monitoring

- Conformance/property: `index_names[0]` is the time column for every level (time-first); the
  `priogrid` entity name is identical across `index_names` and `entity_column`.
- Failure mode to watch: any reintroduction of an entity-first tuple or a second priogrid spelling.

---

## Open Questions

- The single canonical priogrid spelling (`priogrid_id` vs `priogrid_gid`) — pick one at
  relocation and apply it everywhere; coordinate with the `views-faoapi` rename shim (its C-61).

---

## References

- README §4.3, §13a.5; a falsification audit.
- Evidence: `views-pipeline-core/.../domain/spatial.py` (`_INDEX_NAMES`, `index_names` vs `entity_column`).
- Risk register: **C-18** (subsumes original C-04).
- Issue #6; Epic #13.
