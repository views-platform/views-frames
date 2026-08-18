# Changelog

All notable changes to `views-frames` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/) as governed in `GOVERNANCE.md`.

## [2.0.0] — 2026-08-18

**A frame's index must actually be an index.** Until now you could hand a frame anything as
its `index` — a different frame, or a bare object with an `n_rows` attribute — and it was
accepted. The frame was built, it looked fine, and the published conformance suite said it
was fine. That now raises `TypeError`.

**If you pass a `SpatioTemporalIndex`, you will not notice this release.** That is what the
type hint has always said and what every example does. Change your version constraint,
re-lock, and carry on:

```diff
- views-frames = ">=1.10.2,<2"
+ views-frames = ">=2.0.0,<3"
```

This is the package's **first MAJOR** and the first move of `CONFORMANCE_FLOOR` since the
v1.0.0 freeze (`1.0.0` → `2.0.0`). The decision, the full migration table and the reasoning
are in **ADR-028**.

### What actually breaks

| If your code… | Before | Now |
|---|---|---|
| passes a `SpatioTemporalIndex` as `index` | works | **works, unchanged** |
| passes a frame or other object as `index` | silently constructed | `TypeError` |
| passes a non-index to `reindex`/`reindex_fill` | `AttributeError` on `_level` | `TypeError`, naming what was expected |
| mutates `frame.values` in place | silently corrupted buffer-sharing frames | `ValueError: assignment destination is read-only` |
| calls `map_estimate` on `inf`/`NaN` draws | bare `IndexError` | `ValueError` naming the cause |

Only the fourth row can plausibly stop working code, and ADR-025 already documented that
operation as unsupported.

**No `from_legacy_*` shim.** GOVERNANCE's MAJOR process asks for one where a consumer format
changes. Nothing here changes a wire format, a serialized layout or a signature — only the
set of inputs that were never valid narrows, so a shim would have nothing to translate.

### Fixed

- **The three frame constructors never type-checked `index`** (register C-93, Tier 2). They
  validated `y_pred` four times — coerced it, checked dtype, ndim, row count — and read
  exactly one attribute off `index`: `n_rows`. A frame has one. So
  `PredictionFrame(values, another_frame)` constructed silently, as did any object exposing
  `n_rows`.

  The half that made it Tier 2: every summarizer reads `.values` and `.n_rows` and none
  reads `.index`, so a malformed frame returned **numerically correct** answers from
  `collapse`, `map_estimate` and `hdi` — and **`assert_summarizer_contract` certified it**.
  That checker is published under ADR-016 and consumers run it in their own CI, and
  `docs/CICs/Conformance.md` names "a checker that cannot detect a violation" as the failure
  mode it must never have. A false pass is worse than no checker, because it is evidence a
  consumer is entitled to rely on.

  The checker keeps its own assertion even though construction now makes it unreachable by
  ordinary means: consumers run the suite against their own frame factories, and
  `with_metadata` already builds frames through `__new__` rather than `__init__`.

  Found by a falsification audit run against the claim that this package was finished.

- **Same-level alignment leaked a private attribute** (register C-94).
  `reindex`, `reindex_fill`, `is_superset_of` and `intersect` raised
  `AttributeError: '...' object has no attribute '_level'` — naming a private attribute of a
  class the caller never mentioned — where ADR-008 requires `ValueError`/`TypeError`. All
  four route through one private helper, so one guard fixes the family.

- **`map_estimate` crashed obscurely on non-finite draws** (register C-57). An `inf` draw
  produced a `nan` bin index whose `astype(intp)` cast overflowed to the int-min sentinel,
  giving `IndexError: index -9223372036854775808 is out of bounds`. It now raises
  `ValueError` naming the cause, like `exceedance` and `expected_shortfall` have since
  v1.5.0 and v1.6.0.

### Changed

- **`frame.values` is write-protected** (register C-66) — the enforce ADR-025 deferred,
  riding this MAJOR exactly as planned.

  It did not ship as the one-liner ADR-025 recorded. `self._values.setflags(write=False)`
  would have been a defect: `coerce_values` returns the caller's *own* array when it is
  already `float32` — the zero-copy guarantee — so it silently makes **the caller's** array
  read-only too. Measured, not reasoned about: the naive form does flip
  `caller.flags.writeable` to `False`. The frames take a read-only **view** instead, which
  locks the frame's buffer, leaves your array alone, and still shares memory. A `np.memmap`
  keeps its subclass and its zero-copy.

- **`CONFORMANCE_FLOOR` `1.0.0` → `2.0.0`.** The first move since the freeze, because
  `assert_summarizer_contract` now rejects a frame that misreports its own index. Every
  consumer's CI will assert a new contract version — that is what the constant is for, but
  it has never happened before.

### Changed — governance

- **ADR-028** records the decision, the migration and the alternatives — including the three
  that were rejected and why (deferring it as C-66 was deferred; fixing only the checker;
  using a `Protocol` check, which fails because `SpatioTemporalIndexed` describes a *frame*
  and `SpatioTemporalIndex` does not even satisfy it).
- **ADR-018 amended** — the freeze it declares has now been broken once, deliberately.
- **ADR-025 amended** — its "by convention" title is history, and the one-line fix it
  recorded would have been wrong.
- **C-43 declined as a rider, in writing.** C-13's pre-tag checklist names it, so passing it
  over silently would have been the failure this register has recorded three times. The two
  binning functions are not two implementations of one concept: one is a deliberately
  approximate clipped-linear bucket for a heuristic flag, the other reproduces
  `numpy.histogram`'s edge-exact path bit-for-bit and is ulp-sensitive across numpy
  versions. Its precondition is rewritten to `#89` alone, because "#89 or a MAJOR" became
  false the moment this released.
- **New: register C-95** — `SpatioTemporalIndex` still write-protects the caller's
  identifier arrays in place, the hazard C-66 had to avoid for the frames. Left alone
  deliberately: that is ADR-025's own reasoning applied consistently rather than an
  exception made because a MAJOR was already open.

- **The status banners no longer claim a publication they cannot verify** (register C-97).
  `README.md` and `CLAUDE.md` said "published to PyPI" / "released" from the moment the
  version was bumped — true within minutes on every previous release, and false for as long
  as a MAJOR's cross-repo gate takes. They now state the version *in this tree* and link to
  PyPI for what is published. `validate_docs.sh` check 6 still pins the banner to
  `pyproject.toml`, which is the part a repository can actually check.

- **`validate_docs.sh` check 10: the documents that describe the wheel are held against
  `[tool.hatch.build.targets.wheel]`** (register C-96). Two of them still said the wheel
  ships two packages; it has shipped three since v1.7.0, and one of the two was a comment in
  the workflow that publishes. Two halves — completeness and a literal count word — because
  neither catches the other's case, scoped to documents describing the current wheel so that
  ADRs and postmortems stating counts that were true when written are not flagged.

- **The publishing runbook gained a pre-tag checklist.** Register C-13's requirement that
  every pinned consumer has an adoption issue before a MAJOR is tagged lived only in the risk
  register, which is not the document anyone stands in front of at release time. This release
  reached "ready to tag" with none filed.

## [1.11.0] — 2026-08-18

**The published MAP-containment law was wrong on tied draws, and the governance documents
had drifted from the code in ways nothing checked.** This release fixes the first, corrects the second, and
adds the CI checks that keep both from drifting again. `CONFORMANCE_FLOOR` stays `1.0.0`,
and no public API was added, changed or removed.

MINOR rather than PATCH because the conformance suite now asserts a different set of HDI
floors than it did in 1.10.2. Nothing a consumer wrote needs to change, and a consumer that
passed 1.10.2 still passes.

### Fixed

- **`assert_summarizer_contract` failed on integer count posteriors** (register C-88,
  #257). The MAP-containment law decided which HDI floors provably contain the tower tip
  using `floor(m·S)+1` — a floor's *index span*, which `_ks` builds it from. The tip is the
  median of the draws whose *value* lies inside the floor. Those two agree only when draws
  are distinct: duplicated endpoint values put more draws inside the same bounds, so the tip
  floor held more than the formula allowed, and narrower floors were certified that hold
  less than half of it. The law then asserted containment for them.

  Measured on zero-inflated Poisson posteriors at `S ∈ {32, 64, 128}`: **30 of 500 rows
  failed**, every one on the `0.15` floor — exactly the narrowest floor the old arithmetic
  certified at `S = 64`. After the fix, **0 of 500**.

  This is published under ADR-016 and consumers run it in *their* CI, so the failure landed
  as another repository going red on correct data — and integer counts are this platform's
  primary shape, since they are conflict fatality counts. No test here used integer or tied
  draws, which is why it survived: the estimator tests build posteriors from continuous
  distributions, where endpoint ties are measure-zero.

  The fix counts rather than computes. Both the tip floor's occupancy and each candidate
  floor's now come from `_in_range_span` — the same quantity `tower_point` takes the median
  of. Occupancy depends on the row once ties exist, so a floor may qualify in one row and
  not another, and the law asserts containment only where it qualifies. Nesting across the
  candidate grid is asserted *unconditionally*, because qualification is derived from the
  tower under test and a broken tower would otherwise disarm the law with its own defect.
  Counted in the same row blocks `hdi_tower` uses, so the published suite stays inside the
  memory discipline of the code it certifies (C-22/C-25/C-71): 143 MB peak on a 200k×32
  frame, against 149 MB before.

  `CONFORMANCE_FLOOR` stays `1.0.0`: the correction *narrows* what the suite asserts, so
  consumers who passed still pass and consumers who failed now pass.

- **The two IO codecs disagreed on a non-JSON metadata value** (register C-90). `io/npz`
  passed `json.dumps(..., default=str)` and `io/arrow` did not, so a `datetime` timestamp
  was silently stringified by one codec and rejected by the other — reloaded as
  `'2026-01-01 00:00:00'` where the field is declared `int | None`. The storage backend
  decided whether the run failed. Both now raise, per ADR-008.

### Added — checks

- **Import contracts run in CI** (#238). `pyproject.toml` gained two `import-linter`
  `layers` contracts and CI gained an `imports` job. The first records that the core does
  not depend on its two sibling packages and that the siblings do not depend on each other;
  the second records the module layering inside `views_frames`. Both describe the structure
  the code already has — nothing was restructured.

  The first duplicates `tests/test_import_enforcement.py`, which remains the stricter of the
  two (it also bans foreign `views_*` packages, pandas and friends, and `pyarrow` outside
  `io/`). The duplication is deliberate: the same contract is landing across the platform's
  cycle-free repos, so it is written the same way here.

- **`docs/validate_docs.sh` now asserts three completeness claims** that four governance
  documents had been making without evidence (register C-85, C-89):

  - every publicly exported name is named in some CIC (38 names, read from the `__all__`
    blocks);
  - every public class has a CIC or a recorded exemption (13 classes);
  - `GOVERNANCE.md` names every published conformance entry point (8 names).

  Each would have caught one of C-64, C-81 and C-85 mechanically. Names are matched on
  **word boundaries, not substrings** — `Frame` has 84 substring hits across the CICs and 9
  real ones, so a substring match would let any `*Frame` satisfy the bare `Frame` protocol
  and let `hdi_tower` satisfy `hdi`.

  The same change fixed a check that could silently switch itself off: the README-banner
  comparison was guarded by `if [ -f ... ]` with no `else`, so moving either input disabled
  it while CI stayed green (C-89).

- **`examples/` runs in CI** (register C-83, #247). README's quickstart tells readers to run
  `examples/quickstart.py` and `examples/cross_level.py`, and no workflow executed either,
  while `notebooks/` has had a drift check since #151. The job loops over `examples/[!_]*.py`
  so a third script tomorrow is covered, keeps going after a failure so one broken script
  cannot hide another, fails when the glob matches nothing rather than passing vacuously,
  carries `timeout-minutes: 5`, and is pinned to the 3.10 floor — the on-ramp is promised to
  the reader most likely to pin conservatively.

- **A cross-version IO fixture test** (register C-79). Every arrow IO test wrote a file and
  read it back in the same process at the same version, which proves the codec is
  self-consistent and nothing about the property that matters for a data contract: that a
  file written by an earlier release still loads. Consumers on that path hold archived
  shards (views-postprocessing, views-faoapi #100).

  `scripts/gen_arrow_crossversion_fixture.py` extracts `io/arrow.py` and `io/npz.py` from
  the `v1.8.0` tag and writes the fixtures with *that* `save`. `v1.8.0` predates v1.10.1,
  which added three `ValueError` paths rejecting row orders that violate the wire contract
  (C-72) — so these fixtures are the evidence those rules accept a file written before they
  existed.

- **The architecture-tree check runs in CI**, as a step of the `docs` job. It was added in
  this cycle to stop the standard's directory tree going stale again and then ran nowhere,
  which is the same failure C-74 records. It is stdlib-only, so the `docs` job still
  installs no Python toolchain.

- **`__all__` on both sibling conformance modules** (register C-87), so all three published
  surfaces are read the same way.

### Changed — architecture record

- **ADR-002 amended: `io/` is a codec the frames call, not a layer above them** (register
  C-82). The decision never changed — dependency direction is still one-way and acyclic —
  but the ADR's claim about *which way* `io/` runs was wrong, and had been since C-09's
  resolution in v0.1.0 moved `io/` onto a generic frame-state contract. `Persistable` puts
  `save`/`load` on the frame, and those are frozen v1 surface, so the documents moved rather
  than the code. Corrected alongside it:
  `docs/standards/physical_architecture_standard.md`, `docs/ADRs/README.md`, `README.md`
  §layout rules, and `docs/CICs/Protocols.md`, which now records that `Persistable` is *why*
  the dependency runs the way it does.

- **The physical-architecture standard's directory tree matches the repository** (register
  C-84). Its §2 tree was a pre-implementation sketch that had never been revised: it showed
  one of the three shipped packages, omitted `metadata.py`, `_typing.py` and the whole
  `conformance/` subpackage, listed two files that were never written, and still marked
  `target_frame.py` as "anticipated" — it shipped in v1.0.0.

- **README's tree and its conformance path** (register C-86). The tree omitted 11 of 36
  modules — the summarize package was shown as four where it has fourteen — and named two
  `tests/` directories that do not exist. §9 introduced the published suite as
  `tests/conformance/`, **a path that has never existed**; it is
  `src/views_frames/conformance/`, which GOVERNANCE, ADR-016 and every CIC name. README is
  the PyPI long-description, and that sentence sits in the section written to close the
  cross-repo contract-test gap (C-30).

- **`GOVERNANCE.md` names all seven published conformance exports** (register C-85 part 1).
  It told consumers the suite was three functions. The two it omitted from
  `views_frames.conformance` are not incidental — `assert_frame_envelope` is the shipped
  mitigation for the still-open Tier-2 C-46, and `assert_reindex_fill_law` pins ADR-026 —
  and it omitted `views_frames_reconcile.conformance` entirely. A consumer following it
  literally ran three of seven. It is now written to be checked rather than trusted: a table
  per module, an explicit statement that **each module's `__all__` is the source of truth,
  not the table**, and the command to read it.

- **ADR-018 records eight names it froze but never listed** (register C-85 parts 2–3). An
  audit of the whole public surface against the ADR — 65 names — found eight omissions. The
  largest is a package: `views_frames_reconcile` shipped in v1.7.0 and ADR-018 does not
  mention it, though the "Additive since v1.0.0" section records the estimator families in
  careful detail. The rest are `feature_names`, `n_features`, `from_2d`, `n_rows`,
  `SpatialLevel`, `FrameMetadata`, `assert_frame_envelope`, and the ADR-026 dense-grid
  family.

- **New contract document: `docs/CICs/FrameMetadata.md`** (register C-85 part 4). It was
  exported from `views_frames`, listed in ADR-018's frozen surface, and its name appeared in
  exactly one CIC — a sibling package's. The parts worth having in writing are what the
  unknown-key drop *costs* (a header written by a newer version and read by an older one
  silently loses fields, and re-saving persists the loss — which is why adding a field is
  MINOR rather than free), what the class deliberately does not validate, and why `io/`
  never sees it.

### Changed — tests

- **`tests/test_packaging.py` collected zero tests on the 3.10 leg** (register C-80).
  `importorskip("tomllib")` sat at module level and `tomllib` is 3.11+, so the classifier
  assertions never ran on the leg the `floor` job exists to scrutinise. Now a `tomli`
  fallback, with the dependency declared for `python_version < '3.11'`.
- **Three `FrameMetadata` guarantees that its contract states and nothing pinned** now have
  tests: the unknown-key drop (the nearest test only asserted `from_dict` does not raise),
  the empty-header default, and the save/load round-trip for `FeatureFrame` and
  `TargetFrame` — pinned for `PredictionFrame` only.
- `tests/test_reconcile_head_to_head.py` collects zero tests anywhere and is kept: it is a
  real local cross-check against the *live* old package, which a fixture cannot be. Its
  docstring now names what holds the guarantee in CI instead.

### Changed — governance

- **`docs/contributor_protocols/carbon_based_agents.md` gained a section on claims about
  your own work** (register C-77): demonstrate rather than describe; use a check that could
  actually have failed; leave it where the next person can run it; and remember that the
  mutations an author picks are the ones they already had in mind. The fourth part earned
  its place twice more after being written — a tree check that passed its author's own
  mutations and still could not see a duplicated basename, and the C-88 fix that was tested
  for firing falsely but not for failing to fire.

- **CI checks are not gates here** (register C-92). Neither `main` nor `development` has
  branch protection and there are no rulesets, so all eleven checks run on every pull
  request and none is required. Several documents described checks as "blocking" or as
  "what makes it a gate"; they make it a signal. The wording is corrected and the entry
  stays open until branch protection is configured.

- **`docs/guides/publishing-to-pypi.md` describes the repository as it is.** The runbook
  is written to be followed "solo, cold, months later", and it still said the pipeline was
  *"not yet exercised by a real release"* after thirteen of them, described a wheel of two
  packages where it ships three, and told the reader to configure a *pending* trusted
  publisher for a project that has existed since `v1.0.0`. The wheel-contents check in the
  TestPyPI rehearsal expected two `py.typed` files and would have passed while missing a
  package.

- **`CLAUDE.md` gained a `## Maintenance mode` section.** This package is frozen and
  released, and the register's open entries are a log of accepted conditions, not a backlog.
  The section says so, and says which discovery tooling should not be run here.

## [1.10.2] — 2026-07-31

**No behaviour change.** This release publishes work on the checks, the tests and the
documentation. The only change under `src/` is a corrected docstring. `CONFORMANCE_FLOOR`
stays `1.0.0`, and no public API was added, changed or removed.

If you are upgrading from 1.10.1, nothing in your code needs to change.

### Fixed

- `FeatureFrame.from_2d` was documented as a *"deprecated shim"*. It is not deprecated —
  it builds a frame from a 2-D `(N, F)` array of unsampled features and adds the trailing
  sample axis to give `(N, F, 1)`. Since the sample axis is always explicit (ADR-012),
  that is the ordinary constructor for deterministic features. The method docstring, the
  module docstring, the constructor's `ValueError` message and the contract file were all
  corrected — the first pass missed the last two, so the same file contradicted itself for
  a while (register C-76).

### Changed — checks

- **`docs/validate_docs.sh` now runs in CI.** It checks documentation consistency,
  including that the README's version banner matches `pyproject.toml`. That banner check
  had been added specifically to stop version drift recurring, but the script was never
  wired into CI — it only ran when someone typed it (register C-74, half closed here; the
  formatting half follows).

### Changed — tests

- **Eleven falsification tests now check the code instead of the README's wording.** They
  were written before the package existed, when asserting that the design document had
  *decided* something was the only check available. They had reached the point of failing
  when someone reworded a paragraph and passing when the code broke. Ten were rewritten
  against behaviour; one was retired because `test_import_enforcement.py` already enforces
  it directly (register C-75).
- Among them, the check that no legacy `priogrid_gid` alias exists now inspects the code
  rather than the documentation — a guard against something that was actually attempted.

### Changed — documentation

- **New contract document: `docs/CICs/Conformance.md`.** The published conformance suite —
  the checks consumers run in their own CI — had no contract describing what it guarantees,
  while the contract index claimed every shipped surface was covered. It now documents each
  check, what it deliberately does *not* verify, and the failure mode that matters most: a
  checker must **fail** when handed a frame that misreports itself (register C-81).

- **ADR-027** records the decision to decline issue #113, which asked for a one-line
  shortcut for building a `PredictionFrame`. Construction stays two-step. The design that
  had been agreed for it is preserved in the ADR, along with what would justify revisiting
  it (register C-52, C-53, C-54).
- The reconciliation production-slice check is closed: the comparison tool and the runbook
  requirement for it both shipped some time ago (register C-58).
- Documentation now cites code **by name** rather than by line number
  (`_validation.py::coerce_values`, not `_validation.py:64`). Line numbers had already
  drifted unnoticed in two entries.

## [1.10.1] — 2026-07-28

**`io.arrow.load` now validates the wire-contract row order before reshaping (#199 item 1).**
Fail-loud hardening of the parquet load path; no API change; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Fixed
- **Silent sample-slot corruption on out-of-order parquet input.** `arrow.save` writes the
  row order as the contract (`sample = tile(arange(S), N)`; `io/arrow.py`) but `load`
  reconstructed positionally without ever checking it — a reordered, truncated, or
  foreign-rewritten table reshaped **plausible floats into the wrong sample slots with no
  error**. `load` now validates the layout first and raises `ValueError` on: a row count
  that is not a positive multiple of the header's `n_samples` (truncated/filtered table);
  a `sample` column deviating from the written tile order (row-level reorder); or
  `time`/`unit` not constant within a sample block (rows swapped between cells — the case
  the tile check alone cannot see). A whole-cell block reorder (identifiers travel with
  their draws) remains a *consistent* table and still loads. Implements the check
  views-postprocessing ADR-013 §4.5(b) previously required every consumer to run
  themselves on a separate raw-table read — the leaf now hardens all consumers at once.
  Register C-72. (#199 item 2 — mmap/partitioned arrow reading — remains open.)

## [1.10.0] — 2026-07-27

**The dense-grid fill primitive (ADR-026) — unblocks pandas-free FAO ingestion (#203).**
Additive MINOR; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`frame.reindex_fill(other, *, fill_value)`** on all three sibling frames
  (`PredictionFrame`/`FeatureFrame`/`TargetFrame`, WET per ADR-011): align to `other`'s
  rows with **no** superset requirement — present rows pass through **bit-exact**, absent
  rows get the caller's `fill_value` broadcast across the trailing axes (`NaN` legal;
  keyword-only and required — no silent default, ADR-009). The result's index **is**
  `other`; metadata (and `feature_names`) preserved. Owns the `-1`-sentinel scatter once:
  a consumer hand-rolling `values[pos]` silently picks the *last* row for absent cells.
  Inherits the C-21 row-uniqueness stance (unique rows assumed in *self*; duplicate
  target rows allowed and repeat).
- **`SpatioTemporalIndex.cartesian(times, units, level)`**: the dense product-index
  constructor — every `(time, unit)` combination in canonical **time-major** order, from
  **explicit arrays only** (deriving them, e.g. "units of the last time step", is
  consumer policy). Fails loud on duplicated input values (a duplicated product input
  manufactures duplicate rows → undefined same-level joins, C-21).
- **`assert_reindex_fill_law`** in the published conformance suite (ADR-016): result
  index equals the target row-for-row; present rows bit-exact; absent rows equal the
  fill (NaN-safe); on a superset frame the fill degenerates to `reindex`.
- Consumer note: faoapi's `dense_grid.py` can now delegate (its last-step-entity rule +
  C-87 dropped-entity check stay consumer-side) and drop its pandas implementation
  (faoapi #242). Densification allocates the full dense buffer — a deliberate, costly
  act at grid scale (documented on both symbols).

## [1.9.0] — 2026-07-24

**The tower-tip MAP reads the top floor (ADR-019 Amendment 3): `tip_mass` 0.5 → 0.25.**
Behavior change to `tower_point`/`summarize_tower` outputs, shipped MINOR per the C-44/C-45
precedent (estimator amendment with ADR evidence); `CONFORMANCE_FLOOR` stays `1.0.0`.

### Changed
- **`tip_mass` default 0.5 → 0.25 (the top-quartile floor).** The tower-tip MAP is now the
  median of the **top floor of the published tower**, matching the design intent the name
  always promised. Evidence (`research/map_hdi/tip_mass_study.py`, 1000-replicate battery +
  duplicate-capture frontier + the real-cell C-44 gate): the 0.5 shorth carried a structural
  rightward bias that does not shrink with sample count; 0.25 roughly halves it, beats the
  shorth on RMSE at pooled S, reads zero-inflated cells exactly, and passes the real-cell
  zero-stack gate with margin (masses ≤ 0.15 resurrect the C-44 signal loss; 0.20 has zero
  margin). Consumer note: published MAPs shift toward the mode on skewed cells — the intended
  C-32 direction.

### Added
- **MAP-containment law** in `assert_summarizer_contract`: every floor holding more than half
  the tip floor's draws (asymptotically mass > `tip_mass`/2 = 12.5%) provably contains the
  tip — wider floors by nesting, narrower qualifying floors by the sub-window trim argument.
  All published bands (50/90/95/99) qualify; the unguaranteed region *shrinks* versus the old
  default (was: everything below 0.5).
- `research/map_hdi/tip_mass_study.py` — the committed evidence trail for the amendment.
- `research/figures/` — permanent, seeded generators for the PRN06 tower figures (overlay +
  detail, upright-tower rendering), with `reports/plots/` as the gitignored output home.

## [1.8.1] — 2026-07-02

**Falsification-audit hardening (four-axis audit 2026-07-02; register C-67/C-68/C-69/C-70).**
Bug fixes with an identical contract — the code now honors what the docs already promised.
No public-surface change; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Fixed
- **`reconcile_proportional` conserves exactly for any nonzero draw sum (C-68, the audit's one
  hard finding).** The torch-port's `+ 1e-8` denominator epsilon — a float32 no-op for draw sums
  ≳ 0.1 but a **silent** deflator for tiny nonzero sums (a draw sum of 1e-8 reconciled a country
  total of 100 to 50, with no error signal, violating the Reconcile.md §3 sum-to-country
  guarantee) — is replaced by an explicit all-zero-draw guard: exact division for any nonzero
  sum; all-zero draws stay zero exactly as before. **Bit-identical on all realistic data**
  (torch-oracle parity unchanged and green).
- **Negative country totals now fail loud (C-68/F8):** `reconcile_proportional` raises
  `ValueError` instead of silently clamping the output to zero (sum 0 ≠ the requested total).
- **The published conformance suites refuse to run under `python -O` (C-67):** all three
  (`views_frames.conformance`, summarize, reconcile) now guard their entry points with
  `_require_assertions()` — under optimized bytecode (which strips the suites' `assert`
  statements) they raise `RuntimeError` instead of silently reporting green.
- **Empty-index `searchsorted` returns all `-1` (C-69)** — the documented not-found value —
  instead of crashing with an obscure `IndexError` (the `np.clip(pos, 0, -1)` corner).

### Notes
- Regression pins for all four fixes: `tests/test_falsification_safety_audit_2026_07.py`.
- `Reconcile.md` §6 documents the two reconcile behaviors; `proportional.py`'s module docstring
  records the deliberate (bit-parity-preserving) deviation from the torch original.
- Register: C-67/C-68/C-69 registered-and-resolved; **C-70** (the audit's docs/tests polish
  bundle) opened and **cleared in the same release** (below).

### Tests
- **C-70 test adds** (#195): the share-**proportionality law** (the method's defining
  forecast-proportion property, previously pinned only by the frozen-oracle fixtures); an mmap
  **read-only pin** (`writeable is False`, in-place write raises); the reconcile
  missing-`(time, priogrid_gid)`-mapping-entry raise.

### Documentation
- **C-70 docs refresh** (#196): `CLAUDE.md` rewritten for the released three-package reality;
  README banner → v1.8.0 + chronicle; ADR-013 as-built amendment (`feature_names`); CIC accuracy
  fixes (§5 artifact names → `values.npy`, PredictionFrame §6 real dtype behavior, index §6
  NaN-via-dtype, Reconcile §10 pinning files); CICs/ADRs README framing refreshed; and a
  **recurrence guard** — `validate_docs.sh` now checks the README banner's MAJOR.MINOR against
  `pyproject.toml`.

## [1.8.0] — 2026-06-28

**Native point-country broadcast in `views_frames_reconcile` (ADR-023 amendment, #143 / Epic #142),
the three showcase notebooks (Epic #166), and a governance/test hardening pass (Epic #179).** All
additive — the frozen leaf and summarize public surface are unchanged, and the hardening work makes
**no `src/` behaviour change**; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`ReconciliationModule.reconcile` accepts a point country** (`cm.sample_count == 1`) against a draws
  grid (`pgm.sample_count == S`): the point is broadcast across the `S` draws inside the orchestrator
  (`np.tile`), so callers no longer tile it themselves (the DRY home of pipeline-core's WET
  `align_country_to_grid`, #143). The **aligned-draws** path (`cm.sample_count == S`) is byte-for-byte
  unchanged; any other count still fails loud.
- **`ReconciliationModule.reconcile_result(cm, pgm) -> ReconciliationResult`** (#144) — reconciles and
  **reports the mode** (`POINT_BROADCAST` | `ALIGNED_DRAWS`) + method (`proportional`) on a returned
  `ReconciliationResult`. The mode is *returned*, never stamped on the leaf's generic `FrameMetadata`
  (ADR-020 / register C-47 — the numpy leaf carries no reconciliation vocabulary). `reconcile` is
  unchanged (it returns `reconcile_result(...).frame`). New public names: `ReconciliationResult`,
  `POINT_BROADCAST`, `ALIGNED_DRAWS`, `METHOD_PROPORTIONAL`.

### Notes
- The broadcast lives entirely in `views_frames_reconcile/module.py`; the leaf `proportional` and the
  parity-frozen `grouping` hot loop are untouched, so the torch-oracle parity is exact (0.000e+00).
- The aligned-draws mode remains the documented per-draw approximation. **ADR-024** (#145) records the
  design direction + deferral for the principled joint upgrade (and corrects `proportional.py`'s
  ambiguous "C-37" reference; register C-62). Design-only — no code.

### Documentation
- **Three showcase notebooks** (`notebooks/01_frames`, `02_summaries`, `03_reconciliation`; Epic #166):
  public-frozen-API-only, synthetic-data teaching notebooks for the frames contract, the posterior
  summaries (with a calibration/coverage + PIT panel), and reconciliation — including a
  bit-identity-≠-method-quality panel and a toy-lattice spatial view (register C-59/C-60/C-61).
- **`docs/CICs/Reconcile.md`** (Epic #179) — the package-level Class Intent Contract for
  `views_frames_reconcile` (§1–§11): the sum-to-country / zero-preservation / non-negativity /
  de-mutation guarantees, the point/aligned **mode** contract, the five fail-loud validation guards
  + the per-draw-approximation caveat, and the green/beige/red test alignment. The reconcile package
  was the last non-trivial surface without a CIC (ADR-006); **register C-64 resolved**.
- **ADR-025 — value-buffer immutability is by convention; only the index is enforced** (Epic #179).
  Corrects the "immutable value objects" contract (the three frame CICs §9/§3 + README design
  principle 3) to match the code: the index (`time`/`unit`) is `setflags(write=False)`-enforced; the
  value buffer is immutable *by convention* (left writeable to preserve zero-copy / `mmap` — mutating
  `.values` in place is unsupported). The `setflags`-enforce on `.values` would be a MAJOR
  ("tightening an invariant" on a frozen-surface member, GOVERNANCE/ADR-018), so it is recorded as a
  **deferred MAJOR-rider**, not done now; **register C-63 resolved** (contract corrected).

### Tests
- **Adversarial (red) test hardening** (Epic #179), no `src/` change, 100% line+branch coverage held:
  - the non-finite (NaN / ±inf) fail-loud guard in `exceedance`/`expected_shortfall` is now pinned on
    the **blocked (multi-block) path** — the bad draw placed in a non-first block via the `block_rows`
    kwarg with block 0 all-finite (**register C-65 resolved**);
  - **conformance-suite negatives** — `assert_reconcile_contract` and `assert_summarizer_contract` are
    shown to reject a deliberately non-conforming implementation (the leaf's C-51 envelope-negative
    pattern, extended to the sibling packages);
  - **reconcile mode-corners** — `reconcile_result.mode` for both-points and pre-tiled-cm inputs (both
    `ALIGNED_DRAWS`); and **`ReconciliationResult` frozen-ness** (`FrozenInstanceError`).

## [1.7.0] — 2026-06-26

**Forecast reconciliation is a third sibling package (ADR-023, Epic 11).** A new importable
package `views_frames_reconcile` joins `views_frames` + `views_frames_summarize` in the mono-wheel.
Additive surface — the leaf and summarize are unchanged; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`views_frames_reconcile`** — numpy + `views_frames` only — makes grid (`pgm`) predictions sum,
  per posterior draw, to their country (`cm`) totals:
  - **`ReconciliationModule(map_keys, map_vals)`** — orchestrator holding the **injected**
    `(time, priogrid_gid) → country_id` mapping (never fetched here; ADR-014/ADR-023);
    `.reconcile(cm_frame, pgm_frame)` returns a new pgm `PredictionFrame`.
  - **`reconcile_proportional(grid, country)`** — the per-draw top-down proportional method
    (zeros preserved, country totals authoritative, non-negative).
  - **`assert_reconcile_contract(...)`** — the conformance suite (sum-to-country per draw,
    zero-preservation, non-negativity, level correctness, injected mapping).
- A faithful **WET relocation** of the parity-proven reconciler from views-postprocessing — the
  ported modules differ from the originals by import lines only (no algorithmic change).

### Notes
- **Charter (ADR-023):** frame-reconciliation algorithms only; **never fetch the mapping** (injected
  as arrays, like `cross_level_align`); no IO, scoring, plotting, or foreign `views_*`. Import-DAG
  `views_frames_reconcile → {views_frames}`.
- **Parity is the gate:** green against the frozen views-reporting torch oracle, **and** a
  new-vs-old bit-identity head-to-head (`np.array_equal`, 136 cases) vs the old
  `views_postprocessing.reconciliation` — proven bit-identical at relocation.
- **WET before DRY:** `grouping.py` overlaps the leaf's `cross_level_align`; folding them is a
  deferred later story. The principled probabilistic upgrade (C-37) will be a future sibling module.
- Consumer repoint (views-models) + views-postprocessing deletion are the cross-repo cutover, gated
  on this release.

## [1.6.0] — 2026-06-25

**Worst-case scenario estimator (ADR-022, register C-55/C-56 Resolved).** Additive surface — the
frozen v1.0–v1.5 estimators are unchanged; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`expected_shortfall(frame, tails, *, block_rows=ROW_BLOCK)` → `(N, …, K)` array** — the per-row
  **mean of the worst `⌈t·S⌉` draws** for each upper-tail fraction `t` (the tail mean / CVaR): a
  robust, **coherent** (subadditive) worst-case risk measure and the companion to `exceedance`.
  Vectorized over the trailing sample axis in row-blocks.
- **Conformance:** `assert_summarizer_contract` now also checks the ES laws — `min ≤ ES ≤ max`,
  non-decreasing as the tail deepens, and `ES(t) ≥ the (1 − t)` quantile.

### Notes
- **`max` is never offered** — it is the highest-variance, non-reproducible summary `expected_shortfall`
  replaces (D-10). **Tails are required per-call, no default, not in config**, in `(0, 1]` — the
  consumer's policy. **Fails loud** on any **non-finite draw — NaN or ±inf** (C-56; the guard is
  `np.isfinite`, hardened by the falsify audit 2026-06-25 so an `inf` draw can't silently contaminate
  the tail mean to `inf`), empty `tails`, or any `t ∉ (0, 1]`.
- **Best case ships no code** — a low quantile (`quantiles(frame, [0.005])`) + `exceedance(frame, [0])`
  express it, including the "model puts no mass at zero" case.
- Country worst-case = `aggregate_distributions` → `expected_shortfall` (the estimator never
  aggregates; the joint-sample obligation is the consumer's, C-55).
- **WET before DRY:** its own module, written explicitly — *not* refactored into a shared "tail
  reducer" with `quantiles`/`exceedance`. Deferred, reversible extensions: a lower-tail/`side` mode, an
  `expected_shortfall_reducer`, `cvar`/`tail_mean` synonyms (D-10).

## [1.5.0] — 2026-06-24

**Threshold exceedance-probability estimator (ADR-021, register C-49/C-50 Resolved).** Additive
surface — the frozen v1.0–v1.4 estimators are unchanged; `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`exceedance(frame, thresholds, *, block_rows=ROW_BLOCK)` → `(N, …, K)` array** — the per-row
  empirical survival fraction `P(Y > c_k)` for each of `K` caller-supplied thresholds (same
  shape/role family as `quantiles`), vectorized over the trailing sample axis in row-blocks.
  Distribution-agnostic (a counting reducer); the flagship is `P(Y > 0)` = onset.
- **`exceedance_reducer(threshold)` → `Reducer`** — a `collapse`-compatible factory, so
  `collapse(frame, exceedance_reducer(c))` returns `P(Y > c)` as a `(N, …, 1)` frame, sharing one
  strict-`>` / fail-loud-non-finite policy.
- **Conformance:** `assert_summarizer_contract` now also checks the exceedance laws — values in
  `[0, 1]`, non-increasing in the threshold, `P(> −inf) = 1`, `P(> +inf) = 0`.

### Notes
- **Thresholds are required per-call, no default, not in config** — an *input* in the frame's own
  units, like `quantiles`' `qs` (ADR-021). Canonical VIEWS thresholds (25/100/1000 country, 5/25
  grid) are documentation only, never an executable default.
- **Strict `>`** (D-08; for integer counts `P(Y ≥ k)`, pass `k − 1`). **Fails loud** on any
  **non-finite draw — NaN or ±inf** (C-50; `np.isfinite` guard, hardened by the falsify audit
  2026-06-25 so an `inf` draw can't silently bless `P` as valid — ±inf *thresholds* stay valid) and on
  empty thresholds. Country exceedance = `aggregate_distributions` → `exceedance` (the estimator never
  aggregates; the joint-sample obligation is the consumer's, C-49).
- **Deferred, reversible extensions:** an `inclusive`/`≥` flag (D-08), a `nan_policy='skip'` (D-07),
  relative/reference-frame thresholds, an EP-curve helper.

## [1.4.0] — 2026-06-24

**Generic provenance + a published frame-envelope checker (ADR-020, register C-46/C-47).**
Operationalises the substrate half of the `MetricFrame` decision: views-evaluation hosts
`MetricFrame` on the views-frames substrate, and this release provides the two leaf-side
pieces it reuses. No change to the frozen surface (ADR-018); `CONFORMANCE_FLOOR` stays `1.0.0`.

### Added
- **`FrameMetadata.run_id` / `FrameMetadata.data_version`** — optional, **generic** provenance
  (additive/MINOR, ADR-013). Meaningful for any frame; they ride the existing
  `to_dict`/`from_dict` and IO round-trip unchanged. Evaluation-specific provenance
  (`scoring_code_version`, full-precision `evaluation_timestamp`) deliberately stays in
  views-evaluation's `MetricFrame`, never this generic header (the C-47 guard).
- **`views_frames.conformance.assert_frame_envelope`** — the shared **frame envelope** (float32
  values, explicit trailing axis, save/load round-trip) factored out of `assert_frame_contract`
  as a single written authority. A non-spatiotemporal sibling (views-evaluation's string-keyed
  `MetricFrame`) validates against it instead of re-asserting drifting copies (mitigates C-46).
  `assert_frame_contract` now composes the envelope + the spatiotemporal `(time, unit)` rule.

### Fixed
- **Conformance round-trip is now NaN-tolerant.** `_assert_roundtrip` compared values with
  `np.array_equal` (NaN-blind: `NaN != NaN`), so a *correct* round-trip of a frame carrying NaN
  values raised a spurious `"save/load changed values"`. Now uses `equal_nan=True` on the float32
  values. This matters for `assert_frame_envelope`'s intended consumer — evaluation metrics are
  realistically NaN ("not calculated"). A bugfix that only *removes a false rejection*, so
  `CONFORMANCE_FLOOR` stays `1.0.0`.

### Notes
- The cross-repo **wire schema + `schema_version`** marker (the other half of the C-46
  mitigation) is the emit/consume wire contract and remains future work, tracked on C-46.

## [1.3.0] — 2026-06-24

**Distribution-agnostic tower summary (register C-45).** Removes a count-domain magnitude
assumption from the tower estimators: the "quiet row" rule zeroed any posterior whose
`max(draws) <= 1.0` — zeroing *every* cell of a rate/probability `[0,1]` target and silently
erasing low-intensity counts. The estimators now work for **any** distribution (counts,
continuous, normal, beta/probability). No change to the frozen estimators (ADR-018);
`CONFORMANCE_FLOOR` stays `1.0.0`.

### Changed
- **No magnitude-based zeroing by default.** `tower_point` / `hdi_tower` / `summarize_tower` /
  `bimodality` no longer collapse sub-1 rows to 0. Zero-inflation is handled by the **density**
  of the `tip_mass` floor (a zero-majority row reads 0 naturally), which is distribution-agnostic.
- **`config['zero_cutoff']` is now an optional, off-by-default opt-in** (default `None`). A count
  consumer that wants "sub-1 ⇒ 0" sets it to a float; it is read **live** (the prior import-time
  snapshot, which made the knob non-configurable at runtime, is fixed).

### Notes
- The modeling choice "should a sub-1 *count* posterior read 0?" is the **consumer's** (set
  `zero_cutoff`, or apply a downstream `mass_at_zero` policy) — not a leaf default.
- ADR-019 amended; the Summarize CIC documents the opt-in and the consumer-owns-the-zero-policy
  note. Register **C-45 → Resolved**.

## [1.2.0] — 2026-06-24

**Outside-in HDI tower + mass-aware tip + fail-loud config (register C-44).** Fixes a silent
output-correctness bug in the v1.1 tower estimators: a **minority duplicated draw** (a couple
of exact zeros, a lone pair) could hijack the degenerate ~2-sample narrowest floor and collapse
both `tower_point` and the nested `hdi_tower` bands — confirmed on real faoapi forecast cells.
No change to the frozen estimators (`map_estimate`/`hdi`/`quantiles`, ADR-018);
`CONFORMANCE_FLOOR` stays `1.0.0`.

### Changed
- **The canonical tower is now built `outside-in`** (widest floor first, each narrower floor the
  shortest interval *contained in* its wider parent) instead of inside-out. Robust by
  construction: a lonely outlier is shed by the well-determined wide floors and the containment
  constraint forbids a narrower floor from re-selecting it. Nesting + reproducibility laws
  unchanged.
- **`tower_point` reads the configurable `tip_mass` floor** (default `0.5` — the "shorth"),
  not the degenerate 5% floor — a mass-aware, duplicate-robust point.
- **The tower-family public functions drop their tunable kwargs** (`bins`/`prominence`/
  `min_mass`/`block_rows`); those values now come from the config (below). `masses` stays a
  per-call argument. The frozen estimators are untouched.

### Added
- **`views_frames_summarize.config`** — a fail-loud config (`TOWER_CONFIG` dict, `REQUIRED_KEYS`,
  `validate_config`, `get`, `canonical_floors`) holding every tower-family tunable (the grid,
  `tip_mass`, the zero cutoff, the bimodality thresholds, the row-block) with **no silent
  defaults**: a missing key raises `ValueError` naming it (ADR-008/009).
- Conformance: the tip law is restated to **tip ∈ the `tip_mass` floor**; a large adversarial +
  edge test matrix (the C-44 truth table A–L, real faoapi cells, duplicate-count sweep,
  NaN/inf locality, multimodality, config fail-loud) — `tests/test_summarize_config.py` added.

### Governance
- **ADR-019 amended** (inside-out → outside-in; `tip_mass`; config). **Register: C-44 → Resolved**
  (Tier 1); C-32 / C-34 mitigation notes updated. The Summarize CIC records the new construction,
  the `tip_mass` tip, and the config failure mode.

## [1.1.1] — 2026-06-24

Documentation only — no public-API or behaviour change (identical contract).

### Documentation
- README: a "Which estimator?" note (frozen `map_estimate`/`hdi`/`quantiles` vs the
  coherent-tower `tower_point`/`hdi_tower`/`summarize_tower`) and a **bimodality caveat** —
  a `bimodality` `0` means "no clear bimodality detected," **not** "proven unimodal"
  (conservative-by-design, register C-34/C-42).
- Corrected the `tower._pin` docstring (ties resolve **down** to the lower floor via
  `argmin`'s lowest-index rule) and the `research/map_hdi/audit.py` stale tuple-unpack
  (register C-41).

## [1.1.0] — 2026-06-24

**Coherent posterior summary (ADR-019).** Additive new surface in `views_frames_summarize`
— the frozen v1.0 estimators (`map_estimate`/`hdi`/`quantiles`/`collapse`/`aggregate_*`) are
unchanged. A constrained-nested HDI tower resolves the C-33 nesting gap and mitigates the
C-32 mode bias.

### Added
- `hdi_tower(frame, masses)` → `(N, …, M, 2)` — nested-**by-construction** HDIs read off a
  **fixed canonical grid** (5% body + fine tail to 0.99); requested masses are *pinned*,
  never inserted, so a mass's interval is reproducible regardless of which other masses are
  requested (resolves register **C-33**). Out-of-range masses fail loud (ADR-008).
- `tower_point(frame)` → `(N, …, 1)` frame — the **tower tip** (median of the narrowest
  floor) with a raw-count zero short-circuit: an unbinned, directionally-unbiased
  alternative to the C-32-biased `map_estimate` (mitigates **C-32**).
- `bimodality(frame)` → `(N, …, 1)` — a deliberately conservative 0/1 flag for genuinely
  multi-peaked rows (where a single point / shortest interval is ill-defined).
- `summarize_tower(frame, masses)` → `TowerSummary(point, intervals, bimodal, masses)` — a
  single-pass bundle deriving all three from one sort; provably equal to the trio.
- Conformance suite extended with the tower laws (nesting / tip-in-narrowest /
  reproducibility / bundle==trio); `tests/test_summarize_tower.py` (🟩/🟫/🟥 per ADR-005).

### Governance
- **ADR-019** records the decision; the `Summarize` CIC documents the new surface and its
  failure modes. Register: **C-33 → Resolved**; **C-32 → mitigation note** (a non-biased
  point now exists; a fully-convergent mode remains #89). Evidence + research note under
  `research/map_hdi/`.

## [1.0.1] — 2026-06-23

**Test hardening (Epic 6).** No public-API change — the frozen v1.0 surface is unchanged.
Closes the post-freeze test-coverage debt: every fail-loud branch and the cross-frame shared
surface are now exercised, and CI enforces 100% line coverage.

### Added
- 🟥 IO failure-mode tests (`tests/test_io.py`): `arrow.save` bad ndim, `FeatureFrame.load`
  missing `feature_names`, `npz.load` missing sidecar, `arrow.load` non-frame parquet
  (register C-29).
- `tests/test_frame_parity.py` — a parametrized matrix asserting `reindex`/`select`/
  `with_metadata`/`save`-`load` across all three frame types, filling the Feature/TargetFrame
  `reindex` gap (register C-31).
- `tests/test_construction_red.py` — construction/validation fail-loud reds (3-D →
  `PredictionFrame`, row-mismatch, `from_2d`, malformed identifiers/values).
- `tests/test_value_object_and_laws.py` — index value-object semantics (`__hash__`/`__eq__`/
  `argsort`), the `SpatialLevel` vocabulary, and the two CIC alignment laws (align∘collapse
  commute; `reindex` idempotent on a superset).

### Changed
- CI (`ci.yml`) enforces **100% line coverage** (`pytest --cov --cov-fail-under=100`) and now
  runs on `development` as well as `main`. `pytest-cov` added to the dev dependency group.

## [1.0.0] — 2026-06-21

**API freeze (ADR-018).** Leaf completion (Epic 5) — the second-round consumer-review
findings, then the v1.0 freeze. Two rounds of consumer review validated
the design (no ADR challenged). From here the public surface is frozen; breaking
changes are MAJOR (GOVERNANCE "Stability — the v1.0 freeze"). The pre-1.0
breaking-in-MINOR latitude ends.

### Added
- `FeatureFrame`/`PredictionFrame`/`TargetFrame` gain `select(positions | mask) ->
  Frame` and `reindex(other) -> Frame` (frame-level row selection / alignment; the
  former returned only positions). `SpatioTemporalIndex.select(indexer)` underlies them.
  Closes the second-round consumer gap F12.
- `SpatioTemporalIndex.cross_level_align_arrays` + `aggregate_distributions_arrays` —
  columnar `(map_keys, map_vals)` mappings, ~30× faster / ~10× less memory than a
  grid-scale Python dict (benchmark-gated; register C-26).

### Changed
- **`map_estimate` tie-break is now deterministic and portable** — it breaks ties on
  integer counts (lowest-index), not `np.histogram(density=True)`'s width-based
  argmax, which differed by ~1 ulp across numpy versions and flipped on ties. Output
  is now identical on every numpy build (register C-24). Only tied rows differ from
  v0.3.0; ties are arbitrary, so this is a strict portability win.
- `hdi`/`quantiles` are row-blocked like `map_estimate`; all three estimators take a
  `block_rows` kwarg. Peak memory no longer scales with the full grid (register C-25).
- `Persistable.save`/`load` typed `Path | str` to match the concretes (register F-L).
- Conformance floor `CONFORMANCE_FLOOR = "1.0.0"`; it tracks the whole published
  conformance surface and bumps on breaking changes to it (register C-27).

### Fixed
- The `map_estimate` equivalence test asserted bit-exact float32 equality and was red
  on the numpy 1.26 floor while green in CI; the **`floor` CI job now runs pytest** at
  `numpy==1.26.4`, not just mypy — the floor is behaviour-checked (register C-24).
- README: `MetricFrame`/C-48 framing softened to "substrate, not the cure" (it is out
  of the leaf); status header → v1.0.0.

### Governance
- **ADR-018** records the freeze and the frozen surface; GOVERNANCE adds the 1.0
  stability policy and the pre-1.0 latitude's end.
- `examples/cross_level.py` demonstrates the time-varying mapping + `HDI(sum) ≠ sum(HDI)`.

## [0.3.0] — 2026-06-21

Hardening release (Epic 4) — the first-round consumer-review findings.
No new surface beyond a time-aware mapping; correctness, typing, and scale.

### Changed (breaking, pre-1.0)
- **`cross_level_align` / `aggregate_distributions` mappings are now keyed by
  `(time, unit)`** (`Mapping[tuple[int, int], int]`), not `unit` alone — ADR-014's
  mapping is time-varying (a cell's country changes by month) and the static shape
  could not express it (register C-20). The remap is vectorized (void-viewed keys +
  `searchsorted`) and fails loud on the old unit-only shape or a missing key.

### Added
- `assert_cross_level_alignment_law` in `views_frames.conformance` — the time-varying
  cross-level law (one cell, two months → two target units).
- `SpatioTemporalIndex.has_unique_rows()` + a documented `(time, unit)` row-uniqueness
  stance (duplicates allowed; same-level joins assume uniqueness — register C-21).
- `index` on the `SpatioTemporalIndexed` protocol (a consumer typing to the abstraction
  can reach `.index`/`cross_level_align` — register C-23/F4).
- `py.typed` markers in both packages (the package is now seen as typed — register C-23).
- A CI **`type-floor`** job pinning `numpy==1.26.4`; `mypy --strict` is green at the
  declared floor (was 14 `[type-arg]` errors hidden behind numpy 2.x — register C-19).
- `examples/quickstart.py` (a runnable end-to-end example) + an in-repo synthetic
  grid-adapter proxy test (`tests/test_proxy_adapter.py`, register F15 in-repo).

### Performance
- `map_estimate` and `hdi` are vectorized over the trailing axis (no per-row Python
  loop); `map_estimate` runs a **row-blocked** batched histogram that caps peak memory
  at `O(block × bins)` and stays identical to v0.2.0 to float32 precision —
  bit-exact on numpy ≥ 2.0, ~1 ulp on the 1.26 floor (register C-22/#181, C-24).
  A `tracemalloc` scale guard asserts memory does not scale with `rows × bins`.

### Fixed
- Doc↔code drift: README version header, the nonexistent `align` op (§4.3), and the
  `collapse` glossary entries (§13a.2/§14 — `collapse` lives in the sibling package).

## [0.2.0] — 2026-06-21

Two-package release: the leaf is now a pure data contract; sample-axis summarization
moved to a sibling package (ADR-017).

### Added
- `views_frames_summarize` — a second package (numpy-only, depends on `views_frames`)
  for sample-axis posterior summarization over frames:
  - `collapse(frame, reducer)` — generic point fold (statistic injected) → `(N,…,1)` frame.
  - `map_estimate(frame)` — histogram-peak MAP with a zero-mass→0 rule → frame.
  - `hdi(frame, mass)` — shortest-interval HDI → `(N,…,2)` index-aligned array.
  - `quantiles(frame, qs)` → `(N,…,len(qs))` index-aligned array.
  - `aggregate_distributions(frame, mapping, level)` — conservation-correct joint-sampling
    cross-level aggregation (`HDI(sum) ≠ sum(HDI)`), reusing the leaf's injected mapping.
  - `views_frames_summarize.conformance.assert_summarizer_contract`.

### Changed (breaking, pre-1.0)
- **Removed `collapse` (and `SUPPORTED_AGGREGATE_METHODS`) from the leaf frames** and
  from the `Sampled` protocol; the leaf keeps only the structural `sample_count`/
  `is_sample`. All sample-axis reduction is now in `views_frames_summarize` (ADR-017).
- The import-enforcement test is now a two-package DAG: `views_frames` imports no
  `views_*`/pandas (so never the summarize package); `views_frames_summarize` imports
  only `views_frames` + numpy.

## [0.1.0] — 2026-06-21

First implemented release — the leaf is functional and releasable (Epic 2).

### Added
- `SpatioTemporalIndex` — immutable `{time, unit, level}` row index with pure-numpy
  same-level alignment (`intersect`, `reindex`/`searchsorted`, `is_superset_of`,
  `argsort`) and `cross_level_align(mapping, target_level)` with a **consumer-injected**
  mapping (ADR-014).
- `SpatialLevel` — cm/pgm identifier vocabulary, time-first index names (ADR-015).
- The frame family (separate siblings, no shared base — ADR-011): `PredictionFrame`
  `(N, S)`, `FeatureFrame` `(N, F, S)` (+ `from_2d` shim), `TargetFrame` `(N, 1)`.
  The sample axis is always an explicit trailing axis (ADR-012).
- `FrameMetadata` — typed, optional-extensible provenance header (ADR-013).
- Protocols `Frame` / `SpatioTemporalIndexed` / `Sampled` / `Persistable`.
- `io/npz` (native, mmap-capable) and `io/arrow` (flat-columnar parquet; the `[arrow]`
  extra). Object-dtype / list-in-cell is banned.
- `views_frames.conformance` — the published conformance suite + the conformance
  floor (ADR-016, `GOVERNANCE.md`).
- Construction is fail-loud and numpy-only; structural (not temporal) validation.

### Notes
- Resolves register concerns C-07 (copy-vs-view), C-09 (generic io state),
  C-11 (structural-not-temporal), C-14 (injected cross-level mapping), C-17
  (numpy-only `PredictionFrame`).
- Out of scope (Epic 3): consumer adoption (re-export shims in pipeline-core /
  datafactory; pandas migration).
