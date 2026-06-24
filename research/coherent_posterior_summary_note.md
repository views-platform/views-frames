# Research note — a tiny, reproducible, distribution-agnostic posterior summarizer: the constrained-nested HDI tower

**Status:** working note (v1.3.0). Seed material for (a) an FAO prerelease/release note and
(b) a short methods article. Ships in `development` as documentation; not version-gated.
**Scope:** the `views_frames_summarize` tower estimators — `tower_point`, `hdi_tower`,
`bimodality`, `summarize_tower`.
**Primary references:** ADR-019 (the decision), `docs/CICs/Summarize.md` (the contract),
register C-32/C-33/C-34/C-44/C-45, issue #89, the research lab `research/map_hdi/` (evidence;
see `research/map_hdi/NOTE.md` for the C-32/C-33-era trail this note supersedes).

---

## Abstract

Operational forecasting systems must collapse a *posterior sample* into a small set of
published numbers — a point estimate and a few credible intervals — per cell, at grid scale.
For the VIEWS conflict-forecasting pipeline serving the UN FAO, each cell is a **~32-draw
posterior of a count** that is **zero-inflated, right-skewed, low-sample, and occasionally
multimodal**. We describe a small, fully-tested estimator that summarizes such posteriors
**coherently** (intervals nested by construction), **reproducibly** (an interval at a given
credible mass does not depend on which other masses are requested), **robustly** (immune to a
pathology where a few coincident draws capture the estimate), and **distribution-agnostically**
(no assumption about the scale or domain of the values). The construction — a *constrained-
nested HDI tower over a fixed canonical mass grid, built outside-in, with a mass-aware tip* — is
deliberately tiny (numpy-only, a few hundred lines) and lives at the root of the platform's
dependency DAG as an immutable data-contract leaf. The contribution is engineering, not
statistics: a robust, reproducible default that an operational system can trust without tuning.

## 1. Problem setting

The estimand is the *mode* and a family of *highest-density intervals (HDIs)* of a posterior we
observe only through a handful of draws. Three features make the standard tools misbehave:

1. **Zero-inflation.** A large fraction of cells are "no event" — a spike of exact zeros plus,
   sometimes, a small positive body. Naïve summaries either collapse the body or over-report it.
2. **Right skew and low sample size (~32).** A fixed-bin histogram mode is *biased and
   non-convergent* at this sample size: the bin count cannot shrink with `n`, and the argmax
   tie-break introduces a directional artifact (register **C-32**).
3. **Coherence and reproducibility requirements.** Consumers publish *several* masses
   (e.g. 50/90/95%). Computed independently, shortest-interval HDIs need not nest, and a
   post-hoc "patch to nest" makes a given band depend on which others were requested — so "the
   50% HDI" is path-dependent (register **C-33**).

The estimator lives in a **domain-agnostic data-contract leaf** (ADR-001/002): numpy-only,
depends on nothing internal, carries no scale metadata, and may *not* embed domain knowledge —
domain facts are injected by consumers, never inferred from values (ADR-003, ADR-014). This
constraint is central: the leaf must summarize counts, rates, probabilities, and continuous
targets identically, because the frame it summarizes is deliberately scale-free (ADR-012/013).

## 2. The incumbents and their failure modes

The prior art (faoapi's `PosteriorDistributionAnalyzer`; the same class in views-reporting):

- **Patched-to-nest HDIs** — `expand-to-contain` + `shift-to-cover-MAP`, an ad-hoc "move the
  least distance" repair, computed only at the requested masses → **path-dependent** (C-33).
- **A histogram-mode MAP** — fixed bins + lowest-index argmax → **toward-zero bias** on the
  skewed/zero-inflated/low-`n` regime (C-32; measured ~21% of active cells diverging
  one-directionally on the production cache).

Two further pathologies were discovered *in our own first designs* and are the heart of this
note's contribution, because the fixes are what make the method robust and agnostic:

- **Degenerate-tip collapse (C-44).** A narrowest floor holding ~2 samples makes "shortest
  interval" = "the two closest draws"; *any* duplicated value (two exact zeros, distance 0) is
  unbeatably closest and, under an inside-out construction, becomes the tower's foundation —
  collapsing the point *and* all nested bands. The trigger is any duplicate, at any value.
- **Magnitude-zeroing (C-45).** A `max(draws) <= 1` "quiet row" rule is a count-domain
  assumption: it zeroes *every* cell of a `[0,1]` rate/probability target and silently erases
  low-intensity counts. Incoherent for a domain-agnostic leaf (violates ADR-003/ADR-014).

## 3. The method

The estimator is a **canonical tower** plus three read-outs. All four public functions share one
private engine (`_dense_tower`, `_median_in`, `_pin`, `_zero_mask`).

### 3.1 A fixed canonical mass grid, with *pinning* (reproducibility)

A fixed grid of credible masses `G` (a 5% body `0.05…0.90` plus a fine high-mass tail
`0.92,0.94,0.95,0.96,0.97,0.98,0.99`), built from rounded literals (never `np.arange`, whose
float drift is not bit-reproducible across numpy versions — register C-24). The tower is *always*
built on the full `G`; a requested mass `m` is **pinned** to its nearest grid floor and *read
out*, never *inserted* into the construction. Consequence (the **reproducibility law**): the
interval at mass `m` is a function of the data and `G` alone — identical regardless of which
other masses a caller requests.

### 3.2 Outside-in constrained-nested construction (coherence + robustness)

The tower is built **outside-in**: the widest floor (≈0.99) is the unconstrained shortest
interval holding its sample count; then each *narrower* floor is the shortest interval **contained
in its wider parent**. This gives two guarantees at once:

- **Nesting by construction** (resolves C-33): each floor ⊆ its parent, no post-hoc patch.
- **Robustness to minority duplicates** (resolves C-44): the well-determined wide floors land on
  the dense body and *shed* lonely outliers (a 2-draw spike cannot fill a wide floor); the
  containment constraint then *forbids* a narrower floor from re-selecting an outlier window. A
  containing window always exists (the parent's own first `k+1` samples qualify), so the
  construction is provably total — no defensive fallback needed.

A `k <= 0` floor (too few samples to hold two draws, at small `S`) collapses to a real *sample*
(the in-parent middle draw), keeping the contiguous-run invariant that the read-outs rely on.

### 3.3 A mass-aware tip — the *shorth* (robust mode, distribution-agnostic zero handling)

The point estimate is the **median of the floor at a configurable `tip_mass`** (default `0.5` —
the *shorth*, the shortest-half mode), **not** the degenerate narrowest floor. Two properties
follow:

- **Robustness.** A duplicate would have to fill ~half the draws to capture a 50%-mass floor —
  so a minority spike cannot move the tip (the C-44 cure, made a *definition* rather than a patch).
- **Distribution-agnostic zero handling (the C-45 result).** The shorth *already* reads 0 when
  the zero atom dominates the central mass and the body mode otherwise — for *any* distribution.
  No magnitude rule is needed; we removed the `max <= 1` default entirely. A count consumer that
  wants an explicit "sub-1 ⇒ 0" policy sets an **optional, off-by-default** `zero_cutoff` (read
  live from config); the modeling choice is the consumer's, not a leaf default.

### 3.4 Bimodality flag (surface ambiguity, don't collapse it)

A deliberately conservative 0/1 flag (`bimodality`) marks rows where a single point / shortest
interval is inherently ambiguous (a zero atom plus a distinct bump, or two separated bumps).
Tuned for **zero false positives** on the normal regime at the cost of recall (register C-34) —
its job is to catch a future regime change that produces *clearly* separated modes, not to
adjudicate every heavy tail. A `0` means "no clear bimodality detected," **not** "proven
unimodal."

### 3.5 Fail-loud configuration (no silent defaults)

All tunables (the grid, `tip_mass`, the optional `zero_cutoff`, the bimodality thresholds, the
row-block) live in a single `config.TOWER_CONFIG` dict with **no silent defaults**: a missing
key raises `ValueError` naming it (ADR-008/ADR-009). Knobs are read **live** (not snapshotted at
import), so the optional `zero_cutoff` is genuinely runtime-configurable.

## 4. Guarantees (as executable conformance laws)

The contract is enforced by the conformance suite (`views_frames_summarize.conformance`; see the
Summarize CIC §3/§10) and a 100%-line+branch test gate:

| Law | Statement |
|---|---|
| **Nesting** | across the canonical floors, lower bounds are non-increasing and upper bounds non-decreasing (each floor ⊆ its parent). |
| **Reproducibility** | `hdi_tower(frame, (0.5,))` equals the 50% column of `hdi_tower(frame, (0.5, 0.9, …))` — a mass's interval is independent of co-requested masses. |
| **Tip-in-`tip_mass`-floor** | `tower_point` lies inside the `tip_mass` floor (it is that floor's median). |
| **Bundle == trio** | `summarize_tower` is provably equal to `(tower_point, hdi_tower, bimodality)` from one sort. |
| **Distribution-agnostic** | with the default config, no magnitude-based zeroing occurs; a `[0,1]`/probability field is not collapsed to zeros. |
| **Fail-loud config** | a missing tower-config key raises, naming it; the optional `zero_cutoff` is read live. |

Memory is bounded (one sort per row-block, never a whole-grid sorted copy — C-22/C-25), and the
construction is deterministic across numpy versions (leftmost tie-breaks; rounded-literal grid).

## 5. What an FAO/consumer adopter must know (release-note seed)

- **The point estimate is the robust dense mode.** On right-skewed / zero-inflated / multi-cluster
  cells it returns the *densest* mode, which is often **much lower** than a histogram MAP that
  lands on a sparse high bin. That downward disagreement is largely the **C-32 histogram bias
  being corrected**, not an error — but it is a real, visible semantic shift; validate it on your
  data before swapping an incumbent MAP.
- **No zeroing by default; opt in for counts.** The leaf does no magnitude zeroing. A count target
  that should report "sub-1 ⇒ 0" sets `config['zero_cutoff']` to a float, *or* applies its own
  zero-fraction (`mass_at_zero`) policy downstream. Rate/probability/continuous targets need no
  config.
- **`hdi_tower` is a coherent *nested* band, not the unconstrained shortest interval.** The
  nesting cascade can shift a band's *location* (≈ up to ~20% of its width on skewed data; width
  near-identical) off the bare shortest HDI. For the exact single-mass shortest interval, use the
  frozen `hdi`; use the tower when you need a coherent, reproducible *family* of bands.
- **Pair the point with the `bimodality` flag.** A `1` means "treat the single point with care";
  a `0` is conservative, not a guarantee of unimodality (C-34).

## 6. Engineering context (why it is a leaf, and why that matters)

The estimator is intentionally **small and immutable**, at the **root of the platform DAG**:
numpy-only, no IO, no domain data, no scoring/reconciliation (ADR-017 charter). It is published as
one PyPI package (`views-frames`) shipping both `views_frames` and `views_frames_summarize`. The
v1.0 public surface is **frozen** (ADR-018); the tower is purely *additive* surface, and the
**conformance floor** (ADR-016) — the version a consumer can rely on — stayed `1.0.0` across all
of this work, because nothing in the published structural contract changed. This is the discipline
that let four releases (1.1.0 → 1.3.0) ship in rapid succession without breaking any consumer.

The lesson worth generalizing: in a domain-agnostic transport layer, **robustness and
distribution-agnosticism are the same property**. Both production bugs (C-44, C-45) were a
domain/scale assumption smuggled into the leaf — a degenerate 2-sample floor (an implicit "the
mode is the tightest pair") and a magic `1.0` (an implicit "values are counts"). Removing each
assumption made the estimator simultaneously more correct *and* smaller.

## 7. Reproducibility and evidence

- **Lab:** `research/map_hdi/` — an immutable synthetic battery (`benchmark/`) of conflict-shaped
  posteriors with known *analytic* modes, plus `point_pass.py` (the tip ties/beats the incumbent
  against a *non-circular* oracle at production `n`), `density_sweep.py` (HDI floors are
  density-stable on unimodal/zero cells, unstable only on bimodals → "5% body is enough; flag
  bimodals"), and `NOTE.md` (the original C-32/C-33 trail).
- **Tests:** `tests/test_summarize_tower.py` + `tests/test_summarize_config.py` — the C-44 truth
  table (A–L) and real faoapi cells; the distribution-agnostic matrix (beta/uniform/normal/
  lognormal/low-count); scale-consistency; vectorized==scalar; opt-in regression parity; 100%
  line+branch.
- **Governance:** ADR-019 (with the C-44/C-45 amendments), the Summarize CIC, register
  C-32/C-33/C-34/C-44/C-45. The convergent-mode question remains open as **#89**.

## 8. Pointers for downstream assembly

- **FAO prerelease/release note** → §5 (adopter-facing) + §1 (problem) + a CHANGELOG diff of the
  relevant version(s). Lead with the semantic shift (robust dense mode vs histogram MAP) and the
  opt-in zero policy.
- **Methods article (arXiv)** → §1–§4 + §6–§7. Framing: *a tiny, reproducible, distribution-
  agnostic posterior summarizer for operational forecasting* — the contribution is the
  outside-in constrained-nested tower (coherence + duplicate-robustness in one construction) and
  the observation that a mass-aware tip makes magnitude-based zero rules unnecessary, i.e. that in
  a domain-agnostic layer robustness and scale-agnosticism coincide. Related work to situate
  against: the *shorth*/half-sample mode and shortest-interval (HDI) estimators; nonparametric
  mode estimation at low `n`; zero-inflated count modeling. Honest limitations: the conservative
  bimodality recall (C-34); the nesting-vs-shortest-HDI location trade-off (§5); no convergence
  guarantee for the mode at fixed `tip_mass` (#89).
