
# ADR-005: Testing as Mandatory Critical Infrastructure

**Status:** Accepted  
**Date:** 2026-06-21  
**Deciders:** VIEWS platform maintainers  

---

## Context

`views-frames` is the single data contract through which the entire VIEWS platform moves
arrays aligned to `(time, unit)`. A defect here is not contained: it propagates to every
consumer (views-pipeline-core, views-datafactory, views-evaluation, the model repos,
views-reporting) on the next version bump. The failure modes that matter most are not
crashes but *quiet* ones — an alignment that drops rows silently, a `collapse` that
reduces the wrong axis, a "structural" `select` that secretly copies a multi-GB buffer
and reintroduces the §7 blow-up.

In such a leaf, failure is not limited to exceptions. It includes:
- silent semantic drift (an alignment law that quietly stops being commutative),
- misuse by well-intentioned consumers (passing a partially-overlapping index and getting truncation, C-26),
- over-trust in a frame whose identifiers were never actually validated,
- memory regressions where an op that should share a buffer copies it instead.

Given this, testing is not a convenience. It is **critical infrastructure**. The design
bible already designates a **published conformance suite** every consumer re-runs in CI
(README §9) — codifying that intent here. Falsification stubs already live in `tests/`
as TDD-red enforcement artifacts.

---

## Decision

This repository treats **testing as mandatory critical infrastructure**.

All non-trivial functionality **must be covered by tests**.

Testing is not limited to correctness under ideal conditions, but must explicitly address:
- adversarial behavior,
- realistic human use,
- and system robustness under expected operation.

To achieve this, tests are explicitly divided into **three complementary categories**:

- 🟥 **Red team tests** (adversarial)
- 🟫 **Beige team tests** (realistic, neutral misuse)
- 🟩 **Green team tests** (supportive, resilience-oriented)

Each category serves a distinct purpose and **none may substitute for another**.

---

## Test Taxonomy

### 🟥 Red Team Tests — Adversarial Testing

Red team tests deliberately attempt to **break, exploit, or misuse the system** by assuming hostile or worst-case behavior.

- **Goal:** expose failure modes and unsafe behaviors
- **Mindset:** *“How could this go wrong?”*
- **Project-grounded focus (planned):**
  - Constructing a frame with a NaN / wrong-dtype / `object`-dtype identifier (must fail loud, ADR-003/008)
  - Mismatched array length vs identifier length; `sample_count < 1`; missing required `{time, unit}`
  - Feeding `object` dtype or a list-in-cell array (the banned non-scaler, C-40/C-66) — must be rejected, not coerced
  - Aligning two indices that do not overlap, or at mismatched `SpatialLevel`s
  - Calling `cross_level_align` with a malformed or partial injected mapping

Red team tests are expected to fail the system until weaknesses are addressed.

---

### 🟫 Beige Team Tests — Realistic, Neutral Usage

Beige team tests focus on **boring, realistic, non-adversarial usage patterns** that are neither friendly nor hostile — but still dangerous if mishandled.

- **Goal:** catch failures caused by normal consumer behavior
- **Mindset:** *“What will a real consumer repo actually do?”*
- **Project-grounded focus (planned):**
  - A consumer `save()`s a frame and `load()`s it back expecting an identical frame (round-trip)
  - A consumer aligns a prediction frame to an actuals frame with only partial overlap (silent-truncation risk, C-26)
  - A consumer `collapse()`s a multi-sample frame and assumes the trailing axis was reduced
  - A consumer treats a `mmap`-loaded frame as in-memory, or mutates a frame in place (forbidden; ops return new frames)
  - The same code path running against cm and pgm `SpatialLevel`s

Beige team tests are mandatory for any consumer-facing component — which, for a leaf, is
all of it.

---

### 🟩 Green Team Tests — Supportive, Resilience-Oriented Testing

Green team tests focus on **ensuring the system works as intended** under expected conditions and degrades safely.

- **Goal:** ensure reliability, robustness, and trustworthiness
- **Mindset:** *“How do we make this solid?”*
- **Project-grounded focus (planned):**
  - **Property tests for `SpatioTemporalIndex` alignment laws:** intersection is commutative; `align` then `collapse` == `collapse` then `align`; reindex is idempotent on a superset (README §9)
  - **Copy-vs-view memory property:** `with_metadata` and contiguous `select` return frames that **share** the `values` buffer (numpy view / zero-copy); a `mmap`-backed frame stays `mmap`-backed; only `collapse` allocates, and only the reduced array (README §3.3)
  - Round-trip save/load and `io/arrow` flat-columnar round-trip preserve the frame exactly
  - `collapse(method="arithmetic_mean")` reduces the trailing sample axis to `(N, 1)`
  - Construction-time validation accepts every valid frame and rejects every invalid one

Green team tests are expected to pass continuously and form the backbone of CI.

---

## The Conformance Suite and Falsification Stubs

Two test artifacts are specific to this leaf:

- **Published conformance suite (`tests/conformance/`).** A *published*, importable set of
  contract tests asserting the invariants of each Protocol (round-trip save/load,
  identifier completeness, collapse semantics, alignment laws). **Every consumer repo
  re-runs it in CI against its own adapters** — this is the missing cross-repo contract
  test (C-30) and the safety net that lets the frames evolve without silently breaking N
  repos. It must ship as an installable artifact against a governed **conformance-floor**
  version (README §13b.4); how that ships is still open.
- **Falsification stubs (`tests/`).** TDD-red enforcement artifacts generated by
  `/falsify` audits, each encoding an unresolved finding from the critiques / risk
  register. A stub is expected-red until the finding it encodes is resolved and **must not
  be deleted to make a gate pass** — it turns green only by fixing the finding.

No mocks are needed: frames are pure value objects over numpy. If a test needs a mock, the
thing under test probably does not belong in this leaf.

---

## Relationship to Other ADRs

This ADR reinforces and operationalizes:

- **ADR-001 (Ontology):** tests must respect declared categories and stability (never assume a metadata schema the leaf disclaims)
- **ADR-002 (Topology):** tests must not bypass architectural boundaries (no `views_*` import sneaking in via a test fixture)
- **ADR-003 (Authority & Semantics):** tests must assert loud failure at construction on missing/ambiguous identifiers
- **ADR-004 (Deferred):** future evolution rules must account for the conformance-floor coverage obligation

Testing is a primary mechanism by which these ADRs are enforced.

---

## Enforcement Rules

- Code that meaningfully affects behavior **must not be merged without tests**
- Tests that only cover happy paths are insufficient
- Warning-only behavior in tests is unacceptable for decision-relevant semantics
- If a failure mode is known and untested, it is considered technical debt and must be tracked in the technical risk register (ADR-010)

The absence of appropriate tests is valid grounds for blocking a change.

---

## Consequences

### Positive
- Reduced risk of silent failure
- Earlier detection of misuse and misunderstanding
- Increased trustworthiness of outputs
- Clearer system boundaries and guarantees

### Negative
- Higher upfront development cost
- Slower iteration if tests are neglected
- Requires cultural discipline and reviewer enforcement

These costs are accepted intentionally.

---

## Notes

Testing in this repository is not merely about correctness.

It is about **preventing silent harm in a contract that N repos trust**. As of v1.1.0
this ADR describes a realised suite — 225 tests, a CI **100% line+branch** coverage gate
(`--cov-fail-under=100`, `branch = true`), and the red/beige/green taxonomy applied across
`src/`; the published conformance suite is itself part of the deliverable.
