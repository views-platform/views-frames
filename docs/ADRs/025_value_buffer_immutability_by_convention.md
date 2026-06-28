
# ADR-025: Value-buffer immutability is by convention; only the index is enforced

**Status:** Accepted
**Date:** 2026-06-28
**Deciders:** VIEWS platform maintainers
**Consulted:** repo-assimilation + test-review (2026-06-27, the audit that surfaced C-63)
**Informed:** views-pipeline-core, views-datafactory (consumers that hold frames)

---

## Context

The leaf advertises **immutable value objects** (README design principle 3; ADR-013;
PredictionFrame CIC §9 lists `pf.values[:] = 0` as forbidden). The audit chain
(repo-assimilation + test-review, 2026-06-27, register **C-63**) established empirically that
the guarantee is enforced **only for the index**, not the value buffer:

- `SpatioTemporalIndex` stores its `time`/`unit` arrays `setflags(write=False)`
  (`index.py:55-56`) — they are genuinely write-protected.
- The frame **value buffer is not.** `_validation.coerce_values` returns a float32 input
  **without copy** and without `setflags` (`_validation.py:64`); each frame constructor does
  `self._values = values` with no write-protection; `frame.values.flags.writeable` is `True`.
- `with_metadata` returns a new frame **sharing** that buffer (zero-copy, C-07). So an
  in-place mutation of `frame.values` (`f.values[:] = 0`, `f.values *= k`) **silently
  corrupts every frame sharing the buffer**, with no error signal — the contract claims an
  invariant it does not enforce.

The obvious fix — add `self._values.setflags(write=False)` in each constructor — is trivial
code, and the audit confirmed **zero** in-place `.values`/`_values` mutations anywhere in
`src/` or `tests/`, so it would be safe. **But it is a breaking change under our own
governance:** `GOVERNANCE.md` lists **"tightening an invariant"** as a **MAJOR** bump, and
`values` is an explicit member of the frozen public surface (**ADR-018**). A MAJOR triggers
the full **cross-repo coordinated-bump process** (propose ADR → consumer shims → bump
`CONFORMANCE_FLOOR` → merge-train across every consumer). That is disproportionate to a hole
**no code in the ecosystem actually hits**.

We must stop the contract from lying, without paying a platform-wide MAJOR for a latent,
unexercised gap. That is the decision this ADR records.

---

## Decision

**Value-buffer immutability is a guarantee held *by convention*, not by enforcement. Only the
index is write-protected.**

1. Mutating a frame's `.values` buffer in place is **unsupported**: it may silently corrupt
   other frames that share the buffer (the zero-copy / `mmap` path). Consumers must build a
   new frame instead. This is the documented contract; it is **not** mechanically enforced.
2. The leaf deliberately leaves the value buffer **writeable** so that structural/metadata
   operations stay **zero-copy** and `mmap`-backed frames stay `mmap`-backed (design
   principle 2 / C-07). The enforced invariant is on the **index** (`time`/`unit`), which is
   small, never shared mutably, and already `setflags(write=False)`.
3. **The `setflags`-enforce on `.values` is a deferred MAJOR-rider.** When a MAJOR bump
   happens for any reason, enforcement is added **for free** as part of that coordinated bump:
   `self._values.setflags(write=False)` after assignment in each frame constructor, plus a red
   test that `frame.values.flags.writeable is False`. It is **out of scope** to do this on its
   own (it does not justify a standalone MAJOR).

In scope: correcting the docs (the three frame CICs, README principle 2) to state the
by-convention reality. Out of scope: any code change; any change to `CONFORMANCE_FLOOR` (stays
`1.0.0`); enforcing read-only `.values` now.

---

## Rationale

- **Correctness > convenience, but proportionate.** The contract must be honest, but
  enforcement here buys near-zero real-world safety (nothing mutates `.values`) at the cost of
  a full cross-repo merge-train. Correcting the docs removes the dishonesty at zero cost and
  keeps the enforcement option open for when a MAJOR is already being paid.
- **Zero-copy is the load-bearing guarantee.** Write-protecting the *shared* value buffer
  interacts with the C-07 copy-vs-view semantics (a frozen buffer shared across frames changes
  caller-visible flags); the index, which is never shared mutably, is the clean place to
  enforce. Keeping the value buffer writeable preserves the §7 OOM-avoidance the whole frame
  contract exists for.
- **Asymmetry made explicit, not hidden.** The index-enforced / value-by-convention split is
  now stated, so a reader is not misled into relying on a guard that is not there.

---

## Considered Alternatives

### Alternative A: Enforce read-only `.values` now (a MAJOR)
- **Pros:** the strongest guarantee; the contract becomes self-enforcing.
- **Cons:** a **MAJOR** (`GOVERNANCE.md` "tightening an invariant"; `values` is frozen,
  ADR-018) → the full cross-repo coordinated-bump process for a hole nothing exercises.
- **Reason for rejection:** disproportionate. Deferred to ride a future MAJOR for free.

### Alternative B: Leave the docs as written
- **Pros:** no work.
- **Cons:** the contract keeps claiming an enforced invariant it does not enforce — the docs
  lie, and a consumer could rely on the lie.
- **Reason for rejection:** a contract that lies is worse than an honestly-scoped one.

### Alternative C: Correct the contract + defer the enforce (**chosen**)
- Make the docs match the code (by-convention, index-enforced); record the `setflags`-enforce
  as a deferred MAJOR-rider. No MAJOR, no merge-train, honest contract.

---

## Consequences

### Positive
- The immutability contract is **honest**: docs match code (C-63 resolved).
- **No MAJOR, no cross-repo coordination**; `CONFORMANCE_FLOOR` stays `1.0.0`; the release
  stays the additive `1.8.0`.
- Zero-copy / `mmap` is untouched.

### Negative
- The value buffer stays **writeable**, so a careless consumer *can* still corrupt
  buffer-sharing frames. Mitigated: documented as unsupported in all three frame CICs + this
  ADR; no code in the ecosystem does it; the deferred-enforce removes the gap on the next
  MAJOR. (The risk is recorded as the resolution-with-residual of C-63.)

---

## Implementation Notes

- **Docs (this release, S2 / #181):** reword PredictionFrame / TargetFrame / FeatureFrame CIC
  §9 (the `pf.values[:] = 0` example) and §3 immutability wording, and README design principle
  2, to state: the **index** is enforced read-only; the **value buffer is immutable by
  convention** (mutating it is unsupported and may corrupt shares — build a new frame), left
  writeable to preserve zero-copy. Mark register **C-63 Resolved** (contract corrected) with
  the deferred-enforce recorded.
- **The deferred MAJOR-rider (future):** in `prediction_frame.py` (~line 44), `target_frame.py`
  (~line 43), `feature_frame.py` (~line 52), add `self._values.setflags(write=False)` after
  the `self._values = ...` assignment; add a red test mirroring `tests/test_properties.py:38`
  asserting `frame.values.flags.writeable is False` and that an in-place write raises. Do this
  **only** as part of a MAJOR that is already happening.

---

## Validation & Monitoring

- This release: no code change → the import-DAG, parity, coverage, and `mypy` gates are
  unaffected; `validate_docs` stays green; no doc asserts an enforced read-only `.values`.
- Reconsider if a consumer is found mutating `.values` in place (promote the deferred-enforce,
  or schedule the next MAJOR sooner), or whenever a MAJOR is next opened (do the enforce then).

---

## Open Questions

- **A zero-copy-preserving enforcement for the future MAJOR.** Returning a read-only *view*
  from the `.values` property (`arr.view()` + `setflags(write=False)` on the view) would make
  `frame.values[:] = 0` raise while leaving the underlying shared buffer writeable internally —
  cleaner for zero-copy than freezing the shared buffer. It still changes observable behavior
  (mutation now raises) and so is still a MAJOR, but it is the preferable mechanism when that
  MAJOR is paid. Recorded for the principled redesign, not decided here.
