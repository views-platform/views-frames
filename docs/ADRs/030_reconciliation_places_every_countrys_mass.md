# ADR-030: Reconciliation places every country's mass — donor fill for empty-grid draws (3.0.0)

**Status:** Accepted (ratified by the maintainer 2026-11-01, #287)
**Date:** 2026-10-31
**Deciders:** VIEWS platform maintainers
**Consulted:** views-pipeline-core (views-pipeline-core#579), views-models (the 2026-10-30 `chrome_box` run)
**Informed:** views-pipeline-core, views-models

---

## Context

`views_frames_reconcile` makes a grid (`pgm`) forecast agree with a country (`cm`) forecast:
for every `(time, country)` and every draw, it scales the country's grid cells so they sum to
the country's value for that draw (`reconcile_proportional`, ADR-023).

Scaling is multiplication, so there is one thing it cannot do. **If every cell in a country
is zero in a draw, no multiplier produces a positive total.** Until 3.0.0 those draws stayed
at zero and the country's fatalities were simply missing from the grid. Nothing reported it.
The contract called this "an edge, not a failure" (`docs/CICs/Reconcile.md` §6), and the
published conformance check required it.

The first production run measured the cost (`chrome_crate` → `chrome_box`, 2026-10-30;
64,742 cells × 36 months × 1,024 draws; views-frames#283):

| target | fatality mass lost | draws affected |
|---|---|---|
| `lr_sb_best` | 4.023% | 164,429 |
| `lr_ns_best` | 7.321% | 188,481 |
| `lr_os_best` | 2.943% | 193,903 |

The scaling was otherwise exact: 0 failures across 22.3M `(country, month, draw)` triples.
All of the loss is this one case. pipeline-core neither causes nor hides it
(views-pipeline-core#579). The test suites in both repositories were green because no fixture
ever produced the case.

This matters now because that forecast is bound for a UN partner, and because reconciliation
has just started being used. Changing it costs the least today.

---

## Decision

**1. The country forecast is the authority.** This is a premise, adopted by decision, not a
finding. Nobody has yet shown empirically that the country totals are more accurate than the
grid totals; register **C-100** keeps that question open. But reconciling at all already
assumes it. The old code applied the premise in one direction: a country of 0 sets the whole
grid to 0. It abandoned it in the other: a positive country with an empty grid lost its mass.
That is half a rule. This ADR applies it in both directions.

**2. The country decides how much, the grid decides where.** When a draw's grid is empty,
the pattern comes from the grid model's own other draws, not from outside data.

**3. The rule.** For each `(time, country)` group, a draw `s` needs filling when the country
value is positive and every grid cell is zero. It is filled by copying the **pre-scaling**
grid values of a **donor**: a draw chosen uniformly at random from the draws in the same group
whose grid has mass. Then the unchanged `reconcile_proportional` scales it as usual. The
result: the filled draw has exactly the donor's zero cells and the donor's proportions, and
sums to its own country value.

**4. Reproducible.** Each group draws from `numpy.random.default_rng([seed, time, country])`.
`seed` is an explicit keyword argument of `ReconciliationModule`, default `0`. The output does
not depend on how a caller chunks its calls (pipeline-core reconciles one month at a time) or
on the order groups are processed.

**5. No donor → `ValueError`.** If a group needs filling and none of its draws has grid mass,
the call raises before building any output. The message names the time, the country and the
number of draws. A single-draw grid (`S = 1`) has no other draws, so the same applies. A
country of 0 with an empty grid needs nothing and is not an error.

**6. Where it lives.** A new sibling module, `donor_fill.py`, runs as a pass over the grid
before the existing grouping step. `module.py` calls it after validation and the point-country
broadcast. **`proportional.py` and `grouping.py` do not change** (`Reconcile.md` §11, ADR-024):
their torch-oracle parity stays the proof that the scaling hasn't moved. `donor_fill.py` groups
rows by `(time, country)` the same way `grouping.py` does. That duplication is deliberate: it
is the second occurrence, and sharing it would mean editing the parity-frozen loop.

**7. Reporting.** `ReconciliationResult` gains `filled_draws: int`, the number of draws that
were filled. `method` reports the new constant `METHOD_DONOR_FILL = "proportional-donor-fill"`.

**8. It is the default, with no opt-out, released as 3.0.0.** A caller who needs the old
numbers pins `views-frames<3`.

**Out of scope:** borrowing from neighbouring months; choosing donors by similarity
(k-nearest); the draw-pairing question (C-62 / ADR-024).

---

## Rationale

- **Correctness first.** On the real run, 2.9–7.3% of the forecast's deaths disappeared
  silently. A rule that places them, or refuses loudly, is the only acceptable behaviour for
  a forecast delivered to a partner.
- **It uses the grid model's own knowledge.** A donor is a pattern the grid model actually
  produced for that country and month. Nothing is invented and no outside data is used.
- **It keeps the forecast's character.** Copying one real draw keeps the zeros and the sharp
  peaks. Different empty draws get different donors, so the spread of possible locations
  survives.
- **The evidence supports the simplest version** (read-only analysis of the 2026-10-30
  archive, 2026-10-31):
  - every one of the 546,813 empty-grid draws had donors in the same month and country (at
    least 10, median 130–211). A neighbouring-month fallback would never have been used, and
    neither would the no-donor error;
  - the empty-grid draws carried real deaths: country value median 3–5, mean 28–78, never
    below 1;
  - a draw's country value barely predicts its grid pattern (Spearman 0.06–0.09), so matching
    donors on the country value would behave like a random pick.
- **Minimum machinery.** One function, one pass, one keyword argument, one result field. No
  strategy registry and no configuration of methods.

---

## Considered Alternatives

### Alternative A: Mean pattern across the group's draws
- **Description:** fill an empty draw with the mean of each cell across the group's draws.
- **Pros:** simple; deterministic without a seed.
- **Cons:** the mean is positive in every cell that is non-zero in *any* draw, so the deaths
  are smeared thinly across many cells, a pattern no draw ever shows. It destroys the
  mostly-zeros character of the forecast. Every empty draw in a group gets the identical
  pattern, so spatial uncertainty is understated.
- **Why rejected:** it changes the forecast's character rather than filling a gap.

### Alternative B: k-nearest donors
- **Description:** choose among the k donors whose intensity is closest to the value being
  placed.
- **Pros:** respects the intuition that more deaths spread over more cells.
- **Cons:** the meaningful match is the donor's *own pre-reconciliation* grid total, not its
  country value (draw `s` of the grid and draw `s` of the country share almost no information:
  Spearman 0.06–0.09). The archive keeps only scaled output, so the method can't be tested yet.
- **Why rejected:** parked, not rejected on its merits. It needs a pre-reconciliation grid pool
  from views-models to test.

### Alternative C: Borrow from neighbouring months
- **Description:** when a month has no donor, borrow from month `t−1` or `t+1`.
- **Pros:** conflict locations persist from month to month.
- **Cons:** needs the whole forecast window in one call; edge months have one neighbour. It was
  needed zero times on the real run.
- **Why rejected:** parked until a real run hits the no-donor error.

### Alternative D: Opt-in method in 2.1.0
- **Description:** ship the fill as an option and keep the old behaviour as default.
- **Pros:** additive; no MAJOR.
- **Cons:** with the country as the authority, the old behaviour is a defect, not an
  alternative worth defaulting to. Every caller who forgot the option would keep losing mass.
- **Why rejected:** reconciliation has just started being used; the cheapest time to correct
  the default is now.

---

## Consequences

### Positive
- The reconciled grid sums to the country forecast in every draw, or the call raises.
- The loss is no longer silent anywhere: a filled draw is counted, a no-donor group raises.

### Negative
- **Breaking (MAJOR, GOVERNANCE.md):**

  | If your code… | 2.x | 3.0.0 |
  |---|---|---|
  | reconciles a group whose draws are all empty, with a positive country | returns zeros | `ValueError` |
  | reconciles a single-draw grid that is empty, with a positive country | returns zeros | `ValueError` |
  | reconciles draws with an empty grid and a positive country, where donors exist | returns zeros | the country's value, placed on a donor's pattern |
  | runs `assert_reconcile_contract` | requires empty draws to stay zero | requires every draw to sum to its country |
  | reads any other draw | — | bit-identical |

  No `from_legacy_*` shim: no wire format or signature changes. `CONFORMANCE_FLOOR` moves
  2.0.0 → 3.0.0.
- **Memory:** one extra values buffer per call when anything is filled. A call with nothing to
  fill makes no copy. For pipeline-core's month-at-a-time calls that is about 265 MB at
  64,742 cells × 1,024 draws (cf. C-71).
- **Filled draws are random.** They are reproducible with the same seed, but two seeds give
  different filled draws. That is the intended representation of the uncertainty about where
  the deaths fall.

---

## Implementation Notes

- `src/views_frames_reconcile/donor_fill.py`: the kernel
  `fill_empty_draws(grid, country, rng)` plus the frame-level pass. Pure functions; inputs are
  never mutated.
- `module.py`: `ReconciliationModule(map_keys, map_vals, *, seed=0)`; the fill runs between the
  broadcast and `reconcile_pgm_to_cm`.
- `result.py`: `METHOD_DONOR_FILL`, `ReconciliationResult.filled_draws`.
- `conformance.py`: the laws are restated (sum-to-country for every draw; zeros preserved in
  draws that had grid mass; a filled draw is proportional to a donor from its group).

---

## Validation & Monitoring

- Unit tests on realistic sparse fixtures (94–96% zeros), written to fail on 2.x first (#285).
- Mutation testing of the new path, which gates the release (#289).
- **Real-data proof on the 2026-10-30 archive (#292, 2026-10-31):** reconciled one month per
  call, all 36 months × 202 countries × 1,024 draws, on all three targets. Unplaced mass is
  **0** on every target (was 4.023% / 7.321% / 2.943%), scaling failures are 0, and no group
  lacked a donor. `filled_draws` = 164,429 / 188,481 / 193,903, exactly the measured counts.
  Reconciling a month alone or inside a two-month call is bit-identical. Runtime rose by
  about 0.2–0.4 s per monthly call. The reconciler's own memory overhead was not isolated.
- Consumers: views-models' `residual.py` should report 0 unplaced on 3.0.0; a non-zero value
  then means something is wrong.

---

## Open Questions

- **Is the country forecast actually the better total?** Register C-100.
- **Does the grid model's pattern depend on its own intensity?** If yes, k-nearest donors on
  the pre-reconciliation total would beat a random donor (Alternative B).

---

## References

- views-frames#283 (problem and measurement), epic #286, views-pipeline-core#579
- ADR-003 (fail loud), ADR-023 (the reconcile sibling), ADR-024 (principled joint
  reconciliation, deferred), C-62 (per-draw pairing), C-71 (dense-buffer memory)
- Register C-99 (the silent loss), C-100 (the country-authority premise)
