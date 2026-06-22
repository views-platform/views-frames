
# ADR-012: Sample axis convention — always an explicit trailing axis

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** VIEWS platform maintainers
**Informed:** views-pipeline-core, views-datafactory, views-faoapi, views-reporting

---

## Context

The two twins disagree on where the posterior-sample axis lives: `PredictionFrame` is `(N, S)`
(sample axis at position 1, **always present**), while `FeatureFrame` is `(N, F)` or `(N, F, S)`
(sample axis at position 2, **optional**). A single contract cannot host both conventions, and
this decision is upstream of `protocols.py`, `_validation.py`, and every shape check — so it
**cannot be deferred** while unification proceeds (C-02, C-16). This is the structural blocker
the falsification audit flagged.

---

## Decision

The sample axis **S** is **always an explicit trailing axis** with `S ≥ 1`.

- `PredictionFrame`: `(N, S)`
- `FeatureFrame`: `(N, F, S)`
- `TargetFrame`: `(N, 1)`

`is_sample` is `S > 1`. `collapse(method)` reduces the **trailing** axis, returning a frame with
`S = 1`. There is **one** shape contract across the whole family and **no `ndim` branching** in
shared code. A non-sampled frame still carries an explicit trailing `S = 1` axis rather than
omitting the axis.

---

## Rationale

A uniform, always-present trailing axis gives one validation path and one `collapse`
implementation for every frame, eliminating the `ndim`-branching that an optional axis forces
into every shape check. The small cost — a "redundant" `S = 1` axis on non-sampled frames — is
trivial in memory (one stride) and pays for itself in contract simplicity. It also makes the
`Sampled` protocol total: every frame can answer `sample_count`/`is_sample`/`collapse`.

---

## Considered Alternatives

### Alternative A: optional / absent sample axis (present only when sampled)
- **Pros:** most numpy-idiomatic; non-sampled frames are minimal `(N,)`/`(N, F)`.
- **Cons:** every operation must branch on `ndim`/axis-presence; `collapse`/`is_sample` become
  partial; the twins keep their *different* conventions, defeating unification.
- **Reason for rejection:** the branching and partiality are exactly the friction a shared
  contract must remove.

---

## Consequences

### Positive
- One shape contract; total `Sampled` protocol; no `ndim` branching in shared code.
- Closes the C-02 sequencing contradiction and de-risks the C-16 unification.

### Negative
- Relocating `PredictionFrame` is **not verbatim** — its `(N, S)` already matches, but its
  pandas-based NaN validation must be rewritten numpy-only (C-17), and `FeatureFrame` callers
  that produced 2-D `(N, F)` arrays must now emit `(N, F, 1)`. Accepted; covered by shims.

---

## Implementation Notes

- Enforce in `_validation.py`: assert `values.ndim >= 2` and treat `values.shape[-1]` as `S`.
- `collapse` always reduces `axis=-1`.
- Producer adapters (`grid_to_feature_frame`, the model engines) must emit the trailing axis;
  provide a `from_legacy_*` shim where a producer currently emits a 2-D feature array.

---

## Validation & Monitoring

- Conformance property: for every frame, `frame.collapse().values.shape[-1] == 1` and
  `is_sample == (values.shape[-1] > 1)`.
- Failure mode to watch: any shared code path that inspects `ndim` to locate the sample axis —
  that is a regression toward the rejected optional-axis convention.

---

## Open Questions

- None blocking. The exact `collapse` reduction methods (mean/median/quantile/HDI) are a
  `Sampled`-protocol detail tracked in the CICs (D1), not here.

---

## References

- README §4.1, §13a.2; a falsification audit.
- Risk register: **C-02**, **C-16**, **C-17**.
- Issue #3; Epic #13.
