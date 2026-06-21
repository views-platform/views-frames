# Critique 01 — `views-frames` design package

> **Source:** independent reflection on the four design documents as they stood on
> 2026-06-20 — `README.md` (the design bible) plus the three consumer perspectives
> (`from_views-pipeline-core_perspective.md`, `from_views-reporting_perspective.md`,
> `from_views-datafactory_perspective.md`). Reviewer: Claude (Opus 4.8), reflection
> mode — **no code or docs changed, no risks registered.** This is an assessment.
>
> **Relationship to `critique_00.md`:** this pass was performed independently and
> then reconciled against `critique_00.md`. The two converge on the core findings
> (see §1). That convergence is treated as a confidence signal, not a reason to
> repeat: this document restates the shared findings compactly (so it stands alone)
> and spends most of its length on **net-new material §3–§6** that `critique_00`
> does not cover — the memory cost of immutability, identifier-set extensibility,
> the conformance-suite versioning paradox, a worked twin-unification trade-off, a
> methodological caveat about the perspectives, and the portfolio/WIP question.

---

## 0. Verdict

The **thesis is correct and the architecture is sound** — one of the better-reasoned
internal-library designs in this platform. The risks are not in the idea; they are
in **scope discipline, two load-bearing unresolved decisions, one latent
contradiction, and an unaddressed governance/coordination cost.** The meta-danger
is that a design this rhetorically complete can pre-empt the harder *"build less,
and decide the two hard things first"* question by sheer momentum.

Build it — but ship a deliberately minimal v1, close the two platform-breaking
decisions before relocating anything, fence the leaf against domain data, and name
an owner before the second repo takes the dependency.

---

## 1. Convergence with `critique_00` (high-confidence core findings)

Two independent reflection passes landed on the same load-bearing joints. Treat
these as settled-enough-to-act-on:

| # | Finding | This doc | critique_00 |
|---|---------|----------|-------------|
| A | `SpatioTemporalIndex` is the real product, and its hardest case (cross-level cm↔pgm join) needs domain data the leaf forbids — a latent contradiction, and it is **not** in the §13 open-decisions list. | §2.3 | §1 |
| B | `MetricFrame` breaks the §4 frame definition (`(K,…)` keyed by `(target,step,unit)`, not `(N rows, {time,unit})`); it is the least frame-like member yet the one reporting pulls hardest on. | §2.2 | §2 |
| C | The headline reporting win (C-48) is repeatedly admitted *not* solved by frames alone — it needs a cross-repo run-identity decision. The docs are honest about this but it undercuts the "headline." | §2.6 | §3 |
| D | "Move `PredictionFrame` verbatim" (§10.2) collides with "unify the twins" (§4.1) and with the unresolved sample-axis convention — you cannot move verbatim *and* unify *and* defer the S=1 decision. | §2.1 | §4 |
| E | The unified twin base is under-specified exactly where the twins differ (`feature_names`, `metadata`, feature axis, save/load sidecars). | §2.1, §3.1 | §5 |
| F | `SpatialLevel` relocation is a slippery slope toward the leaf absorbing domain vocabulary; mark the boundary. | §2.3 | §6 |
| G | Governance asymmetry / ownership unaddressed; "buildable against this doc" slightly oversold. | §2.5, §3.4 | §8 |

If `critique_00` and this document disagree anywhere, it is one of emphasis, not
direction: I rank **the twin-unification asymmetry (D/E)** and **the
governance/coordination gap (G)** as the two most likely to actually derail
delivery, slightly above the index-purity framing that `critique_00` leads with.

---

## 2. The core findings (restated so this document stands alone)

### 2.1 The twin "unification" is asserted near-1:1 but is genuinely asymmetric — and it is parked, not resolved
`FeatureFrame` carries `feature_names` + `metadata` + a feature/channel axis
`(N,F[,S])`; `PredictionFrame` is `(N,S)` with neither (README §4.1; datafactory
perspective §3.1, asks #1–#2). The shared core must therefore carry fields only one
twin uses. That forces a fork the README does not take: the unified base either
**bloats to satisfy both — a mini-god-class, the exact thing §5 bans** — or stays
genuinely separate and the de-duplication buys less than the thesis promises. This
is the keystone decision and it is buried in §13.5 + a perspective ask. Resolve it
**before** relocating either twin. (Worked options in §4 below.)

### 2.2 `MetricFrame` breaks your own frame definition — keep it out of the leaf
§4 opens: "a frame = a numeric array whose first axis is N rows, each carrying
`{time, unit}`." `MetricFrame` is `(K,…)` keyed by `(target, step, unit)` — a
different shape and key space. It is the least frame-like member, yet reporting
leans on it hardest (its C-48 "headline"). The pull to build it will be strong and
will stretch the abstraction toward a junk-drawer-of-Frames. Recommendation: keep
it out; let evaluation outputs live with `EvaluationFrame` in **views-evaluation**
(which already owns the eval-output vocabulary, README §4.2). If it must exist,
give it a crisp argument for why it is the *same* abstraction — the current docs do
not.

### 2.3 cm↔pgm cross-level alignment is a Trojan horse in the leaf
Three asks (pipeline-core #3, reporting #2, README §4.3) want `SpatioTemporalIndex`
to do country↔grid joins, "not just same-level intersection." But a cross-level
join requires the **GAUL/PRIO-GRID nesting** — *geographic reference data*, i.e.
exactly the domain knowledge §3 forbids (no app logic, no fetching, numpy-only).
The contradiction: consumers want hierarchy alignment in the leaf; hierarchy
alignment cannot be pure-numpy-no-domain-data. **Draw the line explicitly:**
same-level alignment (`intersect`/`reindex`/`searchsorted` over identical level)
lives in the leaf; cross-level hierarchy join stays in a consumer that owns the
reference data. Otherwise the leaf silently grows a domain dependency and stops
being a leaf — and the §11 scope boundary is quietly violated on day one.

### 2.4 "Maximally stable" vs. "6 open decisions + 4 anticipated frames" is in tension with itself
Stability is the package's entire reason to exist (SDP/SAP), yet §13 still has
load-bearing unresolved decisions — the **sample-axis convention (S=1 explicit vs
absent)** and the **metadata schema** — either of which, changed later, forces a
MAJOR bump across *every* consumer. These two are on the critical path and must
close **before** the first relocation, not "before/at first code." Everything else
in the anticipated family (`WeightFrame`, `MaskFrame`, `MetricFrame`) should be
resisted until a real consumer forces it. The docs preach this (§4.2, §10) but the
perspectives' gravity pulls the other way.

### 2.5 The governance / ownership gap is the largest unaddressed cost
§8 covers SemVer *mechanics* but not the *organizational* reality: a leaf that 6+
repos import needs a **named owner, a release cadence, and a process for the day a
MAJOR bump must land across 6 repos at once.** That coordination — not the code —
is the real expense, and it is nearly silent. Who owns the keystone? That answer
gates whether the strangler plan is real or aspirational. (See also §3.4: the
conformance suite has its own version-coordination problem.)

### 2.6 The README-as-normative-contract is itself a risk
~1,400 lines of prose, zero code, with "if code and README disagree, reconcile
before merging." Prose specs ossify decisions that belong in code and then drift.
**Make the conformance suite the source of truth as early as possible**; demote the
README to explanation. The wall-to-wall SOLID-acronym citation (SDP, SAP, ADP, REP,
CRP, ISP, DIP, LSP, OCP, SRP, CCP) is mostly earned, but it occasionally tips into
justification-by-acronym — the design is right *on the merits*, independent of the
principle names, and should be defended that way.

---

## 3. Net-new findings (not in `critique_00`)

### 3.1 Immutability trades object-dtype bloat for copy bloat unless copy semantics are specified
The memory thesis (object-dtype is ~50–160× dense; ban list-in-cell) is the
package's empirical spine. But §3.3 mandates **immutability — every operation
returns a *new* frame.** For the very tensors that motivate the package (full grid
× full timeline × S, the 9–18 GB regime in #181/C-186), naïve immutability means
*every* `select`/`with_metadata`/`collapse` risks a full **copy** — trading the
object-dtype non-scaler for a copy non-scaler. Immutability is correct for
correctness (it forbids the C-184 mutation), but the contract must specify **copy
semantics**: structural ops (`with_metadata`, metadata-only changes, `select` on a
contiguous slice) should return frames that *share* the underlying `values` buffer
(numpy views / zero-copy), and `load(mmap=True)` must propagate so peak RAM stays
the working set. Otherwise the design's own §7 scaling guarantee is undercut by its
own §3.3 immutability rule. **Add an explicit "copy vs view" subsection to the
serialization/operations contract** — this is exactly the kind of thing the prose
spec leaves implicit and the conformance suite must pin (a property test:
`with_metadata` does not allocate a second `values` buffer).

### 3.2 The (time, unit) identifier set is probably too narrow, and every widening is a platform-wide MAJOR bump
README §8 names "adding a required identifier" as *the* canonical breaking change —
yet the document simultaneously surfaces strong latent pressure for more
identifiers:
- ensemble / forecast **origin** and **scenario** axes (the reconciliation and
  ensemble paths distinguish runs/origins);
- `MetricFrame`'s `(target, step, unit)` keying (a `step`/lead-time axis);
- the **provenance / run-identity** the #178 work and reporting's C-48/C-34 demand
  in metadata.

So the most likely future change is precisely the most expensive one. Two
mitigations the design should decide *now*, at v1: (a) treat `metadata` as a
*typed, optional-extensible* header rather than free-form dict, so provenance/origin
can be added as MINOR (optional) not MAJOR (required); and (b) decide whether the
identifier model is a fixed `{time, unit}` or an **open mapping** validated against
a required *subset* — the latter lets `step`/`origin` ride as optional identifiers
without a MAJOR bump. The current "REQUIRED_IDENTIFIERS = {time, unit}" + free-form
metadata leaves the package one realistic requirement away from a coordinated
6-repo break.

### 3.3 The serialization contract is asymmetric across the twins and the asymmetry is unspecified
`PredictionFrame.save` = `y_pred.npy` + `identifiers.npz`. `FeatureFrame.save` =
`y_features.npy` + `identifiers.npz` + `feature_names.json` + `metadata.json`
sidecars (datafactory §3.1, ask #2). The unified `io/npz.py` must therefore handle
frame types with *different on-disk footprints*, and datafactory explicitly asks
that frame-level fields "serialize with the frame, not require an adapter." This
collides with §6's "serialization is not the frame's job / I/O lives in `io/`."
Decision needed: does `io/npz` know about `feature_names`/`metadata` (coupling the
I/O layer to per-frame schema, weakening SRP), or does each frame expose a
`__frame_state__`-style contract the generic saver round-trips (cleaner, but a new
protocol)? Pick the second, and add it to the `Persistable` protocol — otherwise
`io/` accretes per-frame special cases, recreating a mini `handlers.py`.

### 3.4 The conformance suite has a version-coordination paradox
§9 makes the conformance suite the "missing cross-repo contract test (C-30)" — each
consumer runs it in CI. But the suite ships *with* the package, and consumers pin
*different* versions (datafactory §9 pins `>=1.0,<2`). A v1.4 consumer running v1.4
conformance and a v1.1 consumer running v1.1 conformance are **not testing the same
contract** — drift between consumers is exactly what is *not* caught. The suite
catches "does my adapter satisfy *my pinned* version," not "do all consumers agree."
To actually close C-30 you need a governed rule: a single **conformance floor**
version all consumers must run in CI regardless of their runtime pin, bumped
deliberately. This is a governance artifact (§2.5), not a test-file. Name it.

### 3.5 The leaf cannot fail-loud on temporal sanity — a small erosion of §3.4
Datafactory ask #6 (correctly) makes `time` an **opaque integer** (epoch-agnostic).
Good for decoupling — but it means the leaf's §3.4 "fail loud at construction"
cannot validate that `time` is a plausible VIEWS month_id (range, monotonicity,
epoch). The contract guarantees *structural* validity (integer, length-N, no NaN)
but not *temporal* validity; that check necessarily lives in a producer adapter.
Worth stating explicitly in §3/§3.4 so consumers do not assume the frame's "valid
identifiers" guarantee includes temporal sanity — a silent gap otherwise.

### 3.6 Naming collision on the central type
`SpatioTemporalIndex` (leaf) overloads two loaded terms already in the platform's
vocabulary: pandas `Index`/`MultiIndex` (the very thing this replaces) and
datafactory's `SpatioTemporalGrid` (a *different* concept — fixed 360×720 backbone,
not a row identifier; datafactory ask #4 flags the confusion). A central type
should not share a name with both the thing it abolishes and a sibling production
concept. Consider a less collision-prone name (`RowIndex`, `FrameIndex`,
`UnitTimeKey`); cheap now, a rename-across-6-repos MAJOR bump later.

### 3.7 Concentration risk: views-frames is a single point of coordination failure
The §12 list is long — views-frames is load-bearing for ~12 register items across
3+ repos (C-36, C-40, C-66, C-186, C-48, C-135, C-164, C-165, C-167, C-184, #113,
D-28, D-33). That breadth is a strength (one keystone repays many debts) *and* a
concentration risk: if views-frames slips, stalls on an open decision, or churns
its contract, it blocks **all** of those efforts at once. The "enables vs solves"
honesty mitigates over-claim but not concentration. This argues again for a
minimal, fast, stable v1 that de-risks the *common* dependency before the dependent
efforts queue behind it.

---

## 4. Worked analysis — the twin-unification fork (the §2.1/finding-E decision)

The document asserts unification but never works the options. Three are viable:

**Option A — one shared concrete base (`_FrameBase`) the twins extend.**
- *Pros:* maximal code sharing; one validation path; one save/load.
- *Cons:* the base must carry `feature_names`, `metadata`, feature axis, sample
  axis to serve both → it accretes everyone's fields → **this is `_ViewsDataset`
  /`_BaseFrame` reborn (the C-36 anti-pattern §5 explicitly bans).** Reject.

**Option B — composition + protocols (the README's stated intent).**
- Each frame is a sibling that *composes* a `SpatioTemporalIndex` and a shared
  `_validation` helper, and *satisfies* `Frame`/`Sampled`/`Persistable`.
- *Pros:* no fat base; LSP via protocol conformance; twins stay small; new frames
  drop in via OCP.
- *Cons:* the genuinely-shared mechanics (identifier validation, npz round-trip,
  collapse) must live *somewhere* — as free functions / a mixin / the index object.
  The risk is the "small `_validation` helper" quietly becoming the god-class
  through the back door. The discipline that prevents A's failure must be actively
  enforced here, not assumed.
- *Verdict:* **correct choice, but only if `feature_names`/`metadata` are modeled
  as the index/metadata carries them, not as base-class fields.** Concretely:
  `metadata` (incl. `feature_names`) is a typed header object composed by *each*
  frame that needs it; `PredictionFrame` simply has an empty/None header.

**Option C — do not unify the concretes; unify only `SpatioTemporalIndex` +
protocols; leave `FeatureFrame` and `PredictionFrame` as separate classes that both
import the shared index/validation.**
- *Pros:* honest about the asymmetry; smallest leaf; lowest churn; the *real* shared
  primitive (index) is still de-duplicated.
- *Cons:* the §1 "diverging twins (REP)" pain is only *partly* solved — the two
  classes still exist in two files (now both in the leaf), so they can still drift
  in their *class* surface even if the index can't.
- *Verdict:* **underrated.** The document treats "unify the two frame classes" as
  the goal, but §4.3 itself argues the *index* is the real reused core. If that is
  true, Option C captures ~80% of the value (shared index + validation + protocols +
  single release cadence, since both now live in one repo) at a fraction of the
  base-class risk. **Option C is the safer v1; Option B is the v2 if a measured
  need to share more than the index appears.**

**Recommendation:** ship **C** (shared `SpatioTemporalIndex`, `_validation`,
protocols, `io/npz`; twins relocated as *separate* classes), and adopt **B**'s
composed-metadata-header only if/when a third frame proves the header is reused.
Explicitly *reject* A in the README so no PR drifts toward it.

---

## 5. Methodological caveat — the perspectives may be one author simulating three

The three perspective docs are the package's best feature *and* carry a hidden
assumption. They read as if written *by* pipeline-core, datafactory, and reporting —
but their uniform structure, shared idioms ("the honest line," "TL;DR for a hurried
reader," identical section skeletons), and cross-referential consistency strongly
suggest **one author wrote all three** (almost certainly AI-assisted, like the
README). That is not disqualifying — it is a good way to pressure-test a design from
multiple angles — but it means the perspectives are *simulated stakeholder views,
not elicited ones*. Their internal consistency is partly an artifact of single
authorship, not evidence that the owning teams agree.

The real test is **endorsement**: does the actual datafactory team accept that
`from_grid()` becomes an adapter and that taking a first cross-repo dependency is
worth it? Does reporting accept that `MetricFrame` is "exploratory," not their
promised C-48 fix? Until each perspective is *ratified by its repo's owner*, treat
them as the proposer's hypotheses about the consumers, not consumer commitments.
Recommend: add a one-line "**Ratified by:** <name/date>" header to each perspective,
and do not count an unratified perspective as stakeholder buy-in.

## 5b. Missing perspectives (the two that would stress the riskiest claims)

Three perspectives exist (pipeline-core, datafactory, reporting). The two **absent**
ones are precisely those that would test findings B and D/E hardest:
- **views-evaluation** — it *owns* `EvaluationFrame` and would *produce*
  `MetricFrame`. The most confused boundary in the whole design (§2.2) has no voice.
  Its perspective should be written *before* `MetricFrame` is promoted from
  "exploratory."
- **a model / engine repo** (hydranet, bayesian, stepshifter) — they implement
  `_forecast_model_artifact() -> PredictionFrame` and are the *production* end of
  the contract. Whether the engine extension points actually want this typed return
  (pipeline-core ask #5) is untested without one of them speaking.

(views-postprocessing — the repo currently mid-migration on the un_fao path — is a
third absent consumer, though a lower-priority one for this contract.)

---

## 6. Portfolio / sequencing — the WIP question

`critique_00` §8.1 notes views-frames is "the same architectural move as
views-appwrite." Push that further into a **portfolio** observation: the platform
now has *at least three* concurrent cross-repo initiatives competing for the same
scarce resource — **cross-repo coordination budget**:

1. the live **viewser → views-datafactory** data-source migration (in flight);
2. **views-appwrite** (a zero-code roadmap to extract the shared Appwrite client);
3. **views-frames** (this — extract the shared data contract).

All three are "extract/replace a thing that N repos depend on," all three touch
datafactory and pipeline-core, and all three require the same merge-train +
shim + conformance discipline across the same repos. Running them concurrently
multiplies the coordination surface and destroys change attribution (if a number
moves, was it the data migration, the Appwrite swap, or the frame relocation?).

**Sequencing judgment:** views-frames is the **highest-leverage** of the three (it
unblocks #113, C-186, the eval boundary, and de-duplicates two real twins) — but
leverage is not the same as urgency, and it is the **largest coordination load**.
Recommend an explicit WIP limit: do not have views-frames' *relocation* phase and
views-appwrite's *extraction* phase in flight in the same repo (pipeline-core,
datafactory) at the same time. The data migration should reach a stable baseline
first (per the separate migration analysis), because it is the only one of the
three that changes *data values* and therefore most needs a clean attributable
diff. views-frames v1 (the index + twins, behavior-preserving) can proceed in
parallel *only* because it is contract-preserving — but its *consumer adoption*
should queue behind the data migration's baseline.

---

## 7. Prioritized recommendations

**Blocking (resolve before first relocation):**
1. Close the **sample-axis convention** (S=1 explicit vs absent) — it is the single
   decision most likely to force a platform-wide MAJOR bump (§2.4, finding D).
2. Decide the **twin-unification model** — recommend Option **C** (§4); reject the
   shared concrete base in writing.
3. Decide the **metadata/identifier model** as *typed-optional-extensible* so
   provenance/origin/step can be added as MINOR, not MAJOR (§3.2).
4. **Fence the leaf:** same-level alignment in; cross-level cm↔pgm join and
   `MetricFrame` out (to consumers / views-evaluation) (§2.2, §2.3).

**Major (resolve before second consumer adopts):**
5. Name an **owner + release cadence + conformance-floor policy** (§2.5, §3.4).
6. Specify **copy-vs-view semantics** for frame operations and propagate `mmap`
   (§3.1) — pin it in the conformance suite.
7. Make the **conformance suite the contract**; demote the README to explanation
   (§2.6).

**Minor / cheap-now:**
8. Rename `SpatioTemporalIndex` to avoid the pandas-Index / datafactory-Grid
   collision (§3.6).
9. State explicitly that the frame's identifier guarantee is *structural, not
   temporal* (§3.5).
10. Add a **"Ratified by"** header to each perspective; write the **views-evaluation**
    and a **model-repo** perspective before promoting `MetricFrame` (§5, §5b).

**Portfolio:**
11. Set a WIP limit: do not run views-frames relocation + views-appwrite extraction
    in the same repo concurrently; queue consumer adoption behind the data-migration
    baseline (§6).

---

## 8. Open questions for the authors

1. Is the goal to unify the *frame classes* or the *index*? If §4.3 is right that
   the index is the reused core, why not Option C (§4)?
2. What is the smallest v1 you would ship and *stop* — and does it include any of
   the anticipated family, or only `SpatioTemporalIndex` + the two twins + `io/npz`?
3. Who owns the repo, and what is the process for a MAJOR bump that must land across
   6 repos simultaneously?
4. Where does the cm↔pgm hierarchy mapping live, given the leaf forbids domain data
   (§2.3)?
5. Have the datafactory, reporting, and (absent) evaluation owners *ratified* their
   perspectives, or are these the proposer's hypotheses (§5)?
6. Given the concurrent migration and views-appwrite work, what is the intended
   *sequence* and WIP limit across the three cross-repo initiatives (§6)?

---

*This is a critique, not a patch. No code, docs, or registers were changed. A
`/falsify` pass against specific load-bearing claims (e.g. "the index is pure
numpy," "the twins are near-1:1," "frames are immutable without copy cost") is the
natural next step and would convert the §2–§3 findings into failing-test stubs.*
