# Class Intent Contract — `views_frames.conformance`

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-07-31
**Related ADRs:** ADR-003, ADR-005, ADR-006, ADR-008, ADR-016, ADR-018, ADR-020, ADR-026

> Authored 2026-07-31 (register C-81). This was the last shipped surface without a
> contract — the same gap as `Reconcile.md` before it (register C-64), one module over.
> It matters more here than it did there: this module is the only part of the package
> whose *users run it themselves*, in their own CI, against their own code.

---

## 1. Purpose

This module is **the contract, made executable**. Everything else in the package
*implements* the frame contract; this module lets somebody else *check* it.

A consumer repository imports these functions and runs them in its own test suite,
against its own frame-producing code. If the check passes, that consumer's output is a
valid frame — by the same definition every other consumer is held to, at a single
governed version. That is what closes the cross-repo gap where each repository asserted
its own idea of "valid" (register C-10).

The checks are plain assertion functions with **no pytest dependency**, so they run in
any test runner, or in a script, or in a notebook.

## 2. Non-Goals (Explicit Exclusions)

- **Not a test suite for this package.** These functions do not test `views_frames`;
  they are shipped *to* consumers. This package's own tests live in `tests/`.
- **Not a validator of data.** They check that a *type* satisfies the contract, not that
  its numbers are correct, plausible, or in range.
- **Not a schema migrator.** They do not convert, repair, or normalise anything. A frame
  either satisfies the contract or an assertion fails.
- **Not version-negotiating.** `CONFORMANCE_FLOOR` records the version this suite belongs
  to; it does not branch on it. Consumers pin a floor, they do not get compatibility
  shims.
- **No domain knowledge.** Nothing here knows what a country or a grid cell is. The
  cross-level law takes an injected mapping like everything else (ADR-014).

## 3. Responsibilities and Guarantees

**`assert_frame_envelope(frame)`** — the *shared* envelope, for any frame-like type,
including ones that are not spatiotemporal. `float32` values, an explicit trailing sample
axis, and a save→load round-trip that returns the same values. This exists so a
non-spatiotemporal type — views-evaluation's `MetricFrame`, keyed by string axes — has
**one written authority** to validate against instead of re-asserting its own copy that
drifts (ADR-020, register C-46).

**`assert_frame_contract(frame)`** — the full spatiotemporal contract: everything the
envelope checks, plus the required `time` and `unit` identifiers being present, integer
dtype, and of length `n_rows`. This is what a producer of `PredictionFrame`-shaped output
runs. It does **not** check the spatial level or index write-protection — those are
guaranteed by construction in this package and are pinned by its own tests, not by a check
shipped to consumers.

**`assert_index_alignment_laws(index_a, index_b)`** — three same-level alignment laws:
`intersect` is commutative between the two indices, `is_superset_of` is reflexive, and
`searchsorted` against itself is an identity round-trip (positions recover the original
`time`/`unit`). The `-1`-for-absent-rows behaviour is *not* checked here — it is pinned by
this package's own tests and, from the consumer's side, by the fill law below.

**`assert_reindex_fill_law(frame, target, fill_value)`** — the dense-grid fill law
(ADR-026): the result's index **is** the target, present rows come through bit-exact, and
absent rows equal the fill. NaN-safe, so a NaN fill is checked as a NaN, not as an
inequality.

**`assert_cross_level_alignment_law(index, mapping, target_level)`** — remapping honours
the **time-varying** key: the same unit at two different times may produce two different
target units. A mapping keyed by unit alone would pass every other check here and still
be wrong, because borders move.

**`CONFORMANCE_FLOOR`** — the version string this suite belongs to. It moves only when the
contract itself changes, **not** when the package version does. It has stayed `"1.0.0"`
across every release since the freeze (ADR-018), which is the intended behaviour, not an
oversight.

**Assertions must be enabled.** Every entry point calls `_require_assertions()` first and
raises `RuntimeError` under `python -O`. Without it the entire suite would silently pass
on any input — the one failure mode that would make this module actively harmful
(register C-67).

## 4. Inputs and Assumptions

Inputs are **duck-typed on purpose** (`Any`). A consumer's type does not need to inherit
from anything here, or even be a `views_frames` class — that is the point. What is assumed
is that the object exposes the accessors the relevant check reads: `.values`, and for the
spatiotemporal contract `.index`, `.n_rows`, `.sample_count`, `.save`/`.load`.

The round-trip check writes to a `tempfile.TemporaryDirectory`, so the caller needs a
writable temp location.

## 5. Outputs and Side Effects

Every function returns `None` and raises `AssertionError` on violation, or `RuntimeError`
if assertions are disabled. Nothing is returned to inspect: the check either passes or
stops the test.

The only side effect is the temporary directory used by the round-trip check, which is
removed on exit.

## 6. Failure Modes and Loudness

| Condition | Result |
|---|---|
| The frame violates any checked property | `AssertionError` naming the property |
| Assertions disabled (`python -O`) | `RuntimeError` — never a silent pass (C-67) |
| The object lacks an accessor a check reads | `AttributeError` — the type is not frame-like |
| A NaN fill value in the fill law | Compared NaN-safely, not treated as unequal |

**Never silent.** A check that cannot evaluate its property must raise, not skip. This
module's whole value is that a passing run means something; a check that quietly does
nothing is worse than no check, because a consumer would trust it.

## 7. Boundaries and Interactions

- **Depends on:** `views_frames` only, plus numpy and the standard library. No pytest, no
  `views_*` sibling, no consumer package.
- **Depended on by:** consumer repositories, in their own CI. This is the only module here
  whose primary caller is outside this repository.
- **Governed by ADR-016**, which owns the floor and the ownership question; **ADR-018**
  freezes these signatures like any other public surface.
- **Adding a law** is additive and ships as a MINOR, alongside the feature it governs — as
  `assert_reindex_fill_law` did with ADR-026. Removing or tightening one is a MAJOR,
  because a consumer's CI would start failing on unchanged code.

## 8. Examples of Correct Usage

```python
# In a consumer's test suite
from views_frames.conformance import assert_frame_contract

def test_our_adapter_emits_valid_frames():
    assert_frame_contract(build_our_prediction_frame(...))
```

```python
# A non-spatiotemporal type validates against the shared envelope instead
from views_frames.conformance import assert_frame_envelope

def test_metric_frame_satisfies_the_envelope():
    assert_frame_envelope(build_metric_frame(...))
```

## 9. Examples of Incorrect Usage

```python
# WRONG — running under -O. The suite refuses rather than passing vacuously.
python -O -m pytest        # RuntimeError from _require_assertions

# WRONG — treating a passing check as a statement about the data.
assert_frame_contract(frame)   # says the frame is well-formed,
                               # not that its forecasts are sensible

# WRONG — copying a check into a consumer instead of importing it.
# That recreates the drift the suite exists to remove (C-46).
```

## 10. Test Alignment

- **Green:** each law holds for a valid frame (`test_conformance.py`); the published
  checkers run against all three frame types.
- **Beige:** the fill law degenerates to `reindex` on a superset target; NaN fill compared
  NaN-safely; the envelope accepts a non-spatiotemporal type.
- **Red:** the checkers **fail** when handed a frame that lies — `test_reindex_fill.py`
  uses deliberate `_Lying` wrappers that report a wrong fill, corrupt present rows, or
  return the wrong index, and asserts each is caught. `test_falsification_safety_audit_2026_07.py`
  pins the `-O` refusal.

The red row is the one that matters: a checker that cannot detect a violation is the
failure mode this module must never have.

---

**Register:** C-81 (this contract's absence), C-10 / C-46 (the drift it removes),
C-67 (the `-O` silent-pass it now refuses), C-64 (the same gap, previously, for
`views_frames_reconcile`).
