# ADR-028: 2.0.0 — a frame's index must actually be an index

**Status:** Accepted
**Date:** 2026-08-18
**Deciders:** VIEWS platform maintainers
**Consulted:** the falsification audit of 2026-08-18; register C-13's pre-tag checklist
**Informed:** views-faoapi, views-postprocessing, views-crafdapi (the three pinned consumers)

---

## In short

Until now you could hand a frame **anything** as its index and it would be accepted. A
different frame. A bare object with an `n_rows` attribute. The frame was built, it looked
fine, and the published conformance suite said it was fine.

From 2.0.0 that raises `TypeError`.

**Nothing a correct consumer does changes.** If you pass a `SpatioTemporalIndex` — which is
what the type hint has always said, and what every example and every test does — you will
not notice this release. What changes is that the wrong thing now fails immediately instead
of much later and somewhere else.

This is the package's **first MAJOR** and the first move of `CONFORMANCE_FLOOR` since the
v1.0.0 freeze.

---

## What was wrong

Construction validated `y_pred` four times over — coerced it, checked its dtype, its
dimensionality, its row count. It never checked `index` at all. It read exactly one
attribute off it, `n_rows`, to compare against the value array's first axis.

A frame has an `n_rows`. So this worked:

```python
other = PredictionFrame(values, index)
frame = PredictionFrame(values, other)      # `other` is a FRAME, not an index
```

So did this:

```python
class NotAnIndex:
    n_rows = 2

PredictionFrame(values, NotAnIndex())       # also fine, apparently
```

The resulting object was not a frame in any meaningful sense — `frame.index.time` raised
`AttributeError` — but it was *constructed*, and it would travel. Every summarizer reads
`.values` and never `.index`, so `collapse`, `map_estimate`, `hdi` and the rest returned
**numerically correct answers** on it. The failure surfaced only when something finally
touched the index, far from the line that caused it.

**The part that made this worth a MAJOR:** `assert_summarizer_contract` — published under
ADR-016, run by consumers in *their* CI — returned cleanly for such a frame. A checker
whose stated most important job, in `docs/CICs/Conformance.md`, is to **fail** when handed
a frame that misreports itself, was issuing a false pass.

Two smaller defects from the same audit ship with it: the same-level alignment ops leaked
`AttributeError: '...' object has no attribute '_level'` — a private attribute of a class
the caller never named — where ADR-008 requires `ValueError`/`TypeError`; and `map_estimate`
crashed with a bare `IndexError` on a non-finite draw where its two sibling estimators raise
a clean `ValueError`.

---

## Why this is a MAJOR and not a quiet fix

`GOVERNANCE.md` lists **"tightening an invariant"** as a MAJOR bump, with no exception for
guards that are obviously right. ADR-018 freezes "the three frames, **their constructor
shapes**". A call that returns a valid object today raises tomorrow.

The precedent is **ADR-025 / register C-66**, and it is exact. That ADR considered
`self._values.setflags(write=False)` — one line, mandated in spirit by ADR-008, with an
audit confirming nothing in the ecosystem exercised the gap — and still classified it MAJOR
and deferred it, because tightening frozen surface is MAJOR *regardless of how safe the
guard is*.

The test this repo actually applies is **"does any currently-succeeding call start
raising?"** C-57's `map_estimate` hardening answers no — the input already crashed, just
uglily — so it is additive and rides freely. The index guard answers yes. So: MAJOR.

The bar for a MAJOR is deliberately high here, and it is being met by a *validation* fix
rather than a feature. That is the honest reading of our own rule, and the alternative —
leaving a published checker issuing false passes indefinitely because the fix is
inconveniently classified — is worse.

---

## Decision

1. The three frame constructors raise `TypeError` unless `index` is a `SpatioTemporalIndex`.
2. `SpatioTemporalIndex._require_same_level` raises `TypeError` on a non-index argument,
   which covers `searchsorted`/`reindex`, `is_superset_of` and `intersect` in one place.
3. `assert_summarizer_contract` asserts its frame's index is a `SpatioTemporalIndex`.
4. `CONFORMANCE_FLOOR` moves `1.0.0` → `2.0.0`.
5. The MAJOR carries its riders (register C-13): **C-66** value-buffer write protection and
   **C-57** `map_estimate`'s non-finite guard. **C-43** is declined — see below.

### Riders, and the one declined

**C-66 did not ship as written.** ADR-025 records the fix as
`self._values.setflags(write=False)`. That would have been a mistake: `coerce_values`
returns the caller's *own* array when it is already `float32`, which is the C-07 zero-copy
guarantee, so the one-liner silently makes the **caller's** array read-only — action at a
distance well outside this contract. Measured rather than assumed: the naive form does flip
`caller.flags.writeable` to `False`. The frames take a **read-only view** instead, which
locks the frame's buffer, leaves the caller's array alone, and still shares memory. The
memmap path keeps its subclass and its zero-copy through `.view()`.

**C-43 is declined, deliberately.** C-13's checklist names it a rider, so passing it over
silently would be the "claimed enforcement that does not exist" failure this repo has
recorded three times. `bimodality._coarse_counts` is a clipped linear bucket, deliberately
approximate, for a heuristic flag. `point._batched_map` reproduces `numpy.histogram`'s
edge-exact path bit-for-bit and is ~1-ulp sensitive across numpy versions (the C-24
portability saga). They are not two implementations of one concept — they are two different
algorithms that both happen to bin. Extracting a shared helper forces one onto the other's
path and changes the output of either `bimodality` or the frozen `map_estimate`, to serve a
Tier-4 entry the register itself says has no correctness or reliability impact. C-43's
precondition is rewritten to `#89` alone.

### Migration

**For nearly every consumer: change your version constraint and re-lock. Nothing else.**

```diff
- views-frames = ">=1.10.2,<2"
+ views-frames = ">=2.0.0,<3"
```

Your code breaks only if it was already broken:

| If you… | Before | Now |
|---|---|---|
| pass a `SpatioTemporalIndex` as `index` | works | works, unchanged |
| pass a frame or other object as `index` | silently constructed | `TypeError` at construction |
| pass a non-index to `reindex`/`reindex_fill` | `AttributeError` on `_level` | `TypeError`, naming what was expected |
| mutate `frame.values` in place | silently corrupted every frame sharing the buffer | `ValueError: assignment destination is read-only` |
| call `map_estimate` on `inf`/`NaN` draws | bare `IndexError` | `ValueError` naming the cause |

The in-place `.values` mutation is the only row where working code could plausibly stop
working — and ADR-025 documented that operation as unsupported, so code doing it was
relying on something the contract already denied.

**No `from_legacy_*` shim.** GOVERNANCE's MAJOR process asks for one "where a consumer
format changes". No wire format, no serialized layout and no signature changes here; only
the set of inputs that were never valid narrows. A shim would have nothing to translate.

---

## Alternatives we considered

**Defer to some later MAJOR, as C-66 was deferred.** The C-66 pattern — write the guard and
the red test, register the entry, let it ride — was the recommendation until the maintainer
chose otherwise. It was defensible: no consumer had hit the gap. It was rejected because a
MAJOR that never arrives leaves a published checker issuing false passes for an unbounded
time, and because deferring meant carrying C-66 and C-57 unshipped as well. Deferring is
cheap exactly once; this would have been the third deferral onto the same imaginary release.

**Fix only the checker, leave construction alone.** Tempting, since the checker is the part
that lies, and it would not have been a MAJOR. Rejected: it treats the symptom. The
constructor is where the invariant belongs (ADR-008: validation happens in `__init__`,
before the object is usable), and a malformed frame would still exist and still travel — it
would merely be caught by one checker rather than never.

**Make the guard a `Protocol` check rather than `isinstance`.** ADR-009 has consumers depend
on protocols, so this looked more in keeping. Rejected on the facts:
`SpatioTemporalIndexed` describes a **frame** (`n_rows`, `identifiers`, `index`), not an
index — `SpatioTemporalIndex` does not even satisfy it, having no `.index`. And
`runtime_checkable` protocols check member *presence* only, which is precisely the weak
duck-type that caused this. The constructors' own annotation has always said
`SpatioTemporalIndex`; the guard now matches it.

**Extract the guard into `_validation.py`.** It is where the other construction guards live.
Rejected on a hard constraint: `index.py` imports `_validation.py`, so `_validation.py`
cannot import `SpatioTemporalIndex` back without a cycle — and `tests/test_import_enforcement.py`
plus the `import-linter` contracts exist to keep that graph acyclic. Written three times
instead, which ADR-011 Option C already accepts as the price of having no shared base.

---

## Consequences

**Good.** A frame cannot be built with a non-index. A published checker no longer certifies
frames it was written to reject. The alignment family names what it expected instead of
leaking a private attribute. `frame.values` is immutable in fact rather than by convention,
closing the Tier-2 mechanism behind C-63. `map_estimate` fails like its siblings.

**Costly.** Three consumer repos are pinned `<2` and reach this only by re-locking, and each
needs an adoption issue before tagging per C-13. `CONFORMANCE_FLOOR` moving means every
consumer's CI asserts a new contract version — deliberate, and the reason the constant
exists, but it is the first time it has happened.

**Unproven.** That no consumer relies on the old leniency. The audit could measure this
repo and read the three consumers' pins; it could not run their suites. The migration table
above is the mitigation — every behaviour that changes is enumerated, so a consumer can
check their own code against it without reading this ADR's reasoning.

**A precedent set.** This is the first MAJOR and the first floor move. It should not become
routine: GOVERNANCE's closing note says that a package needing frequent MAJOR bumps is not
abstract enough. The correct reading of this release is that a validation hole present since
v1.0.0 was found by deliberately attacking the claim that the package was finished — not
that the freeze is negotiable.

---

## References

- Register **C-13** (the pre-tag checklist this release executes), **C-66** (shipped here),
  **C-57** (shipped here), **C-43** (declined here), **C-63** (the Tier-2 mechanism C-66
  closes), **C-07** (the zero-copy guarantee the read-only view preserves).
- **ADR-025** — the deferral this release spends; its reasoning is the direct precedent for
  classifying the index guard as MAJOR.
- **ADR-018** — the frozen surface, amended by this release.
- **ADR-008** — validation happens in `__init__`, with `ValueError`/`TypeError`.
- **ADR-011** — Option C, which makes the three-times guard the house pattern.
- **ADR-016** — why a false pass in the published suite is a cross-repo defect.
- `GOVERNANCE.md` — "tightening an invariant" = MAJOR; the cross-repo bump process.
