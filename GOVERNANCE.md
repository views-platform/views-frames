# Governance — views-frames

`views-frames` is the VIEWS platform's leaf data-contract package: many repos
import it, so a breaking change is expensive. This document records the ownership
and release governance required of a keystone (ADR-016).

## Owner

**Keystone owner:** VIEWS platform maintainers. The owner is accountable for the
contract — reviewing every change against the ADRs/CICs, cutting releases, and
driving any cross-repo MAJOR bump.

## Conformance floor

The published conformance suite ships with the wheel in **three modules**, one per package.
Every consumer runs it in CI against its own adapter output.

**The code is the source of truth, not this list.** It has fallen behind twice
(`assert_frame_envelope` in v1.4.0, `assert_reindex_fill_law` with ADR-026), so it is
written to be checked rather than trusted — and the two are not read the same way:

| Module | Published surface | Where the code declares it |
|--------|-------------------|----------------------------|
| `views_frames.conformance` | `assert_frame_contract`<br>`assert_frame_envelope`<br>`assert_index_alignment_laws`<br>`assert_cross_level_alignment_law`<br>`assert_reindex_fill_law`<br>*plus* the `CONFORMANCE_FLOOR` constant | an explicit `__all__` |
| `views_frames_summarize.conformance` | `assert_summarizer_contract` | no `__all__`; the module's public `assert_*` functions (ADR-017, `docs/CICs/Summarize.md`) |
| `views_frames_reconcile.conformance` | `assert_reconcile_contract` | no `__all__`; the module's public `assert_*` functions (ADR-023, `docs/CICs/Reconcile.md`) |

Read all three at once — the sibling packages declare no `__all__`, so asking for one raises
`AttributeError` rather than telling you anything:

```bash
uv run python -c "
import views_frames.conformance as c
import views_frames_summarize.conformance as s
import views_frames_reconcile.conformance as r
for name, mod in (('views_frames', c), ('views_frames_summarize', s), ('views_frames_reconcile', r)):
    pub = getattr(mod, '__all__', None) or [n for n in vars(mod) if n.startswith('assert_')]
    print(f'{name+\".conformance\":38} {sorted(pub)}')
"
```

- **Conformance-floor version:** `1.0.0` (`views_frames.conformance.CONFORMANCE_FLOOR`).
- The floor is a **single governed version every consumer runs regardless of its
  runtime pin** — this is what makes the suite test "all consumers agree," not
  "my adapter vs my pin" (closes register C-10). The floor is bumped deliberately,
  as a governance act, not implicitly by a consumer upgrading.
- **What the floor tracks (register C-27):** the **whole published conformance
  surface** — every `assert_*` entry point in the table above, across all three modules,
  not just the `views_frames.conformance` ones. (`CONFORMANCE_FLOOR` is the number being
  governed, not a checked surface; it does not track itself.) It is bumped whenever a
  **breaking** change is made
  to any of them, so reading `CONFORMANCE_FLOOR` tells a consumer exactly which contract
  version its CI asserts. Additive surface (a new law or method) is MINOR and does
  **not** bump the floor.

## Versioning (SemVer for a contract)

- **MAJOR** — removing/renaming a field, changing a dtype or axis meaning, adding a
  **required** identifier, tightening an invariant.
- **MINOR** — a new frame type, a new **optional** metadata field or identifier, a
  new method, a new `io/` format.
- **PATCH** — bug/doc fixes with an identical contract.

**Pre-1.0 (before the freeze below):** because no consumer had pinned the package,
breaking changes were allowed in a **MINOR** bump (each one labelled "Changed
(breaking, pre-1.0)" in `CHANGELOG.md`). The `(time, unit)` `cross_level_align`
re-key (v0.3.0) was the last such change. This pre-1.0 latitude **ends at v1.0.0.**

## Stability — the v1.0 freeze

**v1.0.0 freezes the public API.** From v1.0.0 on, the SemVer rules above are
binding without the pre-1.0 latitude: any breaking change to the frozen surface is
a **MAJOR** bump and follows the cross-repo process below. What v1.0.0 locks (the
surface a consumer may safely pin) is recorded in **ADR-018**, which is the authority — read
the frozen list and the "Additive since v1.0.0" pointer there rather than the sketch below.
This summary had drifted from ADR-018 until 2026-08-17 — most consequentially by omitting
the entire `views_frames_reconcile` package (register C-85). It is kept deliberately coarse
now so it cannot drift again:

- the three frames, their constructor shapes and their accessors;
- `SpatioTemporalIndex`, its same-level alignment and its `(time, unit)`-keyed
  time-aware cross-level alignment, plus the row-uniqueness stance;
- the value objects the frames compose — `FrameMetadata`, `SpatialLevel`;
- the `Frame`/`SpatioTemporalIndexed`/`Sampled`/`Persistable` protocols;
- the published conformance suite and laws (the table above);
- the estimator surface of `views_frames_summarize`, and the reconciliation surface of
  `views_frames_reconcile` (additive since v1.7.0).

**ADR-018 names every member.** If this list and ADR-018 disagree, ADR-018 wins.

New surface remains additive (MINOR). The bar to a MAJOR bump is deliberately high
(see the closing note); reaching v1.0 with no pinned consumer is intentional — it
gives the first adopters a stable target to pin against.

## Cross-repo MAJOR-bump process

A MAJOR change is never a silent break:

1. Propose it as an ADR (the decision + the migration).
2. Land it behind `from_legacy_*` shims where a consumer format changes.
3. Bump the conformance floor and coordinate a merge-train across consumers.

If the package needs frequent MAJOR bumps, it is not abstract/stable enough —
push the volatility out into consumer adapters (SAP).
