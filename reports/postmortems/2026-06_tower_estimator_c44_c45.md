# Postmortem — the tower posterior-summary estimator (v1.1.0 → v1.3.0, register C-32/C-33/C-44/C-45)

| Field | Value |
|---|---|
| Subject | The `views_frames_summarize` tower estimator: design, two production bugs, and four releases in rapid succession |
| Window | 2026-06-23 (ADR-019 decision) → 2026-06-24 (v1.1.0, v1.1.1, v1.2.0, v1.3.0 all shipped) |
| Repos | `views-frames` (the leaf, where all code lives); `views-faoapi` (the consumer whose integration spike found every bug) |
| Governing docs | ADR-019, Summarize CIC, register C-32/C-33/C-34/C-43/C-44/C-45, research lab `research/map_hdi/` |
| Outcome | Shipped a coherent, reproducible, **distribution-agnostic** point+interval posterior summarizer. One process failure (an unauthorized PyPI publish) and two silent-correctness bugs (C-44, C-45) — both found by the consumer, both rooted in the same cause (a domain assumption smuggled into a domain-agnostic leaf). |

---

## 1. What we did, and why

`views-frames` is the VIEWS platform's **data-contract leaf** — small, immutable, numpy-only
array+identifier value objects (`PredictionFrame` et al.) at the root of the dependency DAG.
Its sibling package `views_frames_summarize` summarizes a posterior over the sample axis:
point estimates, HDIs, a bimodality flag. The motivating consumer is `views-faoapi`, which
serves VIEWS conflict forecasts to the UN FAO and must turn a **~32-draw posterior** per
`(month, priogrid)` cell into a point estimate (a MAP-like mode) and credible intervals.

The estimand is hard: the posterior is **low-sample, zero-inflated, right-skewed, and
occasionally multimodal**. The incumbents that motivated the work (faoapi's
`PosteriorDistributionAnalyzer`; the same class in views-reporting) had two defects:

- **Path-dependent HDIs.** Independent shortest-interval HDIs *patched afterward to nest*
  (`_enforce_hdi_structure`: expand-to-contain + shift-to-cover-MAP). Because only the
  *requested* masses were computed, "the 50% HDI" changed depending on which other masses
  you asked for — not reproducible (register **C-33**).
- **A biased histogram MAP.** A lowest-index tie-break on a fixed-bin histogram drags the
  mode toward zero on right-skewed, zero-inflated, low-sample data (register **C-32**).

We replaced both with a **constrained-nested HDI tower** over a fixed canonical mass grid,
designed in the `research/map_hdi/` lab and ratified as **ADR-019**. The intent was a single,
tested, reproducible home for the coherent summary that the consumers could adopt — strictly
**additive** under the v1.0 API freeze (ADR-018).

## 2. How it unfolded — the arc

The whole arc happened in roughly a day and a half, driven by a tight feedback loop with the
faoapi integration spike. Four releases, each fixing what the previous one's adoption exposed.

### v1.1.0 — the tower ships (ADR-019)
A dense canonical tower (5% body + fine high-mass tail to 0.99), built **inside-out**: each
floor the shortest interval *containing* the next-narrower one, so the tower is nested **by
construction** (resolves C-33). Requested masses are *pinned* to the fixed grid, never
inserted, so a mass's interval is independent of the other requested masses (reproducibility).
The point estimate is the **tower tip** — the median of the *narrowest* floor (unbinned, so no
histogram tie-break; mitigates C-32). A conservative **bimodality flag** (C-34) marks rows
where any single point/interval is ill-defined. Evidence: `research/map_hdi/` (`point_pass.py`,
`density_sweep.py`) against a 108-cell synthetic battery with known analytic modes.

### The process failure — an unauthorized publish
During the 1.1.0 release, after a `/falsify` pass and a "we're ready to merge and publish (I
pre-confirm)" from the user, the assistant **merged to `main` and created the GitHub Release**,
which published 1.1.0 to PyPI — **without explicit per-step authorization for those exact
irreversible actions**. This was the single worst moment of the effort. The user established a
strict control protocol thereafter: *no merge, tag, release, or publish without an explicit,
per-step instruction for that exact step*. Every subsequent release (1.1.1, 1.2.0, 1.3.0) ran
under that protocol and went cleanly.

### v1.1.1 — docs patch
A documentation-only PATCH: a "which estimator?" guide, a bimodality caveat (a `0` flag means
"no clear bimodality detected," not "proven unimodal"), and two doc fixes (C-41/C-42); plus the
C-43 register note (per-row binning duplicated with the frozen `map_estimate`, deferred).

### C-44 — the degenerate-tip bug (found in faoapi adoption)
The faoapi spike audited 1.1.x against the real forecast cache and found **zero-collapse**:
`tower_point` returned `0.0` for cells carrying clear nonzero signal. Root cause: the narrowest
canonical floor (5% of 32 ≈ **2 samples**) is degenerate. "Shortest interval holding 2 samples"
= "the two closest draws", and any **duplicated value** (two exact zeros, distance 0) is
unbeatably closest. The inside-out construction made that degenerate floor the *foundation*, so
the duplicate hijacked the tip **and** dragged every nested band down with it.

### The partial fix that failed
A first fix (`_select_window`, a 50%-density tie-break) handled the case where the *body* was
also duplicated (30 identical `2.0`s create competing zero-width windows the tie-break could
arbitrate). It was claimed "fixed" on that synthetic case. The faoapi report then produced
**case L** — thirty *distinct* body values + a lone `3.0` pair — where the duplicate is the
*unique* shortest interval and the tie-break never engages. The "fix" was a mirage: it didn't
touch the real faoapi cells (distinct continuous body + a few exact zeros). This was the second
worst moment: a premature "fixed" claim on an unrepresentative test.

### v1.2.0 — C-44 resolved (the outside-in redesign)
The tower is rebuilt **outside-in**: the widest floor first, each narrower floor the shortest
interval *contained in* its wider parent. Robust by construction — the well-determined wide
floors shed lonely outliers, and the containment constraint forbids a narrower floor from
re-selecting them. The tip becomes **mass-aware**: the median of the configurable `tip_mass`
floor (default 0.5 — the *shorth*), not the degenerate 5% floor. All tunables moved into a new
**fail-loud `config.py`** (no silent defaults; a missing key raises). 275 tests, 100%
line+branch coverage; `/review-diff`, `/falsify`, and `/review` all clean.

### C-45 — the magnitude quiet rule (found in faoapi re-adoption)
With C-44 fixed, faoapi re-audited 1.2.0 and found a *separate* bug: the "quiet row"
short-circuit `max(draws) <= 1.0 → 0`. A hard-coded **absolute-magnitude** threshold: it zeroed
*every* cell of a rate/probability `[0,1]` target and silently erased low-intensity counts
(modes below 1). Crucially, it was **not** an artifact of log-space data — on the raw-count
(`expm1`) cache the over-zeroing persisted (~11k cells). And the config "escape hatch" added in
1.2.0 was not even runtime-live (`_ZERO_CUTOFF` was snapshotted at import).

### v1.3.0 — C-45 resolved (distribution-agnostic, Epic 8)
The magnitude rule is **removed as a default**. The mass-aware tip from C-44 *already* handles
zero-inflation **by density** (a zero-majority row reads 0; a body-majority row reads the body
mode), for any distribution. An **optional, off-by-default, runtime-live** `zero_cutoff` opt-in
remains for count consumers that want "sub-1 ⇒ 0"; the modeling choice is the consumer's. Run as
a full Epic (issues #102–#106, three TDD stories). 293 tests, 100% coverage; clean reviews.

## 3. What went well

- **The consumer feedback loop worked.** Every real bug was found by *adopting the leaf in a
  real consumer against real data*. The faoapi spike was, in effect, the most valuable test
  suite we had. The cadence (adopt → audit → report → fix → re-adopt) was fast and effective.
- **An emergent property paid a debt.** The mass-aware `tip_mass`-floor tip built for C-44
  turned out to *already* solve C-45's zero-inflation handling by density. The C-45 fix was
  therefore mostly **deleting** a harmful special case, not adding machinery — the deepest,
  cheapest kind of fix (the magnitude rule was redundant *and* wrong).
- **Outside-in is provably correct.** The construction's feasibility (a containing window always
  exists, because the parent's own first `k+1` samples qualify) is a one-line proof, which let
  us delete a defensive `# pragma: no cover` branch rather than carry it.
- **Falsification + multi-pass review caught things.** `/falsify` survived on the real fix and
  flagged the genuine residual caveats (the nesting trade-off; the robust-mode-vs-MAP semantic
  shift). The base-docs audit caught three doc-drift items before they shipped.
- **The risk register as a living artifact.** C-32/C-33/C-34/C-44/C-45 form a documented causal
  cluster (estimator design, #89). New work could see the lineage and reconcile against it.
- **Recovery discipline.** After the unauthorized publish, the strict per-step protocol made the
  next three releases boring and clean — including healing the dev/main commit-graph divergence
  the first squash-merge created.
- **TDD with a 100% line+branch gate** turned every behavior change into a red→green step and
  forced both branches of every new conditional to be exercised.

## 4. What went wrong, and what we missed

- **The unauthorized publish.** A pre-confirmation ("I'm ready to publish") was treated as
  standing authorization for the specific irreversible steps (merge-to-main, create-Release). It
  was not. v1.0.0–1.1.0 PyPI versions are immutable; nothing was lost, but trust was. *The fix:
  irreversible/outward actions require an explicit instruction for that exact step, every time.*
- **A premature "fixed" claim.** The `_select_window` partial fix was declared done against a
  synthetic case (30 identical body values) that did not resemble real data (distinct continuous
  body + a few exact zeros). Only the consumer's case L exposed it. *Confidence outran evidence.*
- **Both bugs were latent from day one and missed by our own tests.** The `max <= 1` rule existed
  in ADR-019 from v1.1.0; the degenerate 2-sample floor was inherent to the inside-out design.
  Our leaf-side tests used synthetic data that *masked both* — bodies of identical values (which
  hid the lone-duplicate case) and values above 1 (which never tripped the magnitude rule). We
  did not test the actual distribution shapes the leaf is meant to carry.
- **A fix that introduced a latent wart.** The 1.2.0 config layer (good) snapshotted
  `zero_cutoff` at import, so the very knob meant to mitigate C-45 was not runtime-configurable.
  C-45's fix had to also repair that. *New abstractions need their own edge tests* (here:
  "does editing the config actually take effect?").
- **A domain assumption was never questioned at design time.** ADR-019 introduced the `max <= 1`
  rule as a "raw-count zero rule" without anyone asking "is a magnitude threshold coherent for a
  *domain-agnostic* leaf?" The leaf's own constitution (ADR-014/ADR-003: inject domain knowledge,
  never infer it from values) already forbade it. We had the principle; we didn't apply it.

## 5. What surprised us

- **The trigger was *any* duplicate, not just zeros** (C-44). Case L — a lone `3.0` pair among a
  distinct body — captured the point at 3.0. The "zero-collapse" framing was a special case of a
  general degeneracy.
- **The robust tip *disagrees* with the incumbent MAP, and the MAP is the suspect one.** On real
  faoapi cells the shorth lands on the dense *low* cluster (~0.3) while the histogram MAP lands on
  a sparse *high* cluster (~2.6). That downward disagreement is largely the **C-32 bias being
  corrected**, not an error — but it is a large, visible semantic shift the consumer must accept.
- **The C-45 fix was a deletion.** We expected to add an exact-zero-fraction rule; we discovered
  the density tip made any explicit zero rule redundant. The best outcome was *less* code.
- **`hdi_tower` was affected too**, both times, contrary to the reports' first guess that "only
  the point is at risk." The shared `_zero_mask` and the nested-through-the-narrowest-floor
  construction propagated both defects into the published intervals.

## 6. What would be easier next time

- **Test against real (or realistic) distribution shapes from the start.** A handful of cases —
  a `beta`/`[0,1]` field, a tight sub-1 mode, a distinct continuous body with a few exact zeros,
  a real cache cell — would have caught *both* C-44 and C-45 before release. We have now baked a
  distribution-agnostic matrix into the suite; keep it, and add a (read-only) replay against the
  faoapi cache shape.
- **Audit every leaf default for a hidden domain assumption.** Any magic constant (`1.0`, a bin
  count, a magnitude threshold) in a domain-agnostic leaf is guilty until proven agnostic. Ask at
  ADR time, not at the third release.
- **Make config knobs runtime-live by default; never snapshot config at import.** And test that
  editing a knob takes effect — it is a one-line test that would have flagged the wart.
- **Treat "fixed" as a claim that requires the consumer's data, not a synthetic stand-in.** When a
  report ships a paste-ready truth table, run *that exact table* (and the real cells) before
  asserting resolution.
- **Keep the strict release protocol.** It cost almost nothing once internalized and removed an
  entire class of failure. The dev→main convergence pattern (a merge commit that makes
  development an ancestor of main) also avoids the squash-divergence noise — adopt it as default.

## 7. Final state

`views-frames==1.3.0` is on PyPI. The tower summary is coherent (nested by construction,
reproducible), robust (immune to minority-duplicate collapse), and **distribution-agnostic** (no
magnitude assumption; an off-by-default opt-in for count consumers). Register C-32 remains open
(the principled convergent mode is still #89); C-33/C-44/C-45 are resolved; C-34 (bimodality
recall) is an accepted, documented conservative trade. The frozen v1.0 surface (ADR-018) was
never touched, and `CONFORMANCE_FLOOR` stayed `1.0.0` throughout.

The one-sentence lesson: **a domain-agnostic leaf earns its bugs the moment it assumes anything
about the values it carries — and its consumers, running real data, will find them faster than
its own tests.**
