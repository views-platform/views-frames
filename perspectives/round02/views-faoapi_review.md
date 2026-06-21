# views-frames — Review (round 02, from the views-faoapi agent)

> **Reviewer:** Claude (Opus 4.8), from the `views-faoapi` working context — an AI
> agent that would *consume* `views-frames` as the serving/delivery layer (forecast
> `PredictionFrame`s, historical `TargetFrame`s, server-side MAP/HDI, geographic
> aggregation).
> **Date:** 2026-06-21. **Reviewed at:** `v0.3.0` ("hardening release — round-01
> findings"). **Prior round:** `perspectives/round01/views-faoapi_review.md`.
> **Method (read-only):** read `src/views_frames/index.py` (cross-level section) and
> `src/views_frames_summarize/point.py` **in full**; read `examples/quickstart.py`,
> `protocols.py`, `_typing.py` in full; mapped the rest via `git log`, the CHANGELOG,
> the test inventory, and targeted greps. I did **not** execute the suite/type-checker
> this session (Bash was usable but I did not run tests to honor the read-only spirit);
> where I rely on a claimed result (the bit-for-bit and `tracemalloc` guards) I say so.
> **No source modified, nothing staged, no commit, no branch; only this report written.**

---

## 0. Verdict

**This is a model of how to respond to a review.** v0.3.0 is, by its own CHANGELOG,
"the round-01 review findings," and it delivers: the one *substantive* gap I flagged —
a time-blind `cross_level_align` whose docstring lied about being time-varying — is
**fully fixed** (now `(time, unit)`-keyed, vectorized, fail-loud), and almost every
other round-01 item is closed (`py.typed`, a runnable quickstart, the protocol `.index`,
a uniqueness stance, mypy-strict green at the numpy floor, vectorized `map_estimate`/
`hdi` with a memory guard, doc drift fixed). The team even **registered my findings as
C-19..C-23** and drove them through a review→register→fix→test→changelog loop. From the
consuming seat, the repo moved from "strong, with a real hole" to "hardened."

What remains is no longer *correctness* but **architectural completeness and proof**:
the consumer-side conveniences a real adopter needs (`select`/subset, a frame-level
`reindex(other) -> Frame`) are still absent; the cross-repo claim is still demonstrated
only by a synthetic in-repo proxy, not a real consumer; and v0.3.0 introduced two new
things worth a second look — **the cross-level *interface* still forces a giant Python
dict at the caller boundary** (the scale fix is half-done), and **the MAP estimator is
now a 104-line bespoke replica of numpy's histogram internals** (correct, tested, but
fragile and concentrated in the most decision-critical number).

**Adoptable-soon. The blocker is no longer "is it right" but "prove it with a real
consumer and finish the consumer-facing surface."**

---

## 1. Does the repository now do what I need it to do?

**Yes — more so than last round.**
- **Purpose & structure:** unchanged and still excellent; the two-package split
  (`views_frames` leaf / `views_frames_summarize` statistics) is clear, one-concept-
  per-file holds.
- **Can I see how I'd use it? — *now yes, directly.*** `examples/quickstart.py` is the
  on-ramp that was missing in round 01: index → `PredictionFrame` → `collapse`/
  `map_estimate`/`hdi` → `save`/`load` → `assert_frame_contract`, numpy-only, ~40 lines.
  It even ends on the conformance check, teaching the consumer the *right* pattern. As
  the faoapi agent I could wire an adapter from this alone.
- **Abstractions:** the protocol surface is now usable for the alignment use-case —
  `SpatioTemporalIndexed` exposes `.index` (`protocols.py:36`), so a consumer typed to
  the abstraction can reach `cross_level_align`. `_typing.py`'s `IntArray`/`Float32Array`
  give the identifier/value arrays named contracts.

**The faoapi-specific needs:** both frames I serve exist; the MAP/HDI/quantile reductions
I compute are in the sibling and now scale; and the `pg→country/gaul` aggregation works
with a *correct, time-aware* mapping — the exact thing that was broken last round. The
only faoapi need still unmet is convenient subsetting (I subset by time/entity/feature on
every request; see §4).

---

## 2. Does it do things in the way I would want?

**Largely yes, with the same high-quality grain as before plus two new wrinkles.**
- **The cross-level fix is textbook** (`index.py:180-242`): `Mapping[tuple[int,int],int]`,
  vectorized via void-viewed keys + a single `searchsorted`, raises on the old unit-only
  shape *and* on a missing `(time, unit)` with the offending pair named. Time preserved.
  This is exactly the shape I asked for.
- **The uniqueness stance is explicit and right** (`index.py:167-176`): duplicates
  allowed in a frame; `has_unique_rows()` is an opt-in `O(n log n)` guard; the docstring
  states same-level joins assume uniqueness. The unstated assumption from round 01 is now
  stated.
- **Immutability/zero-copy, executable architecture, conformance suite** — all still
  present and now extended (a `assert_cross_level_alignment_law` time-varying law).
- **New wrinkle 1 — the cross-level *interface* fights its own scale goal.** The remap is
  vectorized *inside* the leaf, but the contract takes a `Mapping[tuple[int,int],int]` —
  so the consumer must first materialize a Python dict with one entry per `(time, unit)`
  row (at full calibration grid, ~10.5M tuple keys). Building that dict is an O(N) Python
  allocation on the caller side *before* the vectorized step — re-introducing, at the
  boundary, the kind of cost the change was meant to remove. An array-triple
  (`map_time[]`, `map_unit[]`, `map_target[]`) or an injected callable would let the
  consumer stay vectorized end-to-end.
- **New wrinkle 2 — the interval API is asymmetric.** `collapse`/`map_estimate` return
  *frames*; `hdi`/`quantiles` return *bare `(N, k)` numpy arrays* (index-aligned, per the
  quickstart). A consumer (faoapi serves HDI bounds) must re-attach the index by hand. A
  small inconsistency: point estimates are frame-wrapped, interval estimates are not.
- **Unaddressed nit:** `Persistable.save(self, directory: str)` (`protocols.py:64`) still
  types `str` while the concretes accept `Path | str` — the round-01 protocol/impl
  mismatch persists. And `searchsorted` still carries `get_indexer` (not numpy) semantics
  under a numpy name.

---

## 3. What has improved since the previous round?

A near-complete sweep of the round-01 report (and the companion `round01.md`):

| Round-01 finding | Status in v0.3.0 | Evidence |
|---|---|---|
| **`cross_level_align` time-blind / docstring lied** (my headline) | **Fixed** — `(time,unit)`-keyed, vectorized, fail-loud | `index.py:180-242`; CHANGELOG "Changed (breaking)"; register C-20; commit `de487ef` |
| Missing `py.typed` | **Fixed** — both packages | `src/views_frames/py.typed`, `…_summarize/py.typed`; register C-23 |
| No Quickstart / `examples/` | **Fixed** — runnable end-to-end | `examples/quickstart.py` |
| No protocol `.index` (companion §6.4) | **Fixed** | `protocols.py:36` |
| Unstated `(time,unit)` uniqueness | **Fixed** — documented + `has_unique_rows()` | `index.py:167-176`; register C-21 |
| `mypy --strict` red on numpy floor (companion §6.1) | **Fixed** — `_typing.py` + a CI `type-floor` job pinning `numpy==1.26.4` | `_typing.py`; register C-19 |
| Per-row `apply_along_axis` in `map_estimate`/`hdi` (companion §6.3) | **Fixed** — vectorized + row-blocked + scale guard | `point.py`; `tests/test_summarize_scale.py`; register C-22 |
| README/version drift; stale `align`/`collapse` prose | **Fixed** | CHANGELOG "Fixed" |
| Central claim untested e2e | **Partly** — in-repo synthetic proxy adapter | `tests/test_proxy_adapter.py` |

Two improvements stand out as *meaningful design wins*, not just fixes: (a) the cross-
level mapping is now **correct for the real bitemporal case**, with a conformance *law*
guarding it; and (b) the **process itself** — findings registered (the repo now has its
own `reports/technical_risk_register.md`, 22 entries), each fixed behind a commit and a
CHANGELOG line. That review→register→fix→test loop is the strongest signal here.

---

## 4. What is still missing?

- **Consumer-side subsetting (`select`/`subset`) and a frame-level
  `reindex(other) -> Frame`.** Still absent (round-01 item, unaddressed). The index
  returns *positions*; no helper reorders/subsets a frame's `values`. faoapi subsets by
  time/entity/feature on every request; without these, every consumer hand-applies
  indexer arrays — re-creating the duplication the leaf exists to remove. **The single
  biggest remaining consumer-facing gap.**
- **A real external consumer (Epic 3).** The proxy adapter is *synthetic and in-repo* —
  a good step, but the cross-repo value ("one contract, N consumers") is still
  demonstrated by views-frames testing itself, not by pipeline-core/datafactory running
  `assert_frame_contract` against real adapter output. Until one real consumer pins and
  conforms, "stable keystone" is asserted, not proven.
- **`EvaluationFrame`/non-spatiotemporal key protocol; `MetricFrame`.** Still deferred —
  so the reporting C-48 story the README front-loads as motivation remains unaddressable
  in code. Fine as a choice, but it's the one headline use-case with no path yet.
- **A scalable cross-level mapping interface** (see §2): the `Mapping[tuple[int,int],int]`
  shape is correct but not consumer-vectorizable.
- **Interval results as frames** (or a documented reason they aren't): `hdi`/`quantiles`
  return bare arrays while point estimates return frames.
- **Minor:** `Persistable` signature still `str`; `searchsorted` naming; the
  `test_falsification_*` stubs still live in the main suite (regex-over-README — they
  presumably pass now, but they couple CI to prose).

---

## 5. What surprised me this round?

**Good surprises**
- **The fix loop closed end-to-end and *fast*.** Round-01 findings → registered as
  C-19..C-23 → fixed → tested → CHANGELOG, in one release. The cross-level fix in
  particular is exactly the salvage I proposed, ratified and guarded by a conformance
  law. This is the rare repo where a review demonstrably changed the code *and* the
  process recorded why.
- **The `map_estimate` engineering is meticulous.** `_batched_map` reproduces
  `numpy.histogram`'s uniform-bin edges *and* its float-rounding correction
  (`point.py:82-88`) so the row-blocked path is bit-for-bit identical to the v0.2.0
  per-row reference, with a `tracemalloc` guard asserting memory doesn't scale with
  `rows × bins`. That is real numerical care.
- **The quickstart teaches the right pattern** — it ends on `assert_frame_contract`,
  i.e. it shows a consumer how to self-verify, not just how to call.

**Bad / unexpected surprises**
- **The MAP estimator is now a 104-line bespoke replica of numpy's histogram internals**
  — concentrated in the *most decision-critical number* (the MAP FAO sees). It's correct
  and tested today, but it (a) couples correctness to a specific numpy version's binning
  (numpy's histogram fast path has changed across versions within the `>=1.26,<3` range;
  the guard would catch a break, but then someone must re-derive the replica), and (b)
  raises the question of whether *bit-for-bit identity with v0.2.0's `np.histogram`* is a
  real contract or an accidental one a documented tolerance would serve better.
- **The "maximally stable leaf" has shipped three releases (two breaking, `!`) in a day.**
  Entirely appropriate pre-1.0 and pre-consumer — but the *stability* that is the leaf's
  whole identity is still aspirational; it won't be real until the churn settles and a
  consumer pins it.

**Harder than it should be**
- Injecting a full-grid cross-level mapping (you must build a ~10.5M-key Python dict) —
  see §2/§4.

---

## 6. Strongest parts now

1. **The review-responsiveness and governance loop.** Findings registered, fixed,
   tested, changelogged; a per-finding `register C-xx` trail in commits and CHANGELOG.
   This is the most trustworthy thing about the repo.
2. **The cross-level operation is now correct *and* guarded by a law.** Time-aware,
   vectorized, fail-loud, with `assert_cross_level_alignment_law` in the conformance
   suite. The thing that was wrong last round is now a strength.
3. **Executable architecture + conformance, extended.** Import-DAG/one-concept AST tests,
   `np.shares_memory` immutability checks, a `tracemalloc` scale guard, a `type-floor` CI
   job — the guarantees are machine-checked, including the new scale claim.
4. **Onboarding now exists.** `examples/quickstart.py` + `py.typed` + the named type
   aliases make the package genuinely pickup-able by a human or an agent.
5. **Disciplined scope, still held.** No domain data, no pandas, no app logic; statistics
   in the sibling; `MetricFrame`/`EvaluationFrame` kept out.

---

## 7. Weakest parts now

1. **No consumer-side `select`/`reindex(other) -> Frame`.** The top remaining gap for a
   real adopter; forces every consumer to re-implement the apply step. *(architectural)*
2. **Cross-repo value still unproven by a real consumer** — only a synthetic in-repo
   proxy. *(milestone)*
3. **The cross-level mapping interface forces an O(N) Python dict at the caller** — the
   scale fix stops at the leaf boundary. *(interface)*
4. **MAP estimator complexity/fragility** — bespoke numpy-internals replication in the
   most decision-critical estimator, pinned to "bit-for-bit identical." *(maintainability)*
5. **API asymmetry** (point estimates → frames, intervals → bare arrays) and small
   unaddressed nits (`Persistable: str`, `searchsorted` naming, falsification stubs in
   the main suite). *(small)*
6. **`EvaluationFrame`/`MetricFrame` still absent** — the reporting C-48 motivation has
   no code path. *(deferred-by-design, but front-loaded as motivation)*

---

## 8. What should be improved next (prioritized)

### Small fixes (hours)
1. **Make `hdi`/`quantiles` consistent with the point estimators** — either return an
   index-attached object or document the bare-array contract prominently (a faoapi/
   reporting consumer wants the bounds index-aligned without re-attaching by hand).
2. **Align `Persistable.save` to `Path | str`** to match the concretes (still open from
   round 01).
3. **Document the cross-level mapping's build cost** in the docstring, and the
   bit-for-bit MAP contract's coupling to the numpy version (so a future numpy bump knows
   to re-check `test_summarize_scale.py`).
4. **Move the `test_falsification_*` stubs out of the unit suite** into a design-
   conformance lane (or retire them — their decisions are now ADRs), so CI green tracks
   behavior, not README prose.

### Larger / architectural (sequence deliberately)
5. **Add a frame-level `select`/subset and `reindex(other) -> Frame`.** The highest-value
   consumer affordance left; it removes the hand-applied-indexer duplication for every
   consumer (faoapi, reporting). *(Ratify the surface; it's additive, MINOR.)*
6. **Offer a vectorizable cross-level mapping shape** alongside the dict — e.g.
   `cross_level_align_arrays(map_time, map_unit, map_target, target_level)` or an injected
   callable — so a full-grid consumer never materializes a 10.5M-key Python dict.
7. **Prove the contract with one real consumer (Epic 3).** Land the pipeline-core
   `PredictionFrame` re-export shim and have its CI run `assert_frame_contract` +
   `assert_cross_level_alignment_law` against real output. This converts "hardened" into
   "demonstrated" and is the most valuable next milestone.
8. **Revisit the bit-for-bit MAP requirement.** Decide whether exact reproduction of
   v0.2.0's `np.histogram` MAP is a true contract; if not, a simpler vectorized binner
   with a documented float32 tolerance would shed the numpy-internals replication risk in
   the most decision-critical estimator.
9. **Give the deferred `MetricFrame`/key-protocol a dated decision** (generalize the index
   to a non-spatiotemporal key in a v2, or assign `MetricFrame` to views-evaluation and
   say so), since the README leans on the reporting C-48 cure as motivation.

---

## Appendix — what I inspected & verification

- **Read this session:** `src/views_frames/index.py` (cross-level + uniqueness sections,
  in full); `src/views_frames_summarize/point.py` (in full); `examples/quickstart.py`,
  `src/views_frames/protocols.py`, `src/views_frames/_typing.py` (in full).
- **Mapped via `git log` / CHANGELOG / greps / test inventory:** the v0.1→0.2→0.3 commit
  history; `pyproject.toml` (`v0.3.0`, `requires-python >=3.10`); the 15 test files (incl.
  the new `test_proxy_adapter.py`, `test_summarize_scale.py`); `reports/
  technical_risk_register.md` (22 entries, incl. the round-01 findings C-19..C-23);
  presence of `py.typed`, `examples/quickstart.py`, the `type-floor` CI job.
- **Not executed this session:** the test suite / type checker (read-only). Claimed
  results (bit-for-bit MAP fidelity, the `tracemalloc` memory guard) are taken from the
  code + CHANGELOG and flagged as such.
- **No changes made:** no source altered, nothing staged, no commit, no branch created or
  switched. The only filesystem write is this report at
  `perspectives/round02/views-faoapi_review.md`.
