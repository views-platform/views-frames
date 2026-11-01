
# Class Intent Contract: views_frames_reconcile

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-10-31
**Related ADRs:** ADR-002, ADR-003, ADR-006, ADR-008, ADR-014, ADR-020, ADR-023, ADR-024, ADR-030

> The `views_frames_reconcile` package — forecast reconciliation as a `views_frames`
> sibling (numpy + `views_frames` only). Implemented in **v1.7.0** (Epic 11, ADR-023): a
> faithful numpy port of views-reporting's top-down proportional reconciler. Extended
> **additively in v1.8.0** (epic #142) with a native **point-country broadcast** and a
> self-describing **reconciliation mode** (`reconcile_result` → `ReconciliationResult`;
> ADR-024 designs the deferred principled upgrade). `CONFORMANCE_FLOOR` stayed `1.0.0`.
> **Changed in 3.0.0 (ADR-030, a MAJOR):** a draw whose grid is all zeros while the country
> is positive is filled from a donor draw of the same `(time, country)` instead of staying
> zero (which lost 2.9–7.3% of the fatality mass on the first production run, #283), and a
> group with no donor raises. `CONFORMANCE_FLOOR` moved to `3.0.0`.
>
> This is a **package-level** contract (the package is functions + two small classes, not
> one class). It governs the public surface re-exported from
> `src/views_frames_reconcile/__init__.py`: `ReconciliationModule`, `ReconciliationResult`,
> `reconcile_proportional`, and the `POINT_BROADCAST` / `ALIGNED_DRAWS` /
> `METHOD_DONOR_FILL` / `METHOD_PROPORTIONAL` mode/method constants — plus the package's own array→frame builder
> `prediction_frame_from_arrays` (`frames.py`) and the `assert_reconcile_contract`
> conformance check (`conformance.py`).

---

## 1. Purpose

Reconcile **PRIO-GRID-month (`pgm`) forecasts to their country-month (`cm`) totals**: make
each country's grid cells sum, **in every posterior draw**, to that country's forecast, by
**top-down proportional disaggregation** (FPP3 forecast-proportions). The country forecast
is the authority (ADR-030; a stated premise, register C-100): where a draw's grid is empty,
the pattern is borrowed from a donor draw so the country's mass is still placed. It is the
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

`ReconciliationModule(map_keys, map_vals, *, seed=0)` holds the injected mapping and the
donor seed, and applies them:

- `reconcile(cm_frame, pgm_frame)` → a **new** `pgm` `PredictionFrame`: validates the
  inputs, fills empty-grid draws from donors (below), then scales each country's grid cells
  to the country total. Returns only the frame.
- `reconcile_result(cm_frame, pgm_frame)` → a
  `ReconciliationResult(frame, mode, method, filled_draws)`: the same reconciled frame
  **plus** the mode it was produced by (`POINT_BROADCAST` | `ALIGNED_DRAWS`), the method
  (`METHOD_DONOR_FILL`) and how many draws were filled. `reconcile` is exactly
  `reconcile_result(...).frame`.

**Donor fill (ADR-030, `donor_fill.py`).** Within each `(time, country)` group, a draw
whose country value is positive and whose grid has no cell `> 0` **needs filling**. It
receives the grid values of a **donor** — a draw of the same group with grid mass, chosen
uniformly at random from `numpy.random.default_rng([seed, time, country])` — and is then
scaled like any other draw. The result is reproducible for a given `seed` and does not
depend on how the caller chunks its calls (one month at a time or all at once) or on
group order. Draws that do not need filling are bit-identical to the 2.x output.

Guarantees on the reconciled frame (per the conformance laws,
`conformance.assert_reconcile_contract`):

- **Sum-to-country in every draw** — for each `(time, country)` group, the cells' sum in
  every draw equals that country's forecast for that draw, to `rtol=1e-4, atol=1e-3`. No
  draw is exempt: a country of 0 empties the grid; a positive country is placed in full,
  or the call raises (§6).
- **Zero-preservation** — in a draw that had grid mass, an input zero cell stays exactly
  zero. A **filled** draw is a scaled copy of one donor draw of its group: the donor's zero
  cells, the donor's shares.
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
  `ReconciliationResult(frame, mode, method, filled_draws)`. No IO, no global state, no
  input mutation; the only randomness is the donor choice, seeded explicitly.
- **Memory:** when any draw is filled, one extra copy of the grid's values buffer is made
  before scaling (ADR-030; cf. C-71). A call with nothing to fill makes no copy.
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
- A **negative country total** → raises (`"country totals must be non-negative"`) — it cannot
  be conserved under the non-negativity clamp, so silently clamping to zero would break the
  sum-to-country guarantee (falsify audit 2026-07, F8).
- A draw that **needs filling in a group with no donor** — the country is positive but the
  grid has no cell `> 0` in **any** draw of that `(time, country)` — raises
  (`"time T, country C: cannot place the country value of K of S draw(s) … no donor
  pattern"`) before any output is returned (ADR-030). A single-draw grid (`S = 1`) whose
  only draw is empty against a positive country is this case. It means the grid and
  country forecasts disagree about that country-month; the package refuses to invent a
  pattern.
- `ReconciliationModule.__init__` with a `seed` that is not a non-negative int → raises
  (`"seed must be a non-negative int"`).

**Never silent:** a level/coverage/shape inconsistency must surface as a `ValueError`, not a
mid-compute crash or a wrong-but-plausible frame. **An empty grid against a positive country
is filled or refused, never dropped.** Until 3.0.0 this contract called it "an edge, not a
failure" and let it stay `0`, which silently lost the country's mass (#283, register C-99).
**Sum-to-country holds exactly for any nonzero draw sum** — the port's `+ 1e-8` denominator
epsilon, which silently deflated the scale factor for tiny nonzero sums, was replaced by an
explicit all-zero guard (falsify audit 2026-07, F1; bit-identical on all realistic data).

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
  by `(time, country)`, call the kernel per group), `donor_fill` (give empty-grid draws a
  donor pattern before scaling; groups rows the same way `grouping` does, deliberately
  duplicated — ADR-030), `validation` (the fail-loud guards),
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

# inject the (time, priogrid_gid) -> country_id mapping (and, optionally, the donor seed)
module = ReconciliationModule(map_keys, map_vals, seed=0)   # map_keys (M,2), map_vals (M,)

# aligned draws: cm carries the grid's S draws -> scaled draw-for-draw
out = module.reconcile(cm_frame, pgm_frame)         # new pgm PredictionFrame, (N, S)

# also report the mode (audit-friendly)
res = module.reconcile_result(cm_frame, pgm_frame)
res.frame                                           # the reconciled frame
res.mode                                            # ALIGNED_DRAWS or POINT_BROADCAST
res.method                                          # "proportional-donor-fill"
res.filled_draws                                    # draws whose empty grid got a donor pattern

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

# WRONG: expecting an empty grid to stay empty against a positive country. Since 3.0.0
# the draw is filled from a donor (ADR-030); if no draw of the group has grid mass, the
# call raises instead of returning a grid short of the country.
module.reconcile(cm_positive, pgm_all_zero)         # ValueError: ... no donor pattern

# WRONG: stamping the mode onto the leaf frame's metadata. It is reported on the result.
out.with_metadata(mode="point-broadcast")           # the leaf carries no reconcile vocabulary
```

---

## 10. Test Alignment

The package is **heavily tested** (100% line+branch coverage, a frozen torch-oracle parity
gate); these are the contract-bearing suites:

- **Green (it reproduces the truth):** `tests/test_reconciliation_e2e_parity.py` —
  `ReconciliationModule.reconcile` reproduces the frozen views-reporting oracle on the S0
  fixture **outside the draws ADR-030 fills** (`TestEndToEndParity`;
  `test_oracle_lost_the_mass_the_module_places` pins why those differ); the sum-to-country
  law on every draw (`test_sum_constraint_on_every_draw`); de-mutation (`test_de_mutated`);
  native point-broadcast ≡ manual tile
  (`test_point_country_broadcast_equals_manual_tile`).
- **Green (mass is placed, ADR-030):** `tests/test_reconcile_mass_placement.py` — on
  realistic sparse inputs (`tests/sparse_reconcile_case.py`, 94–99% zeros): total placed mass
  equals total country mass; every draw sums to its country; a filled draw is a scaled copy
  of a donor of its group. These three failed on 2.x (#285).
  `tests/test_reconcile_donor_fill.py` — the kernel; reproducibility for a seed; month by
  month ≡ all months at once; draws not filled are bit-identical to 2.x; `filled_draws` is
  the number filled; the `seed` guard.
- **Beige (edges):** `tests/test_reconcile_conformance.py` — `assert_reconcile_contract`
  across the oracle fixture, synthetic probabilistic frames (`S ∈ {1, 16, 100}`), the
  no-donor raise (`test_contract_with_all_zero_country_raises`), and the point-country
  (`cm_samples=1`) case; the injected-mapping
  proof (a permuted mapping changes the result). Mode reporting at the corners (point grid,
  both-points, pre-tiled cm) — `TestReconciliationResult`.
- **Red (it fails loud):** `tests/test_reconciliation_validation.py` —
  `validate_reconciliation_inputs` raises on wrong cm level, wrong grid level, sample-count
  mismatch, time mismatch, a missing country forecast, and a missing
  `(time, priogrid_gid)` mapping entry (`test_missing_mapping_entry_raises`); the `(M, 2)`
  map-keys guard (`test_bad_mapping_shape_raises`). The no-donor raise in all its forms
  (multi-draw group, single-draw grid, point country) — `TestNoDonor` in
  `tests/test_reconcile_donor_fill.py`. **One negative per conformance law**
  (`TestEachLawHasTeeth` in `test_reconcile_conformance.py`: the 2.x reconciler, a 1% miss,
  mass moved into a zero cell, a smeared fill, mass invented where no draw had any — each
  must make `assert_reconcile_contract` raise; before 3.0.0 the sum law had no negative and
  could be deleted with the suite green, #285). The original conformance-suite **negative**
  (a deliberately non-conforming impl makes `assert_reconcile_contract` raise) and the
  `ReconciliationResult` frozen-ness assertion live in `test_reconcile_conformance.py` /
  `test_reconciliation_e2e_parity.py` (the C-65 batch, epic #179 / S3). The
  share-proportionality **law** (`test_shares_are_preserved_within_each_draw`) and the
  2026-07 audit regressions — exact conservation for tiny nonzero sums, the negative-total
  raise — are pinned in `test_reconciliation_parity.py` and
  `test_falsification_safety_audit_2026_07.py` (register C-68/C-70).

Each §3 guarantee maps to a green/beige test; each §6 failure mode maps to a red test
(the validation guards in `test_reconciliation_validation.py`; the negative-total and
tiny-sum modes in the audit-regression file above).

---

## 11. Evolution Notes

- **Additive only** (ADR-023 charter; ADR-018 freeze posture): new reconciliation methods are
  **new sibling modules**, never edits to `proportional`/`grouping`. The v1.8.0 point-broadcast
  + mode surface was added without touching the parity-frozen equal-count path (byte-exact).
- **3.0.0 donor fill (ADR-030, a MAJOR):** the rule held — `donor_fill.py` is a new pass
  before the untouched kernel and grouping. The *contract* changed, not the kernel: the sum
  law lost its all-zero exemption, zero-preservation became per draw, and a no-donor group
  raises. Parked, on evidence: borrowing from neighbouring months (never needed on the first
  production run) and k-nearest donors (needs pre-reconciliation grid totals to test).
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
