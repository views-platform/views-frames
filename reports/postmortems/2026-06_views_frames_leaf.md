# Postmortem — `views_frames`, the data-contract leaf (v0.1.0 → v1.4.0)

| Field | Value |
|---|---|
| Subject | The leaf data contract: a numpy-only, immutable array+identifier value-object library at the root of the VIEWS dependency DAG — its constitution-first design, its freeze, and the boundary fights it provoked |
| Window | 2026-06-21 (`v0.1.0`, Epic 2) → 2026-06-24 (`v1.4.0`, provenance + envelope checker). The frozen v1.0 surface (ADR-018) has been unchanged since 2026-06-21. |
| Repos | `views-frames` (all code lives here); consumers `views-faoapi`, `views-pipeline-core`, `views-hydranet`, `views-baseline`, `views-reporting`, `views-evaluation` (each pins the leaf) |
| Governing docs | Constitutional ADRs 000–010; project ADRs 011–016, 018, 020; the conformance suite (ADR-005/016); README design bible; register C-01..C-31 (the design + first-code cluster) |
| Outcome | A small, stable, **provably pure** (import-DAG-enforced) leaf that froze at v1.0.0 and has carried two sibling packages and four consumers without a single breaking change. The leaf itself shipped almost no correctness bugs; every real defect lived at its *boundary* — what a consumer or a sibling leaked into it. The recurring tax was tooling (numpy-version mypy/determinism skew), not design. |

---

## 1. What we did, and why

The VIEWS platform's scaling failure was a **list-in-cell `object`-dtype DataFrame** — a pandas
cell holding a Python list of `S` posterior samples — measured at ~33× memory blow-up over dense
`float32` (register C-40/C-66) and the root cause of the report-stage OOM (#181). Worse, the
"prediction frame" concept was re-implemented, subtly differently, in every repo that touched
forecasts. There was no single, stable, dependency-light definition of *"an array aligned to
`(time, unit)`"* that the whole platform could agree on.

`views_frames` is the answer: a **numpy-only** library of immutable array+identifier value objects
— `PredictionFrame (N, S)`, `TargetFrame (N, 1)`, `FeatureFrame (N, F, S)`, sharing a
`SpatioTemporalIndex {time, unit, level}` — that **depends on nothing internal** and sits at the
root of the dependency DAG, so every other repo can depend *toward* it without a cycle. The design
was settled before any code: a design-bible README, eleven constitutional/project ADRs, and a set
of falsification stubs, all ratified up front (Epic 1), then realised in Epic 2.

The bet was deliberately conservative: make the contract **small, abstract, immutable, and frozen**,
push everything volatile (statistics, IO formats, domain geography) *out* of it, and enforce the
purity mechanically so it can never rot into a god-library. The whole platform's stability would
rest on this one package not changing underneath it.

## 2. How it unfolded — the arc

- **Design first (Epic 1).** The README design bible + ADRs 000–010 (the constitution) and the six
  contract decisions (ADRs 011–016) were ratified *before code*: twin-unification as **Option C**
  (frames are separate sibling classes sharing only `SpatioTemporalIndex` + `_validation` +
  protocols + `io`; **no shared base** — ADR-011, register C-16/C-03); the **sample axis** as an
  always-explicit trailing `S ≥ 1` (ADR-012); a **typed, optional-extensible metadata header** with
  fixed `{time, unit}` identifiers (ADR-013); cross-level cm↔pgm alignment as a **consumer-injected
  mapping**, never embedded or fetched (ADR-014); `SpatialLevel` as identifier vocabulary only
  (ADR-015); and a **governed conformance floor** every consumer re-runs in CI (ADR-016).
- **v0.1.0 (Epic 2, 2026-06-21).** `SpatioTemporalIndex` + `_validation` + `cross_level_align`; the
  three frames + `FrameMetadata`; `io/npz` (mmap) + `io/arrow` (flat-columnar parquet — the *only*
  place `pyarrow` may be imported); and the **published conformance suite** + property tests +
  falsification stubs. The import-DAG test (`tests/test_import_enforcement.py`) was wired from the
  start as the executable form of ADR-002.
- **v0.2.0 / v0.3.0.** The summarize sibling was carved off (ADR-017 — its own postmortem); the leaf
  got a **time-aware, vectorized `cross_level_align`** (`(time, unit)`-keyed, register C-20), the
  columnar `cross_level_align_arrays` for grid scale (C-26), `select`/`reindex` frame ops, and a
  string of numpy-floor hardening fixes (C-19/C-23/C-24/C-25).
- **v1.0.0 — the freeze (ADR-018, 2026-06-21).** After a second round of consumer review, the public
  surface was frozen and `CONFORMANCE_FLOOR` set to `1.0.0`. PyPI Trusted Publishing was stood up.
  From here, **everything is additive** (MINOR) or a fix (PATCH); the frozen surface never changes.
- **v1.0.1.** Test hardening (Epic 6) — protocol runtime-conformance assertions (C-37), IO
  red-team paths (C-29), branch-coverage gate (C-36). No API change.
- **v1.4.0 (2026-06-24).** The one substantive *leaf* addition after the freeze: generic provenance
  on `FrameMetadata` (`run_id` / `data_version`) and a **published `assert_frame_envelope`** checker
  (ADR-020, register C-46/C-47), plus the C-51 direct reject-path tests. Additive; floor stayed
  `1.0.0`. (ADR-020 also ratified that the `MetricFrame` evaluation-output contract stays *out* of
  the leaf and lives in views-evaluation on the leaf's substrate — a boundary defence, not a feature.)

## 3. What went well

- **Constitution-first paid off.** Settling eleven ADRs before code felt heavy, but it meant every
  later question (`where does reconciliation live?`, `can a magnitude rule sit in the leaf?`, `is
  `MetricFrame` ours?`) had a ratified principle to answer it. The two sibling packages (summarize,
  reconcile) and the ADR-020 boundary defence are all *applications* of ADR-001/014/017, not new
  arguments.
- **The import-DAG test is the leaf's spine.** `FORBIDDEN = {pandas, polars, geopandas, wandb,
  viewser, torch}` + a per-package allow-list, asserted by AST scan in CI, makes "the leaf is pure"
  an executable, non-negotiable fact rather than a guideline. It has never had to fail loudly —
  which is the point; it shapes what people even attempt.
- **The freeze held — completely.** `CONFORMANCE_FLOOR` has been `1.0.0` across **seven** subsequent
  releases (v1.1–v1.7). Two sibling packages and provenance all landed as additive surface. No
  consumer has ever eaten a breaking change. For an N-repo contract, this is the whole value
  proposition, delivered.
- **Conformance-as-a-published-artifact works.** ADR-016's "one contract, N consumers, each runs the
  suite in its own CI" is real: `views-faoapi` re-runs `assert_frame_contract` +
  `assert_summarizer_contract` + the cross-level alignment law on its *own* real frames and injected
  GAUL mapping. The contract is checked end-to-end at the boundary, not just in the leaf's own tests.
- **Honesty over symmetry.** ADR-011's "no shared base" (Option C) resisted the tempting `_BaseFrame`
  god-class. The frames are ≥6-axis divergent (C-16); forcing a base would have created exactly the
  dumping-ground the package exists to avoid. Three small sibling files beat one clever hierarchy.
- **Fail-loud, structural, at construction.** Invariants raise `ValueError`/`TypeError` at build
  time (ADR-008/009); the guarantee is *structural*, not temporal (`time` stays opaque). This is
  what lets a downstream repo trust a frame it received without re-validating it.

## 4. What went wrong, and what we missed

- **The numpy-version tooling tax was underestimated, and it never fully went away.** A numpy-only
  leaf is checked under at least two numpy worlds — the **floor** (1.26.4, stricter generic stubs)
  and the **ceiling** (2.x). They disagree, in *both* directions: the floor flags `type-arg`
  (bare `np.floating`/`np.integer` need a parameter); the ceiling flags `no-any-return`. This bit at
  v0.1 (`argsort` typing, C-19; the floor mypy job had to be added), bit again on determinism
  (~1-ulp histogram binning differences forced a deterministic tie-break, C-24), and bit *yet again*
  on the reconcile port two weeks later — the same class of bug, freshly rediscovered. **We never
  turned "run mypy at both the floor and the ceiling" into a reflex that precedes every push.**
- **Coverage that was line-only hid untested branches (C-36).** The 100% gate initially measured
  lines, not branches; a conditional could be "covered" with one outcome untested. Real on a leaf
  whose whole job is fail-loud guards. Fixed by switching to branch coverage — but it was a latent
  hole in the very thing (testing) the leaf treats as critical infrastructure (ADR-005).
- **Reject paths were tested only transitively (C-51).** `assert_frame_envelope`'s structural
  rejections (non-float32, object dtype, wrong ndim) were exercised *through* the higher-level
  contract, not by direct adversarial tests. 100% coverage is not the same as "every documented
  failure mode has a dedicated red-team test." We learned this twice (C-29 on IO, C-51 on the
  envelope).
- **The docs drifted from the code almost immediately (C-39/C-23/C-35).** Stale CIC signatures,
  fossil examples, a README "Status" header still saying v1.0.0 after v1.1.0 shipped. The design
  bible is load-bearing ("if code and README disagree, that is a bug") — but keeping it true needs a
  validator run every release, which we only systematised after it had already drifted.
- **The first-publish PyPI token was account-wide (C-28).** An over-privileged credential on the
  very first release. Migrated to Trusted Publishing (OIDC, no token) — but it shipped first and was
  fixed after.

## 5. What surprised us

- **The leaf itself was almost bug-free; the danger was always inbound.** We braced for subtle
  correctness bugs in the contract. There were essentially none. Every real defect in the *family*
  (the tower's C-44/C-45, the summarizer's NaN/`inf` guards) was a **domain or shape assumption
  leaking across the boundary** — usually into a sibling, occasionally pushed back at the leaf
  (the `MetricFrame` question, ADR-020). The leaf's constitution was right; the violations happened
  where the constitution was *not applied*.
- **The hardest design call was about asymmetry, not symmetry.** The instinct to unify the "twin"
  frames under a base class was strong and wrong. Naming their ≥6 divergence axes (C-16) and
  choosing three honest siblings over one false abstraction was the decision that aged best.
- **"Declare, don't infer" (ADR-003/014) turned out to be the load-bearing principle.** The leaf
  never embeds or fetches geography; the consumer injects the time-varying mapping. Every later
  effort that respected this stayed clean; the one place a sibling *violated* it (a hard-coded
  magnitude threshold) became a production bug. The principle wasn't decoration — it was the fault
  line.

## 6. What would be easier next time

- **Run the full mypy matrix (floor *and* ceiling) as a pre-push reflex, from commit one.** The
  single most repeated failure in this family is "local mypy green, CI floor/ceiling red." It is a
  two-command check; make it muscle memory, not a thing rediscovered each effort.
- **Branch coverage and direct reject-path tests from day one.** For a fail-loud leaf, every
  documented failure mode deserves its *own* adversarial test, and the gate must be branch-level. Do
  not let "100% line coverage" stand in for "every guard is directly proven to fire."
- **Make the docs validator a release gate, not an afterthought.** `validate_docs.sh` + a
  README-status check should block release; doc drift on a design-bible repo is a correctness bug by
  the repo's own rule.
- **Keep settling boundary questions at ADR time.** The leaf's calmest moments came from having a
  ratified answer ready (ADR-020 for `MetricFrame`, ADR-017 for summarize, ADR-023 for reconcile).
  The expensive moments came from a principle that existed but went unapplied. Ask "does this concept
  belong here, by our own constitution?" *before* the code, every time.
- **Treat Trusted Publishing and least-privilege credentials as table stakes for release one**, not a
  follow-up.

## 7. Final state

`views-frames` is a stable, pure, frozen leaf. The v1.0 public surface (ADR-018) is unchanged;
`CONFORMANCE_FLOOR` is `1.0.0` and has been since the freeze. The import-DAG is enforced; the
conformance suite is published and re-run by consumers; provenance (`run_id`/`data_version`) and the
`assert_frame_envelope` checker (v1.4.0) are the only post-freeze leaf additions, both additive. The
design-decision cluster (C-01..C-31) is resolved; the leaf carries two sibling packages
(`views_frames_summarize`, `views_frames_reconcile`) without a cycle or a breaking change.

The one-sentence lesson: **a maximally-stable leaf earns its stability not by being clever but by
being frozen and provably pure — and the only forces that can still hurt it come from outside, when
a consumer or a sibling smuggles a domain assumption across a boundary the leaf's own constitution
already forbade.**
