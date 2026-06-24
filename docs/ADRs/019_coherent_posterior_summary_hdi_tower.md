# ADR-019: Coherent posterior summary — fixed-grid constrained-nested HDI tower

**Status:** Accepted (amended 2026-06-24 — see *Amendments* below)
**Date:** 2026-06-23
**Deciders:** VIEWS platform maintainers
**Consulted:** views-faoapi integration spike (C-32/C-33/C-44/C-45); research lab `research/map_hdi/`
**Informed:** views-reporting, views-faoapi (consumers of `views_frames_summarize`)

> **Amendment 1 (2026-06-24, register C-44).** The original tower was built *inside-out*
> from the degenerate narrowest (5% ≈ 2-sample) floor, which let a **minority duplicated
> draw** (a couple of exact zeros, a lone pair) hijack the foundation and silently collapse
> both the tip and the nested bands — confirmed on real faoapi cells. The tower is now built
> **outside-in** (widest floor first, each narrower floor *contained in* its parent), which
> is robust by construction, and the tip reads the configurable **`tip_mass`** floor (default
> 0.5, the "shorth"), not the 5% floor. All tower-family tunables moved to a fail-loud
> `config.py` (no silent defaults, ADR-009). The sections below are updated in place; the
> *In scope* surface and signatures are otherwise unchanged.
>
> **Amendment 2 (2026-06, register C-45, v1.3.0).** The `max(row) <= 1` raw-count zero
> short-circuit baked a count-domain magnitude assumption into the domain-agnostic leaf
> (it zeroed *every* cell of a rate/probability `[0,1]` target and silently erased
> low-intensity counts). It is **removed as a default**: zero-inflation is handled by the
> `tip_mass`-floor density, and the magnitude rule is now an **optional, off-by-default**
> `config['zero_cutoff']` (read live) for count consumers that want it. The summary family is
> now **distribution-agnostic**. See the *Decided properties* below.

---

## Context

Two consumers summarize conflict-forecast posteriors today, and both are fragile in the
same two ways (register **C-32**, **C-33**; surfaced by the faoapi integration spike):

- **HDIs are computed independently per mass, then patched to nest.** `hdi(frame, mass)`
  returns the empirical shortest interval for one mass and stops. On skewed/multimodal
  empirical samples the shortest 50% interval need not sit inside the shortest 95% one,
  so consumers force a tower **post-hoc** (expand each wider band to contain the
  narrower, plus a MAP-containment shift). The result is no longer the true shortest
  interval and the narrowest band is dragged by the biased mode. And because only the
  *requested* masses are computed, "the 50% HDI" is **path-dependent** — it changes with
  which other masses you ask for, so it is not reproducible.
- **The point estimate is a biased histogram mode.** `map_estimate`'s lowest-index
  tie-break pulls the mode toward zero on right-skewed, zero-inflated, low-sample
  posteriors (C-32). The deeper issue the spike named: a fixed-bin histogram mode is
  neither parametric nor consistently nonparametric — biased *and* non-convergent.

Both C-32 and C-33 independently concluded that the principled fix is **shared**: derive
the whole interval family together so the tower **and** the point fall out
nested-by-construction, exposed as a multi-mass call. This ADR records building exactly
that, and decides where the new surface sits under the v1.0.0 freeze (ADR-018).

The research lab (`research/map_hdi/`) validated the pieces before graduation: against a
*non-circular analytic-mode oracle* (the active families, which have an analytic continuous
mode), the tower tip ties/beats the histogram mode at the **production sample size n=1024**;
at **n=128 the two are mixed** (the tip wins on some families, loses on others) — so the tip
is a mitigation at production `n`, not a guaranteed win at the low-`n` regime where the C-32
bias bites hardest (`point_pass.py`). HDI floors are density-stable on unimodal/zero cells
but inherently unstable on genuinely bimodal ones (`density_sweep.py`) — confirming that no
grid density "fixes" multimodality, so it must be **flagged**, not smoothed away.

---

## Decision

Add a **coherent posterior summary** to `views_frames_summarize`, built on a
constrained-nested HDI tower over a **fixed canonical mass grid**. This is **additive**
new surface (MINOR under ADR-018); the frozen estimators (`map_estimate`, `hdi`,
`quantiles`, `collapse`, `aggregate_distributions*`) are **unchanged**.

**In scope — the new public surface:**

- `hdi_tower(frame, masses) -> (N, …, M, 2)` array. A dense canonical tower (a fixed 5%
  body plus a fine high-mass tail to 0.99) is built **outside-in**: the widest floor is the
  shortest interval holding its mass, then each narrower floor is the shortest interval
  *contained in* its wider parent, so the tower is **nested by construction** (no post-hoc
  patch) **and robust to minority duplicated draws** (register C-44 — a lonely outlier is
  shed by the wide floors and the containment constraint forbids a narrower floor from
  re-selecting it). Requested masses are **pinned** to the nearest canonical floor and read
  out — **never inserted** into the construction. Therefore a mass's interval is
  **independent of the other requested masses** (the reproducibility guarantee that resolves
  C-33).
- `tower_point(frame) -> (N, …, 1)` frame. The "tower tip": the median of the configurable
  **`tip_mass`** floor's samples (default 0.5 — the "shorth"); zero-inflation is read off
  that floor's density (an optional `zero_cutoff` magnitude rule is off by default — C-45).
  Unbinned and median-based, so it carries **none** of `map_estimate`'s
  histogram tie-break bias (mitigates C-32), and — reading a *mass-aware* floor rather than
  the degenerate 2-sample 5% floor — it is robust to minority duplicates (C-44). It is not a
  symmetric/unbiased estimator of the mode — only free of the lowest-index artifact.
- `bimodality(frame) -> (N, …, 1)` array. A deliberately conservative 0/1 flag for
  genuinely multi-peaked rows, where any single point / shortest interval is inherently
  ambiguous.
- `summarize_tower(frame, masses) -> TowerSummary`. A single-pass bundle deriving all
  three from one sort; provably equal to the composable trio.

**Decided properties (the source of truth):**

- **The canonical grid is a fixed config value, not a per-call parameter.** A caller-tunable
  density would let two callers produce different canonical floors and break reproducibility.
  The grid (and the other tower-family tunables: `tip_mass`, the zero cutoff, the bimodality
  thresholds, the row-block) live in `config.TOWER_CONFIG` — a single source of truth with
  **no silent defaults**: a missing key raises `ValueError` naming it (ADR-009). The grid is
  built from rounded literals (not `np.arange`, which drifts ~1 ulp across numpy versions).
  `masses` is the only per-call tunable.
- **Zero-inflation is handled by density, not magnitude** (amended 2026-06, register
  **C-45**). The original `max(row) <= 1` raw-count short-circuit baked a count-domain
  magnitude assumption into the domain-agnostic leaf — it zeroed *every* cell of a
  rate/probability `[0,1]` target and silently erased low-intensity counts. It is
  **removed as a default**: the `tip_mass`-floor density already reads 0 when the zero
  atom dominates and the body mode otherwise, for any distribution. A consumer that wants
  a count-style magnitude rule sets the **optional, off-by-default** `config['zero_cutoff']`
  (a float) — read live, so it is honoured at runtime; the leaf imposes no magnitude
  assumption by default. The modeling choice "should a sub-1 *count* posterior read 0?" is
  the **consumer's**, expressed in that config, not a leaf default.
- **Masses are validated to `(0, 1)`** and fail loud (ADR-008).
- **Bimodality is flagged, never resolved.** No density or point estimator disambiguates
  a genuinely two-peaked posterior; the honest contract is to surface it.

**Out of scope:** changing any frozen estimator; a fully-consistent convergent mode
estimator (still tracked in #89); choosing the point estimate's downstream use (consumers
decide); cross-repo adoption (consumers adopt when ready).

---

## Rationale

- **Coherence-by-construction over post-hoc repair.** Nesting is a structural property;
  deriving the family together makes it an invariant, not a patch with corruption
  (shifted/expanded intervals coupled to a biased mode). This is the resolution both
  C-32 and C-33 prescribed.
- **Reproducibility is a contract, not a nicety.** A fixed grid + pinning makes "the 50%
  HDI" a function of the data alone — essential for a value object at the root of the DAG.
- **Honesty about multimodality.** The research showed the single-most-likely-value is
  only well-defined for unimodal posteriors. Rather than pretend otherwise, we ship a
  conservative flag (zero false positives on the battery's skewed/zero/active families;
  fires only on clearly separated modes). A missed subtle bump is cheaper than crying
  wolf on every skewed tail.
- **Additive under the freeze.** A new function is MINOR (ADR-018); modifying the biased
  `map_estimate` would be a MAJOR break for no gain, since `tower_point` is the better
  path forward and `map_estimate`'s caveat is already documented (CIC §3, C-32).

---

## Considered Alternatives

### Alternative A: keep independent HDIs + the post-hoc nesting patch (the incumbent)
- **Pros:** already exists; minimal new code.
- **Cons:** path-dependent (non-reproducible) "50% HDI"; intervals corrupted by the
  expand-to-nest + MAP-shift; couples the band to the biased mode.
- **Reason for rejection:** it is exactly what C-32/C-33 flagged as fragile.

### Alternative B: caller-tunable grid density (a `density=` parameter)
- **Pros:** flexible; a caller could trade compute for resolution.
- **Cons:** two callers at different densities produce different canonical floors → "the
  50% HDI" is no longer reproducible. Destroys the central guarantee.
- **Reason for rejection:** reproducibility outranks flexibility here. Revisit only if a
  use case needs a *different fixed* grid — which would be a new function, not a parameter.

### Alternative C: a single-bundle-only API (`summarize_tower`, no composable trio)
- **Pros:** smallest surface; always single-pass.
- **Cons:** forces a caller wanting only the point to compute and receive intervals + flag;
  one return mixes a frame with raw arrays, breaking the ADR-017 return conventions.
- **Reason for rejection:** the composable trio (each obeying its ADR-017 convention) plus
  the bundle for the hot path serves both without compromise.

### Alternative D: a fully-consistent convergent mode estimator now
- **Pros:** would close C-32's deeper non-convergence concern.
- **Cons:** needs a distributional assumption (model risk) or an n-adaptive
  smoothing-plus-floor — a larger, SemVer-significant effort.
- **Reason for rejection:** out of scope here; tracked in #89. `tower_point` removes the
  *directional bias* (the acute risk) without that effort.

---

## Consequences

### Positive
- C-33 resolved: a guaranteed-nested, reproducible tower with a multi-mass API.
- C-32's directional bias mitigated: a non-binned, symmetric point estimator.
- Multimodality is surfaced rather than silently collapsed.
- views-reporting gains all of this via its existing delegation to
  `views_frames_summarize`; faoapi can drop its standalone copy when it adopts.

### Negative
- More public surface to maintain and freeze (four names + a NamedTuple).
- The bimodality flag is a heuristic with deliberately limited recall on *ambiguous*
  (overlapping) mixtures, unequal-weight splits, and a tall-narrow mode beside a spread one
  — documented as a conservative trade, not a formal test, and **registered as C-34**.
- `tower_point` reads a fixed `tip_mass` floor (default 50% — the shorth), so it is **not**
  a consistency guarantee to the true mode; a fully-principled convergent mode remains #89.
- `map_estimate` remains in the frozen surface (biased), now with a documented better
  alternative — a residual a naïve consumer can still step on.

---

## Implementation Notes

- Enforced in `src/views_frames_summarize/`: `tower.py` (engine + `hdi_tower`),
  `tower_point.py`, `bimodality.py`, `summarize_tower.py`; re-exported in `__init__.py`.
- Tunables in `config.py` (`TOWER_CONFIG` + `REQUIRED_KEYS` + fail-loud `get`/`validate_config`).
- Conformance: `conformance.py` extended with the nesting / tip-in-`tip_mass`-floor /
  reproducibility / bundle==trio laws (run by `tests/test_conformance.py`).
- Memory-bounded via `block_apply` (register C-22/C-25); numpy-only (import-DAG test).
- Tests: `tests/test_summarize_tower.py` + `tests/test_summarize_config.py`, green/beige/red
  per ADR-005; 100% line+branch coverage gate.
- Follow-up: update the Summarize CIC; reconcile the register (C-33 resolved, C-32
  mitigation note, **C-44** outside-in resolution); CHANGELOG `[1.2.0]`; version bump.

---

## Validation & Monitoring

- **Invariants (asserted in the conformance suite):** every adjacent floor nests; the tip
  lies in the narrowest floor; `hdi_tower(frame, [0.5])` equals the 50% column of
  `hdi_tower(frame, [0.5, 0.9, 0.99])` exactly (reproducibility — the property holds for any
  wider request); the bundle equals the trio.
- **Signals to watch:** if a future model produces genuinely multimodal posteriors, the
  `bimodality` flag rate should rise on those cells — the trigger to revisit the point
  estimate / pursue #89.
- **Failure mode that would trigger reconsideration:** the conservative detector missing a
  *clearly* separated regime change (not just an ambiguous mixture) — tune `prominence` /
  `min_mass` or move to a stronger test.

---

## Open Questions

- A fully-consistent convergent mode (distributional assumption vs n-adaptive smoothing)
  — still #89; `tower_point` is an interim, low-variance, unbiased-in-direction point.
- The bimodality detector's thresholds are battery-tuned; they may need revisiting if the
  real posterior shapes shift (registered as C-34).
- ~~Whether the `research/` lab lands in `development`~~ — **resolved (2026-06-24):** the
  lab landed in `development` (merged via #90), tracked but lint-excluded
  (`pyproject.toml [tool.ruff] extend-exclude = ["research"]`); generated artifacts are
  gitignored. It is the evidence trail for this ADR, retained for reproducibility.

---

## References

- Register **C-32** (`map_estimate` tie-break bias), **C-33** (no nesting guarantee),
  C-24 (tie-break portability), C-22/C-25 (memory bounds).
- ADR-017 (summarize is a sibling package — the charter), ADR-018 (v1.0.0 freeze),
  ADR-008 (explicit failure), ADR-012 (sample-axis convention).
- Issue **#89** (principled mode/HDI estimator).
- Research lab: `research/map_hdi/` — `point_pass.py` (non-circular point evidence),
  `density_sweep.py` (density stability), `timing.py`, `NOTE.md`.
