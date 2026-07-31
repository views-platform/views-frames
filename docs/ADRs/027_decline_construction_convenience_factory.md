# ADR-027: Frame construction stays two-step — the convenience factory is declined

**Status:** Accepted
**Date:** 2026-07-31
**Deciders:** VIEWS platform maintainers
**Consulted:** the 2026-06-24 design review of issue #113; the pipeline-core maintainer
**Informed:** views-pipeline-core, views-baseline, views-hydranet, views-datafactory

---

## In short

Someone asked us to add a shortcut for building a `PredictionFrame` — one line instead of two.
**We decided not to add it.**

Nothing changes for anyone. Code that builds frames today keeps working exactly as it does now.

---

## What was asked for

Building a `PredictionFrame` takes two steps today. First you describe *which rows your numbers
belong to*, then you attach the numbers:

```python
index = SpatioTemporalIndex(time=months, unit=grid_cells, level=SpatialLevel("pgm"))
frame = PredictionFrame(predictions, index)
```

Issue **#113** asked us to collapse that into one step:

```python
frame = PredictionFrame.from_arrays(predictions, time=months, unit=grid_cells, level="pgm")
```

The motivation was reasonable. A model repository does this at the end of every model run. With the
two-step form, every repository that produces predictions has to know that a separate "index" object
exists and how to build it. The one-step version would hide that.

### Two terms this decision depends on

**"The leaf"** is this package, `views-frames`. It sits at the bottom of the platform: every other
repository depends on it, and it depends on none of them. That position is why changes here are
expensive — they ripple outward to everyone.

**"The frozen surface"** means that since v1.0.0 we promised not to change or remove anything public
(ADR-018). We can *add*, but we can never take back. So every public method we add is permanent
unless we coordinate a breaking release across every repository that uses us.

## What actually happened to the request

The request was filed in June 2026 and never built. That turns out to be the most useful evidence we
have.

**Nobody was blocked.** Issue #113 said so itself: engines *"can migrate today by constructing
`SpatioTemporalIndex` directly"* — and that is what they did. The engine repositories migrated
thirteen months ago using the two-step form and have been fine since. No one came back asking again.

**The shape was already agreed; only the need was missing.** An earlier review settled *how* it would
look if we built it — a method on the class rather than a standalone function. That design was never
in dispute. What never arrived was a case where the two-step form actually caused a problem.

**Meanwhile it cost us anyway.** Three entries in our risk register existed purely to watch this
unbuilt thing: one worried the shortcut would grow beyond a shortcut, one worried two ways of
building the same object would drift apart, and one worried the request's wording would pull
domain-specific code into this package. All three were reviewed every cycle for thirteen months, and
all three were guarding something that did not exist.

## Decision

**Frame construction stays two-step.** We will not add `build_prediction_frame`,
`PredictionFrame.from_arrays`, or a `factory.py` module.

The reasoning is a trade of costs:

- **The two-step form costs one extra line and one extra import.** It is not slow, not error-prone,
  and not confusing once seen. It is simply longer.
- **The one-step form would cost us permanently.** Because the surface is frozen, adding it is a
  commitment we cannot walk back. We would be buying a small, temporary convenience with a permanent
  obligation.

There is also a positive reason, not just a cost argument. **`SpatioTemporalIndex` is not clutter to
be hidden — it is the point.** It is how a caller states which rows their numbers describe. Making
that explicit is exactly what a data-contract package should force people to say out loud, rather
than guess at. Hiding it would make the package more convenient and less clear.

### If we ever change our minds

The design is already worked out, so a future request does not restart the argument. It would be:

- a **method on `PredictionFrame`** — never a standalone function, and never a `factory.py` module;
- **no logic of its own** — it just calls the two existing steps, so anything we add to the index
  later flows through automatically without changing this method;
- **only on `PredictionFrame`** — not copied onto the other two frame types unless they need it too;
- named arguments only, and no second alias for the same thing.

**What would reopen this:** someone showing a real place where two steps genuinely do not work — not
just where they would prefer one. *Being longer is not, by itself, a reason.* This matches how we
handle other deferred work: we wait for a concrete case rather than guessing at one.

## Alternatives we considered

**Build it now, as designed.** Rejected on cost, not on design — the design is fine, the need is
absent. Building it would add a permanent method, turn a small documentation release into a feature
release, and immediately invite follow-ups ("can it also accept a dictionary? guess the level? take a
DataFrame?"). Declining can be undone; shipping cannot.

**Build it as originally requested, as a standalone function.** Rejected earlier and again here.
Everyone already imports `PredictionFrame`, so a separate function adds a second way to do one thing
without adding reach.

**Create a `factory.py` module for construction helpers.** Rejected permanently. A module with a
general name attracts loosely-related helpers over time in a way a single method does not. This is
the specific slope our risk register was set up to watch.

**Leave the request open and undecided.** Rejected — this was the status quo, and it is what produced
three register entries sitting in limbo for over a year. An undecided proposal is not free: it
consumes attention at every review and makes our own tracking report work that will never happen.

**Move views-baseline's local helper into this package.** Rejected. That helper loops a
caller-supplied function over entities and time to build many frames at once. That is model-specific
work and belongs in the model repository, not in a shared data-contract package. Only its innermost
two lines were ever in scope here — and those are what we are declining.

## Consequences

**What changes: nothing.** No migration, no deprecation, no action for any repository. Code that
builds frames today keeps working. views-baseline keeps its own helper.

**What we gain:**

- Three risk-register entries close (C-52, C-53, C-54). They were guards on an unbuilt thing.
- The public surface does not grow, and it did not grow for a reason we can point at.
- The next similar request has an answer to cite instead of an argument to repeat.
- The decision is findable. Until now it lived only in the risk register, which is why it could sit
  undecided for a year — nothing forced it to conclude. Someone asking *"why can't I build a frame in
  one line?"* will now find this document.

**What we accept:** if a real need appears, we will have spent a little time re-reading this page
before building the thing we already designed. That is a cheap price for not carrying a permanent
method we did not need.

This is documentation only — no code changed, and the conformance floor stays at `1.0.0`.

---

## References

- **Issue #113** — the original request. Closed by this ADR.
- **ADR-018** — the v1 API freeze: additions are permanent, removals require a coordinated major release.
- **ADR-003** — prefer explicit declaration over inference.
- **ADR-001** — what belongs in this package and what does not; names accretion as its main long-term risk.
- **ADR-011** — the three frame types are separate siblings; symmetry is not assumed.
- **ADR-013** — identifiers may be added later, which is why any future helper must carry no logic of its own.
- **Risk register** — resolves C-52, C-53 and C-54; records the outcome of disagreement D-09.
- Delivered as story S1 (#209) of epic #208, via PR #220.
