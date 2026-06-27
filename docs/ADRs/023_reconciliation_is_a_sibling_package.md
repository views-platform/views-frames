
# ADR-023: Forecast reconciliation is a sibling package, not the leaf and not postprocessing

**Status:** Accepted
**Date:** 2026-06-26
**Amended:** 2026-06-27 — sample-count contract (point-broadcast vs aligned-draws), v1.8.0, #143
**Deciders:** VIEWS platform maintainers
**Consulted:** views-postprocessing (the current, mis-homed host), views-reporting (the frozen torch oracle)
**Informed:** views-pipeline-core, views-models, views-evaluation

---

## Context

Forecast **reconciliation** — making grid (`pgm`) predictions sum to their country (`cm`) totals
(`reconcile_proportional` + `ReconciliationModule`, **numpy + `views_frames` only**, parity-proven against
the frozen views-reporting torch oracle in views-postprocessing PR #30) — currently lives in
**views-postprocessing** (`views_postprocessing/reconciliation/`). A read-only trace of the real code
established the facts:

- **It is a frame→frame operation**, structurally identical to `views_frames_summarize`: numpy on
  `PredictionFrame`s, `views_frames`-only, no IO, no actuals. It takes a pgm frame + a cm frame and returns a
  new pgm frame whose cells sum (per draw) to the country totals. That is a *universal frame operation*, not a
  partner-delivery concern.
- **views-postprocessing does not use it.** views-postprocessing is a partner-delivery repo (the UN-FAO path
  sums by construction and never reconciles). Housing the reconciler there *stretched* that repo's scope and
  forced an **injection dance** to dodge a dependency cycle — views-postprocessing sits *above*
  pipeline-core, so pipeline-core could not import the reconciler directly and had to have it injected
  (pipeline-core #195 / PR #217).
- **It is the same category as summarization** (ADR-017): one correct, tested, numpy-only implementation of a
  frame operation that belongs with the frame types it operates on, not scattered across downstream repos.
  Three reconciler copies are currently in flight — views-reporting (torch, the live production path),
  views-postprocessing (parity-proven but stranded — pipeline-core was never repointed to it), and this one.

The frames foundation is the correct home. **CRP/screaming** — frame operations belong with the frame types
and the other frame operations (`views_frames_summarize` set the precedent). **SDP** — a stable, numpy-only
library belongs *low* in the dependency graph, where pipeline-core already depends, so consumers can import
it **directly**: no cycle, no injection ceremony.

This is **correctness/home work, not cosmetics**. It completes a stranded migration (views-postprocessing
risk C-42); production keeps working on the old views-reporting path until the cutover, so it is *not urgent*
— the priority is getting parity exactly right.

---

## Decision

Forecast reconciliation lives in a **third package in this repo**, `views_frames_reconcile` (the
`src/views_frames_*` multi-package pattern used by views-datafactory, already used for
`views_frames_summarize`). It depends on `views_frames` + numpy only; `views_frames` **never** imports it
(enforced by `tests/test_import_enforcement.py`). It is a faithful **WET** relocation of the
parity-proven views-postprocessing reconciler — *the same algorithm*, re-homed — and on release becomes the
canonical copy.

### Charter (bounded — this is what prevents back-door bloat)

`views_frames_reconcile` **may** contain: forecast-reconciliation **algorithms on frames** (hierarchical /
cross-sectional coherence; the top-down proportional method, applied per posterior draw); per-sample
reconciliation; fail-loud input validation; array→frame construction adapters local to reconciliation; and a
conformance suite.

It **must not** contain: IO (that is `views_frames`); **fetching the `(time, unit) → country` mapping** — the
mapping is **injected by the caller as numpy arrays**, exactly like `cross_level_align` (ADR-014;
data-from-producer / register C-20); actuals or scoring (that is views-evaluation); plotting; or imports of
any `views_*` except `views_frames` (and `views_frames_summarize` only if a real need arises).

> **The mapping is never fetched here.** The `(time, priogrid_gid) → country_id` mapping is the caller's
> responsibility, sourced from the producer (views-datafactory / viewser) and passed in as `(map_keys,
> map_vals)` arrays. `views_frames_reconcile` owns the *operation*; it never embeds or fetches geography. This
> is asserted in the conformance suite, not just documented.

### Sample-count contract: point-broadcast vs aligned-draws (amended 2026-06-27, #143)

`ReconciliationModule.reconcile` accepts a country (`cm`) frame whose `sample_count` is either **`1`**
(a *point* forecast) or **`S`** (the grid's draw count); any other count fails loud in validation. A point
`cm` is **broadcast** to `S` draws by tiling its single column (`np.tile`) inside the orchestrator
(`module.py`), *before* the unchanged aligned-draws reconcile path runs — so the equal-count path stays
**bit-for-bit identical** (the broadcast triggers only for `sample_count == 1`; the leaf `proportional` and the
parity-frozen `grouping` hot loop are untouched). This is the DRY home of pipeline-core's WET
`align_country_to_grid` (the consumer explicitly earmarked it for here, #143). The **aligned-draws** case
remains the documented *per-draw approximation*: pairing grid-draw `s` with country-draw `s` across
independently-trained models has no shared draw identity — the principled joint upgrade is a separate design
(#145; the pragmatic-vs-principled boundary the `proportional` docstring names).

### Import-DAG

`views_frames_reconcile → {views_frames}` (+ numpy / stdlib). Added to `ALLOWED_INTERNAL` in
`tests/test_import_enforcement.py`; `FORBIDDEN = {pandas, polars, geopandas, wandb, viewser, torch}`
unchanged.

### SemVer

A new sibling package is **additive ⇒ MINOR**: **1.6.0 → 1.7.0**. `CONFORMANCE_FLOOR` stays `1.0.0`.

The 2026-06-27 amendment (the point-broadcast sample-count contract, #143) is an **additive input-contract
relaxation** — `reconcile` accepts a new input shape (`cm.sample_count == 1`) it previously rejected, and no
existing call changes ⇒ **MINOR: 1.7.0 → 1.8.0**. `CONFORMANCE_FLOOR` stays `1.0.0` (the frozen leaf surface
is untouched; the broadcast lives entirely in `views_frames_reconcile`).

---

## Rationale

This is "what changes together stays together," applied the same way ADR-017 applied it to summarization. The
**data contract** is one closure group (stable → `views_frames`); **summarization statistics** are another
(`views_frames_summarize`); **reconciliation** is a third — a numpy-only frame operation that versions and
tests *with the frame types it transforms*. Same repo means one CI (a frame change breaks reconciliation's
tests immediately) with no cross-repo brittleness; the import-DAG keeps the leaf provably pure; CRP holds
(a contract-only or summarize-only consumer never imports the reconciler).

Landing it **low** in the DAG (SDP) is the structural payoff: pipeline-core already depends on `views_frames`,
so once this ships, the injection that existed only to dodge the views-postprocessing cycle can **collapse to
a direct import** — the port's only reason to exist vanishes.

**WET before DRY.** This ADR ratifies a *faithful relocation*, not a rewrite. `grouping.py` overlaps the
leaf's `cross_level_align` (it already *uses* `index.cross_level_align_arrays` to label grid rows), but
folding the two together is explicitly **out of scope** — the relocation must be bit-identical to the proven
original first. The DRY pass (reconciliation grouping ↔ `cross_level_align`) is a separate, later story. So is
the principled probabilistic-reconciliation upgrade (views-postprocessing C-37), which will be a *sibling
module*, never a modification of the proportional method.

---

## Considered Alternatives

### Alternative A: keep reconciliation in views-postprocessing
- **Pros:** no move; it already works and is parity-proven there.
- **Cons:** a partner-delivery repo hosts a frame operation it never uses; pipeline-core can't import it
  directly (vpp is above it), so the cycle-dodging injection is permanent; the foundation operation is stuck
  high in the DAG.
- **Reason for rejection:** wrong layer (SDP) and wrong closure group (CRP); the injection ceremony is pure
  accidental complexity caused by the mis-home.

### Alternative B: a new standalone reconciliation repo
- **Cons:** microservice sprawl; a frame operation separated from the frame types it operates on; another CI,
  another release cadence, another version to pin.
- **Reason for rejection:** same "quick, safe, low-maintenance" failure ADR-017 rejected for summarization.

### Alternative C: fold reconciliation into the leaf `views_frames`
- **Cons:** the leaf is the maximally-stable data contract (SAP); a forecast-redistribution *method* (with a
  pending probabilistic upgrade) is an operation that will evolve, not a structural contract. Putting it in
  the leaf makes every reconciliation change a leaf release everyone eats.
- **Reason for rejection:** breaks SAP and the leaf's identity, exactly as Alternative A did in ADR-017.

---

## Consequences

### Positive
- The leaf stays provably pure (import-DAG enforced); the frames family owns "frame types + universal frame
  operations" (summarize, now reconcile).
- One tested, canonical reconciler, low in the DAG — consumers import it **directly**; the cycle-dodging
  injection can collapse.
- views-postprocessing stops hosting a lodger it does not use.

### Negative
- A third package to maintain (mitigated: same repo, one CI, numpy-only, bounded charter).
- A transient period with reconciler copies in three repos until the cutover (release → repoint → delete) —
  managed by the Epic 11 tracking checklist and gated on this release; nothing downstream moves until v1.7.0
  ships.

---

## Implementation Notes

- `src/views_frames_reconcile/` added to `[tool.hatch.build.targets.wheel] packages` (one wheel, now three
  importable packages). Flat layout, one concept per file (mirrors `views_frames_summarize`): `proportional`,
  `grouping`, `frames`, `validation`, `module`, `conformance`, `__init__` (+ `py.typed`).
- `tests/test_import_enforcement.py` gains `"views_frames_reconcile": {"views_frames"}` in `ALLOWED_INTERNAL`.
- The 6 reconciler modules are ported **WET** from views-postprocessing — *import lines only* changed
  (`views_postprocessing.reconciliation` → `views_frames_reconcile`); no algorithmic change.
- Parity is the gate: the frozen views-reporting torch-oracle `.npz` fixtures (`allclose`) **and** a
  transitional new-vs-old **bit-identity** head-to-head (`views_frames_reconcile` vs the old
  `views_postprocessing.reconciliation` on fresh synthetic seeds, `np.array_equal` on float32).
- **Consumer repoint (views-models #191) and views-postprocessing deletion (#62) are out of scope and
  cross-repo — gated on this release. No sibling repo is modified by this work.**

---

## Validation & Monitoring

- The import-DAG test is the guardrail: if `views_frames` ever imports `views_frames_reconcile`, or the
  reconciler imports anything beyond `views_frames` + numpy, CI fails.
- Parity tests reproduce the frozen oracle; the head-to-head proves bit-identity with the stranded vpp copy at
  the moment of relocation.
- The conformance suite asserts the contract (sum-to-country per draw, zeros preserved, non-negativity,
  **mapping injected — never fetched**, level correctness).
- Failure mode to watch: any non-reconciliation concern (IO, domain data / fetched mapping, scoring, plotting,
  foreign `views_*`) appearing in `views_frames_reconcile` — reject per the charter.

---

## Open Questions

- The DRY pass folding `grouping.py`'s row-labelling into the leaf's `cross_level_align` — deferred to a later
  story, only after parity is locked.
- The principled probabilistic-reconciliation method (views-postprocessing C-37) — a future *sibling module*,
  never a modification of `proportional`.
- **Reconciliation-mode provenance (#144):** the mode (`point-broadcast` vs `aligned-draws`) is **returned**
  on a `ReconciliationResult` from `reconcile_result`, **not** stamped on the leaf's generic `FrameMetadata`
  — that header is governed *generic-only* (ADR-020 / register C-47), so reconciliation vocabulary stays in
  the sibling package, off the numpy leaf (decision recorded as register D-12).

---

## References

- ADR-017 (summarization is a sibling package — the precedent this mirrors); ADR-014 (cross-level mapping is
  injected by the caller, never embedded/fetched); README §0/§6 (multi-package layout).
- Evidence: `views-postprocessing/views_postprocessing/reconciliation/` (the parity-proven source);
  views-postprocessing PR #30 (oracle parity), risk C-42 (stranded migration), C-37 (probabilistic upgrade).
- Epic #131; stories #132–#138; cross-repo cutover pipeline-core #221, views-models #191,
  views-postprocessing #62.
