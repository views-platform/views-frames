
# Class Intent Contract: views_frames_reconcile

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-06-28
**Related ADRs:** ADR-002, ADR-003, ADR-006, ADR-008, ADR-014, ADR-020, ADR-023, ADR-024

> The `views_frames_reconcile` package — forecast reconciliation as a `views_frames`
> sibling (numpy + `views_frames` only). Implemented in **v1.7.0** (Epic 11, ADR-023): a
> faithful numpy port of views-reporting's top-down proportional reconciler. Extended
> **additively in v1.8.0** (epic #142) with a native **point-country broadcast** and a
> self-describing **reconciliation mode** (`reconcile_result` → `ReconciliationResult`;
> ADR-024 designs the deferred principled upgrade). `CONFORMANCE_FLOOR` stays `1.0.0`.
>
> This is a **package-level** contract (the package is functions + two small classes, not
> one class). It governs the public surface re-exported from
> `src/views_frames_reconcile/__init__.py`: `ReconciliationModule`, `ReconciliationResult`,
> `reconcile_proportional`, and the `POINT_BROADCAST` / `ALIGNED_DRAWS` /
> `METHOD_PROPORTIONAL` mode/method constants — plus the package's own array→frame builder
> `prediction_frame_from_arrays` (`frames.py`) and the `assert_reconcile_contract`
> conformance check (`conformance.py`).

---

## 1. Purpose

Reconcile **PRIO-GRID-month (`pgm`) forecasts to their country-month (`cm`) totals**: make
each country's grid cells sum, **per posterior draw**, to that country's forecast, by
**top-down proportional disaggregation** (FPP3 forecast-proportions). It is the
frames-native home of the algorithm views-reporting used to own — moved here because
reconciliation belongs in post-processing, not reporting (views-reporting #72). One target
per call; geography is **injected**, never embedded (ADR-014).

---

## 2. Non-Goals (Explicit Exclusions)

- **No geography embedding** — the `(time, priogrid_gid) → country_id` mapping is injected
  as arrays (`map_keys`/`map_vals`); the package never fetches, embeds, or infers it
  (ADR-014). It holds no shapefiles, no PRIO-GRID↔country table.
- **No IO of domain data, no plotting, no scoring** — it transforms frames to frames.
  `prediction_frame_from_arrays` is the package's *own* array→frame adapter, not a
  general loader; comparing forecasts to actuals is views-evaluation.
- **No principled joint probabilistic reconciliation (C-62 / ADR-024)** — the shipped
  method is a **pragmatic per-draw approximation**: it pairs grid-draw `s` with
  country-draw `s`. When grid and country models are trained independently (today's
  platform reality), draw index `s` has **no shared identity**, so the joint country
  distribution is **not guaranteed calibrated**. This is a known, documented method-quality
  limitation with a designed-but-deferred upgrade (ADR-024); it is **not** silently treated
  as principled.
- **No reconciliation *mode* stamped on the leaf frame (ADR-020 / register C-47, D-12)** —
  the mode is *reported* on `ReconciliationResult`, never written into the leaf's generic
  `FrameMetadata` (which must carry no reconciliation/operation vocabulary).
- **No `views_*` import except `views_frames`; no torch, no pandas, no viewser, no wandb**
  (enforced by the import-DAG test). The original's `ProcessPoolExecutor` + WandB alerting
  are deliberately dropped.

---

## 3. Responsibilities and Guarantees

`ReconciliationModule(map_keys, map_vals)` holds the injected mapping and applies it:

- `reconcile(cm_frame, pgm_frame)` → a **new** `pgm` `PredictionFrame`: validates the
  inputs, then scales each country's grid cells to the country total. Returns only the
  frame.
- `reconcile_result(cm_frame, pgm_frame)` → a `ReconciliationResult(frame, mode, method)`:
  the same reconciled frame **plus** the mode it was produced by (`POINT_BROADCAST` |
  `ALIGNED_DRAWS`) and the method (`METHOD_PROPORTIONAL`). `reconcile` is exactly
  `reconcile_result(...).frame`.

Guarantees on the reconciled frame (per the conformance laws,
`conformance.assert_reconcile_contract`):

- **Sum-to-country per active draw** — for each `(time, country)` group, the cells' per-draw
  sum equals that country's forecast for that draw, to `rtol=1e-4, atol=1e-3`.
- **Zero-preservation** — an input zero cell stays exactly zero; an **all-zero country draw
  stays zero** (the documented edge — it is not rescaled to the country total, since there
  is no mass to distribute).
- **Non-negativity** — every reconciled value is `≥ 0` (the leaf clamps).
- **Structure preserved** — same `(N, S)` shape, same `PredictionFrame` type, same
  `SpatialLevel.PGM` level, same `time`/`unit` index as the input `pgm_frame`.
- **De-mutation** — the input `pgm_frame` (and its `values` buffer) is **never mutated**; a
  new frame is returned (register C-184).
- **Injected mapping is honoured, not fetched** — the sum-to-country law holds only because
  each cell is grouped under its *injected* country; permuting `map_vals` changes the result.

**Mode contract (`reconcile_result`).** The mode describes **what this call did**, not
upstream provenance:

- `POINT_BROADCAST` — `cm.sample_count == 1` (a point country) against a draws grid
  (`sample_count == S`): the single country column is tiled across the `S` draws (every draw
  rescaled to the same total), bit-identical to the WET broadcast a consumer would do.
- `ALIGNED_DRAWS` — `cm.sample_count == S`: scaled draw-for-draw (the per-draw
  approximation). A caller who **pre-tiles** a point country to `S` before calling also reads
  as `ALIGNED_DRAWS` (nothing was broadcast inside this call); both-points (`cm == 1` and
  `pgm == 1`) likewise reads as `ALIGNED_DRAWS`.

The `POINT_BROADCAST` / `ALIGNED_DRAWS` / `METHOD_PROPORTIONAL` string values match
pipeline-core's `reconcile_frames` constants verbatim, so the mode vocabulary is shared
across the repos that produce and consume it.

`reconcile_proportional(grid, country)` is the **leaf kernel** (public): rescales a
`(S, n_cells)` (or point `(n_cells,)`) grid so each draw sums to its country total; preserves
zeros, clamps to non-negative. The orchestration (grouping, validation, broadcast) is built
**on top of** it; new methods are **new sibling modules**, never edits to this kernel.

---

## 4. Inputs and Assumptions

- `cm_frame` at `SpatialLevel.CM`, `pgm_frame` at `SpatialLevel.PGM` (both
  `PredictionFrame`, values `(N, S)`, `S ≥ 1`).
- `cm_frame.sample_count ∈ {1, pgm_frame.sample_count}` — a point country (`1`, broadcast)
  or aligned draws (`S`). Any other count fails loud.
- **Identical time coverage** — `cm` and `pgm` cover the same set of `time` values.
- **Country coverage** — every `(time, country)` the grid maps to has a forecast row in
  `cm_frame`.
- `map_keys` is an `(M, 2)` int array of `(time, priogrid_gid)` pairs covering every `pgm`
  row; `map_vals` is the length-`M` int `country_id` for each key. The mapping is the
  consumer's (ADR-014); the package only applies it.

---

## 5. Outputs and Side Effects

- `reconcile` → a new `pgm` `PredictionFrame`; `reconcile_result` → a frozen
  `ReconciliationResult(frame, mode, method)`. No IO, no global state, no input mutation.
- The result is **approximate** in the joint sense (§2 / C-62): conservation (sum / zeros /
  non-negativity) holds **exactly**; joint-distribution calibration does **not**.

---

## 6. Failure Modes and Loudness

All input inconsistencies **raise `ValueError`** before any scaling work
(`validation.validate_reconciliation_inputs`), per ADR-003 (fail loud):

- `cm_frame` not at `SpatialLevel.CM` → raises (message names `SpatialLevel.CM`).
- `pgm_frame` not at `SpatialLevel.PGM` → raises (message names `SpatialLevel.PGM`).
- `cm.sample_count ∉ {1, pgm.sample_count}` → raises (`"sample-count mismatch"` — names the
  allowed `1` / `S`).
- `cm` and `pgm` cover **different time steps** → raises (`"different time steps"`, listing
  the asymmetric difference).
- A grid group has **no country forecast** in `cm_frame` → raises (`"no country forecast"` /
  `"has no country forecast in cm_frame"`).
- `ReconciliationModule.__init__` with `map_keys` not `(M, 2)` or `map_vals` not length `M`
  → raises (`"map_keys must be"` / `"map_vals must be"`).
- A grid row whose `(time, priogrid_gid)` is absent from the injected mapping → raises (via
  `cross_level_align`).

**Never silent:** a level/coverage/shape inconsistency must surface as a `ValueError`, not a
mid-compute crash or a wrong-but-plausible frame. **The all-zero-country draw is an edge, not
a failure:** it stays `0` (no mass to distribute), not `NaN` and not the country total.

**The per-draw approximation is loud-by-documentation, not by exception (C-62):** an
`aligned-draws` result of independently-trained models is a documented approximation
(`proportional.py` docstring, ADR-024, this §2, and the runtime `aligned-draws` mode). It does
not raise — conservation is exact — but consumers keying on **joint** country tails (e.g. an
FAO-style worst-case) must treat the joint distribution as uncalibrated.

---

## 7. Boundaries and Interactions

- Depends **only** on `views_frames` + numpy. `views_frames` never imports this package
  (import-DAG test). It is a sibling of `views_frames_summarize`, peer to it, both depending
  *toward* the leaf (ADR-023).
- Internal SRP split: `proportional` (the scaling math / leaf kernel), `grouping` (group rows
  by `(time, country)`, call the kernel per group), `validation` (the fail-loud guards),
  `frames` (array→frame IO for the package), `result` (the mode/result value object),
  `module` (orchestration), `conformance` (the contract checks). The cm↔pgm labelling uses
  `views_frames`' `cross_level_align_arrays` — the sanctioned primitive — never an embedded
  table.
- Consumers (pipeline-core's frames-native PFE) call `ReconciliationModule.reconcile` /
  `reconcile_result` instead of re-deriving the broadcast + scaling.

---

## 8. Examples of Correct Usage

```python
from views_frames import SpatialLevel
from views_frames_reconcile import ReconciliationModule, ALIGNED_DRAWS, POINT_BROADCAST
from views_frames_reconcile.frames import prediction_frame_from_arrays

# inject the (time, priogrid_gid) -> country_id mapping
module = ReconciliationModule(map_keys, map_vals)   # map_keys (M,2), map_vals (M,)

# aligned draws: cm carries the grid's S draws -> scaled draw-for-draw
out = module.reconcile(cm_frame, pgm_frame)         # new pgm PredictionFrame, (N, S)

# also report the mode (audit-friendly)
res = module.reconcile_result(cm_frame, pgm_frame)
res.frame                                           # the reconciled frame
res.mode                                            # ALIGNED_DRAWS or POINT_BROADCAST
res.method                                          # "proportional"

# point country (sample_count == 1) vs a draws grid -> broadcast inside reconcile
point_cm = prediction_frame_from_arrays(t, u, country_point, level=SpatialLevel.CM)  # (N, 1)
res2 = module.reconcile_result(point_cm, pgm_frame)
assert res2.mode == POINT_BROADCAST
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: passing the grid frame where the country frame is expected -> ValueError
module.reconcile(pgm_frame, pgm_frame)              # cm must be at SpatialLevel.CM

# WRONG: a country with neither 1 nor S draws -> ValueError ("sample-count mismatch")
module.reconcile(cm_half_samples, pgm_frame)        # cm.sample_count must be 1 or S

# WRONG: embedding / fetching the geography. The mapping is injected, always:
ReconciliationModule().reconcile(cm, pgm)           # TypeError — map_keys/map_vals required

# WRONG: treating an aligned-draws result as a calibrated JOINT country distribution.
# Conservation holds exactly, but per-draw pairing of independently-trained models is an
# approximation (C-62 / ADR-024) — read res.mode and treat joint tails as uncalibrated.
res = module.reconcile_result(cm, pgm)              # res.mode == ALIGNED_DRAWS is a caveat

# WRONG: mutating the returned frame's value buffer in place (the leaf value buffer is
# immutable-by-convention; see ADR-025 / PredictionFrame CIC §9) -> may corrupt shares
out.values[:] = 0                                   # unsupported

# WRONG: stamping the mode onto the leaf frame's metadata. It is reported on the result.
out.with_metadata(mode="point-broadcast")           # the leaf carries no reconcile vocabulary
```

---

## 10. Test Alignment

The package is **heavily tested** (100% line+branch coverage, a frozen torch-oracle parity
gate); these are the contract-bearing suites:

- **Green (it reproduces the truth):** `tests/test_reconciliation_e2e_parity.py` —
  `ReconciliationModule.reconcile` reproduces the frozen views-reporting oracle on the S0
  fixture at `0.000e+00` drift (`TestEndToEndParity`); the sum-to-country law on active draws
  (`test_sum_constraint_on_active_draws`); de-mutation (`test_de_mutated`); native
  point-broadcast ≡ manual tile (`test_point_country_broadcast_equals_manual_tile`).
- **Beige (edges):** `tests/test_reconcile_conformance.py` — `assert_reconcile_contract`
  across the oracle fixture, synthetic probabilistic frames (`S ∈ {1, 16, 100}`), the
  all-zero-country edge, and the point-country (`cm_samples=1`) case; the injected-mapping
  proof (a permuted mapping changes the result). Mode reporting at the corners (point grid,
  both-points, pre-tiled cm) — `TestReconciliationResult`.
- **Red (it fails loud):** `tests/test_reconciliation_validation.py` —
  `validate_reconciliation_inputs` raises on wrong cm level, wrong grid level, sample-count
  mismatch, time mismatch, and a missing country forecast; the `(M, 2)` map-keys guard
  (`test_bad_mapping_shape_raises`). The conformance-suite **negative** (a deliberately
  non-conforming impl/input makes `assert_reconcile_contract` raise) and the
  `ReconciliationResult` frozen-ness assertion are the red gaps being closed alongside this
  contract (register C-65 batch, epic #179 / S3).

Each §3 guarantee maps to a green/beige test; each §6 failure mode maps to a red test in
`test_reconciliation_validation.py`.

---

## 11. Evolution Notes

- **Additive only** (ADR-023 charter; ADR-018 freeze posture): new reconciliation methods are
  **new sibling modules**, never edits to `proportional`/`grouping`. The v1.8.0 point-broadcast
  + mode surface was added without touching the parity-frozen equal-count path (byte-exact).
- **The principled joint upgrade is designed and deferred (ADR-024 / C-62):** pairing
  grid-draw `s` with country-draw `s` needs a shared draw-identity / coupling contract and a
  consumer that needs calibrated joint tails. Until those preconditions hold, the per-draw
  proportional method stays the shipped method, and `aligned-draws` results carry the caveat.
  The upgrade, when built, gets its **own** module + its own §3/§6 additions to this contract.

---

## End of Contract

This document defines the **intended meaning** of `views_frames_reconcile`.
Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
