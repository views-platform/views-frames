# Research org — coherent nested HDI tower for VIEWS conflict posteriors

## Objective
Find an estimator that turns ~1024 pooled posterior draws (per cell) into a
**dashboard summary** that is *internally coherent*:

- a **nested-by-construction tower of HDIs** at masses `(0.10, 0.50, 0.90)` — the
  narrower interval is ALWAYS inside the wider one (no post-hoc repair),
- a **point estimate** = the median of the draws inside the narrowest (10%) HDI
  (the centre of the densest region — coherent with the tower by construction),
- a **low** (≈0) and a **high** (~0.99 quantile).

Minimise the composite `score` (lower is better) printed by `run_eval.py`.

This is a **summarisation** task for a dashboard — NOT forecast evaluation. There
is no CRPS / real-outcome scoring here (that is a separate job). The metric only
measures whether the *tower itself* is good (nested, holds the right mass, tight,
stable) against synthetic distributions whose truth we control.

## What you may edit
**ONLY `research/map_hdi/estimator.py`** — the `summarize(samples, masses)` function.
Keep its return contract exactly: `{"tower": [(lo,hi),...], "point": float, "low": float, "high": float}`.

## What you may NOT touch (immutable harness)
`research/map_hdi/benchmark/` (battery, metric, baselines) and `run_eval.py`.
Changing the metric or the benchmark is cheating — the whole point is a fixed bar.

## Hard constraint (feasibility gate)
The tower **must** be nested for every cell. A violation makes the score blow up
(`1e6 + violations`). Build nesting in by construction; never rely on the metric
to forgive it.

## Candidate routes to try (greedy, one at a time)
1. **Constrained nested shortest-intervals** (current `estimator.py`): innermost =
   shortest interval of that mass; each wider = shortest interval *subject to
   containing the previous one*. Sample-native, deterministic.
2. **Density level-sets / HDR** (Hyndman 1996): `scipy.stats.gaussian_kde` (or a
   zero-inflation-aware density); `HDI_α = {x : f(x) ≥ c_α}` — nested by
   construction. Handle the atom at 0 and the disjoint (multimodal) case by
   reporting the outer bounds. The point becomes the centre of the top level set.
3. Tune the bandwidth / the narrow-HDI fraction / the level-set thresholding.

## Discipline
- **Deterministic estimator**: no RNG inside `summarize` (the harness owns all
  randomness, e.g. the stability bootstrap). A non-deterministic estimator makes
  keep/discard meaningless.
- **Beat the baselines**: `run_eval.py` prints the incumbent baselines
  (histogram-MAP + independent-shortest-with-move-to-nest). If you cannot beat
  them out-of-the-box, that result is itself worth keeping (register it).
- **Prefer simpler.** A marginal gain that adds real complexity → discard.
- Keep it reasonably vectorised; this graduates into `views_frames_summarize`
  only after it wins, via a SemVer-gated PR (register C-32 / C-33, issue #89).
