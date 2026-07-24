# Research note — the tower figures (PRN06 provenance, method, and where plotting lives)

This note records what the two published tower figures show, exactly how they were made,
how they were nearly lost, and the placement decision for figure tooling in this repo.

## The figures

FAO Project 02 **Pre-Release Note 06** (2026-06-24) embeds two figures:

- **`tower_overlay`** — "The HDI tower over the empirical forecast distribution
  (synthetic, n = 2000)": a 2×2 zoo (right-skewed, near-symmetric, zero-inflated,
  bimodal), each panel a grey histogram with the full 25-floor nested HDI tower in blue
  and the tower-tip MAP as a red dashed line. Tips: 1.28 / 5.89 / 0.00 / 2.56 [bimodal
  flag].
- **`tower_detail`** — one right-skewed posterior with the full tower and the 50/90/95%
  floors highlighted. Tip: 1.51.

## The method (and a misreading to guard against)

Both figures call the **installed public API directly** — `hdi_tower`, `tower_point`,
`bimodality` — with no bespoke derivation. `tower_point` is (`tower_point.py`):

```python
tower = _dense_tower(srt, ks)                          # outside-in nested tower
tip = _median_in(srt, tower[:, t, 0], tower[:, t, 1])  # median of the tip_mass floor
```

i.e. **the median of the draws inside the `tip_mass` floor of the outside-in tower**.
Since ADR-019 Amendment 3 (2026-07-24), `tip_mass` = **0.25** — the top-quartile floor,
the top floor of the published tower — replacing the original 0.5 ("shorth") default,
whose median carried a structural rightward bias on skewed shapes (evidence:
`research/map_hdi/tip_mass_study.py`; the change also brought the MAP-containment law —
every floor holding more than half the tip floor's draws provably contains the MAP).
It is *not* derived from any central/equal-tailed interval.

**The v1 rendering actively invited that misreading (fixed in v2/v3, 2026-07-24).**
The as-published figures drew credible level *ascending*, which put the widest (99%)
floors at the **top** and the narrow floors at the bottom — an upside-down tower — and
placed the tip marker at level 0.5, i.e. **mid-structure: visually a "tower-middle
MAP"**, directly contradicting the "tower-*tip*" name. v2 inverted the vertical
arrangement (99% base at the bottom, floors narrowing upward) but drew the sub-50%
internal grid as a spire *above* the 50% floor — un-topping the tower and again making
the tip read as mid-structure. **v3 is the correct rendering:** the published tower
**ends at the `tip_mass` floor — its top floor** (50% at the time; **25% since ADR-019
Amendment 3**) — with the MAP marker sitting on it, so "the tower-tip MAP is the median
of the top HDI" is literally what the picture shows. Floors below `tip_mass` are the canonical grid's internal machinery and are not
drawn. (The *narrowest-internal-floor* median — the shrinking-HDI-limit mode — remains
the **deferred #89 redesign**: the tip-mass study showed masses ≤ 0.15 resurrect the
C-44 zero-stack signal loss on real cells, which is what fixed the choice at 0.25.)
A smaller cue inherent to the method remains: on right-skewed shapes the tip-floor
median sits slightly right of the histogram peak (lognormal(0.5, 0.55): analytic mode
≈ 1.22; tip 1.38 on the seed-7 realization). v2/v3 also fixed twin-axis label
collisions between panels, the unreadable 0.92–0.99 floor slab, the endpoint "curtain"
verticals, and the detail figure's annotation collision. The rendering fixes preserved
the published values; the **Amendment 3 method change updated them** (see *Reproduce*).
The "central 50% is path-dependent" defect in `research/map_hdi/NOTE.md` describes the
**pre-C-44 / old-faoapi** behavior the tower *replaced*; these figures postdate that fix
(generated 19 minutes after the v1.3.0 research-note commit `96be471`) and — verified
2026-07-24 — `git diff 96be471..HEAD` over the five tower-family modules is **empty**,
so the published figures match the current (v1.8.x) method byte-for-byte.

## Provenance (and the lesson)

The original generators were **ephemeral scratchpad scripts** run on 2026-06-24
08:00:15 / 08:00:58 CEST (matching the PDFs' embedded CreationDates to the second).
They were never committed anywhere; when their provenance was questioned on 2026-07-24,
no filesystem search could find them — they survived only inside a session transcript,
from which they were recovered verbatim. `make_tower_figs.py` in this directory is that
recovery made permanent (same seeds — overlay 7, detail 3 — same shapes, same styling;
a rerun reproduces the published tip values exactly).

**Lesson:** any figure that lands in a deliverable gets a committed, seeded generator
the same day. Ephemeral plotting scripts are provenance debt.

## Where plotting lives in this repo (the placement decision)

**Figure tooling lives under `research/`, never under `src/`.** Considered and
rejected: a `src/views_frames_plotting` sibling package. Grounds: the sibling charters
exclude plotting explicitly and repeatedly (ADR-017:59, ADR-023:64 + :188
"failure-mode to watch", Summarize CIC §2/§11, Reconcile CIC §2); the wheel is
numpy-only and `pyproject.toml` already rules that matplotlib is "notebook-only …
never imported by the package"; ADR-018 would freeze plot styling — the least stable
kind of code — onto the most frozen release unit (a CCP/SAP inversion); and C-52's
accretion guard names exactly this camel's nose. The native precedent followed instead:
`research/map_hdi/audit*.py`, `notebooks/_synthetic.py`, `scripts/` — dev/research
tooling outside the wheel, matplotlib via the `[docs]` extra.

**Standard output location:** `reports/plots/` (gitignored — generated artifacts stay
out of git; a deliverable's copy travels with the deliverable, as PRN06's correctly
does in its own `figures/`).

**Escalation path (recorded once, to close the question):** if cross-repo demand for
these plots ever materializes, they graduate to a separate *unfrozen* distribution
(the D-11 pattern) or to views-reporting, the platform's presentation layer — never
into this wheel.

## Reproduce

```bash
uv run --extra docs python research/figures/make_tower_figs.py            # both, into reports/plots/
uv run --extra docs python research/figures/make_tower_figs.py --which overlay --figdir /tmp/x
```

Expected (tip_mass = 0.25, ADR-019 Amendment 3): overlay tips `[1.38, 5.94, 0.0, 2.13]`
(4th panel bimodal-flagged), detail tip `1.47`. (The as-published PRN06 v1 figures carried
the pre-amendment 0.5-floor tips `[1.28, 5.89, 0.0, 2.56]` / `1.51`.)

**PRN06 swap status:** the note still embeds the v1 figures (upside-down tower,
pre-amendment 0.5-floor tips); the v1 generators remain recoverable from the session
transcript if ever needed. Once the current figures are approved, copy them into the
note's `figures/` and recompile.
