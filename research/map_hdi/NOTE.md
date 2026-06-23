# Research note — coherent posterior summary (HDI tower + tower-tip point + bimodality flag)

This note records what the `map_hdi` lab found and the decision it led to (ADR-019,
register C-32/C-33, issue #89). It is the evidence trail behind graduating the
constrained-nested HDI tower into `views_frames_summarize`.

## The problem

Two consumers (faoapi's `PosteriorDistributionAnalyzer`; reporting's same-named class,
which already delegates to `views_frames_summarize`) summarize conflict posteriors with:

1. **Independent shortest-interval HDIs, patched afterward to nest** (`_enforce_hdi_structure`:
   expand each wider band to contain the narrower + shift to cover the MAP). The patch is
   an ad-hoc "move the least distance" repair, and because only the *requested* masses are
   computed, "the 50% HDI" is **path-dependent** — it changes with which other masses you
   ask for. Not reproducible.
2. **A histogram-mode MAP** with a lowest-index tie-break that is directionally biased
   toward zero on right-skewed, zero-inflated, low-sample posteriors (C-32).

## The solution

A **constrained-nested HDI tower** over a **fixed canonical mass grid** (5% body + fine
tail to 0.99), built inside-out so each floor is the shortest interval *containing* the
next-narrower one — nested **by construction**, no patch. Requested masses are **pinned**
to the grid, never inserted, so a mass's interval is independent of the other requested
masses (reproducible). The point is the **tower tip** (median of the narrowest floor,
unbinned → no tie-break bias). A separate **bimodality flag** marks the rows where a
single point / shortest interval is inherently ambiguous.

## The evidence

The harness (`benchmark/`, immutable) is a 108-cell battery spanning the VIEWS conflict
shape: zero-mode-dominant families (zi_lognormal, zi_gamma, heavy, bimodal) and non-zero
active families (active_gamma/lognormal/weibull, low_zi_active, bimodal_active) whose
**analytic** mode is known by construction.

- **`point_pass.py` — the tower tip is at least as good as the incumbent, and the metric's
  own oracle is circular.** The battery's stored `true_mode` is a histogram argmax, so the
  histogram `map_estimate` matches it partly by sharing its binning. Scored against the
  *analytic* mode instead (non-circular), the incumbent's edge shrinks or reverses: on
  clean active cells at n=1024 the tower tip ties/beats it (gamma 0.13 vs 0.16, lognormal
  0.11 vs 0.14; weibull goes the other way). On `low_zi_active` the histogram oracle
  *hides* a large `map_estimate` failure (0.24 circular vs 0.82–1.07 analytic) — the same
  cells where the C-32 bias bites.
- **`density_sweep.py` + per-cell diagnostics — density barely matters where the answer is
  well-defined; multimodality is the real ambiguity.** HDI floors are density-stable on
  unimodal and zero cells (so a 5% body is plenty), but on genuinely bimodal cells the
  shortest 50% interval *flips* between the two modes and does **not** settle even at
  0.25%. No grid density resolves this — it is a property of shortest-interval HDIs on a
  multimodal posterior. Hence: flag bimodality, don't try to smooth it away.
- **`timing.py` — the dense tower is cheap.** Vectorized over the sample axis with the
  zero short-circuit (which kills the ~99% quiet cells), the full canonical tower scales
  to the grid; 5% is comfortably within budget.

## The decision

Graduate the tower + tower-tip point + bimodality flag into `views_frames_summarize` as
**additive** surface (MINOR under the v1.0.0 freeze, ADR-018): `hdi_tower`, `tower_point`,
`bimodality`, and the single-pass `summarize_tower` bundle. This **resolves C-33** (a
guaranteed-nested, reproducible, multi-mass tower) and **mitigates C-32** (a non-binned,
directionally-unbiased point). It does **not** claim a fully-consistent convergent mode —
the tower tip uses a fixed 5% smoothing, and "the most likely single value" is only
well-defined for unimodal posteriors (the reason for the flag). A fully-principled
convergent mode remains **#89**.

## What this lab is / isn't

`research/map_hdi/` is un-gated lab code (tracked; generated artifacts gitignored). The
`benchmark/` harness and `run_eval.py` are an immutable eval; `estimator.py` was the
autoresearch sandbox. The production code now lives in `src/views_frames_summarize/` and
is the source of truth; this lab is the evidence behind it, retained for reproducibility.
