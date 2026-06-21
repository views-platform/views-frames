# Critique 00 — `views-frames` design package

> **Source:** structured reflection on the four design documents as they stood on
> 2026-06-20 — `README.md` (the design bible) and the three consumer perspectives
> (`from_views-pipeline-core_perspective.md`, `from_views-reporting_perspective.md`,
> `from_views-datafactory_perspective.md`). Reviewer: Claude (Opus 4.8), reflection
> mode — no code or docs changed, no risks registered. This is the assessment, not
> a patch.
>
> **How to read it:** findings are ordered by importance, each grounded in a
> specific section. "Verdict" lines summarise. A follow-up `/falsify` pass is
> planned separately; this document is the human-readable critique that precedes it.

---

## 0. Overall verdict

This is a better-than-average design package, and it is the *same architectural
move* as the sibling `views-appwrite` repo: a maximally-stable, dependency-light
**leaf at the root of the DAG** that de-duplicates diverging twins and breaks
import cycles. The reasoning from the package-design principles (SDP, SAP, ADP,
REP, CRP, CCP) is rigorous and correctly applied; the grounding in *measured*
production pain (the #181 OOM with the 50–160× object-dtype figure; the 22/25
"not calculated" evaluation bug) is what most design docs lack. The
four-document structure — bible plus three perspectives, each carrying an
explicit *"what it does **and does not** fix"* line — is the strongest feature
and resists the usual keystone-package over-claim.

The critique that follows is therefore **not "this is wrong."** It is "here are
the load-bearing joints that are not yet resolved, and one of them is mis-framed."
The recurring theme: **the package's actual value sits in the two places the
documents are least decided (domain-purity of the index, and evaluation-output /
run identity), while the easy parts (relocating the twins) are the most fleshed
out.**

### What is genuinely strong (so the praise is on record)

- **The thesis is correct.** "DataFrames are a boundary/interop and analysis
  format, not internal transport" (README §0) is a sound, defensible position,
  and the doc follows it through consistently.
- **The dependency-graph reasoning is real, not decorative.** The leaf-at-root
  design genuinely does break the pipeline-core ↔ reporting cycle (#113) via ADP,
  and genuinely does de-duplicate the twins via REP. The "every internal arrow
  points toward views-frames" rule (§2) is the right invariant.
- **It is motivated by defects, not aesthetics.** Each problem in §1 carries a
  register ID and, for #181/C-186, a measured root cause with a micro-benchmark.
- **Intellectual honesty.** The "honest line" in every perspective (*solves X
  outright; enables Y but the cleanup is still yours*) is rare and valuable.
- **The hard constraints target the actual bugs.** Immutability (§3.3) directly
  forbids the C-184 cross-repo mutation; no-`object`-dtype (§3.5) directly
  forbids the list-in-cell encoding that is the measured non-scaler.

---

## 1. `SpatioTemporalIndex` is the actual product, and its hardest case is waved at

**Verdict: the single most important unresolved decision, and it is not in the
§13 open-decisions list.**

The README is explicit and correct that the real deliverable is the
identifier/alignment contract, not "a numpy wrapper" (§1 closing paragraph;
§4.3). But it files `SpatioTemporalIndex` and `SpatialLevel` under *"tiny,
stable value object"* (§4.3, §13.3) — and the one operation **both** downstream
consumers explicitly ask for is **cross-level cm↔pgm alignment** (country → its
PRIO-GRID cells):

- reporting perspective §8.2: *"the index must support cross-`SpatialLevel`
  alignment (country → its priogrid cells), not just same-level intersection."*
- pipeline-core perspective §9.3: *"`SpatialLevel` owns cm/pgm + cross-level
  (country↔grid) alignment … pipeline-core's reconciliation and ensemble
  aggregation both need the cm↔pgm join, not just same-level intersection."*

Cross-level alignment requires a **country→cells mapping**, which is
GAUL/PRIO-GRID hierarchy *reference data that versions over time*. That collides
head-on with two of the package's own rules:

- **"maximally stable"** (§2): a frame package carrying GAUL hierarchy inherits
  GAUL's update cadence — the opposite of stable.
- **"no domain data"** (§3 constraint 2; §11): that mapping is precisely
  domain reference data.

So there is a fork the document does not take:

- **(a) the cross-level mapping lives in the leaf** → the leaf is no longer purely
  stable/abstract, and it now has a non-trivial data-update lifecycle; or
- **(b) it stays in consumers** → the cross-level join (the thing of value) stays
  duplicated across reporting and pipeline-core, undercutting a core pitch of the
  package.

The §4.3 design heuristic — *"if two consumers disagree about how (time, unit)
align, that disagreement belongs here, resolved once"* — actively **invites the
domain data in**, while §3 forbids it. Those two statements need to be
reconciled explicitly, with a stated, defensible line between **"identifier
vocabulary"** (allowed) and **"hierarchy reference data"** (forbidden). cm↔pgm
alignment is exactly the case that tests where that line is, and it is the case
both consumers asked for.

**Recommendation:** add this as a blocking open decision. Likely resolution: the
leaf owns *same-level* alignment and the *protocol* for cross-level alignment,
but the country→cells **mapping table** is injected by the consumer (or lives in
a separate `views-domain`/reference package the leaf does not depend on). State it
either way before building `index.py`.

---

## 2. `MetricFrame` does not fit the frame abstraction it is placed in

**Verdict: a genuine conceptual mismatch; the highest-value reporting win rides on
the worst-fitting frame.**

Every frame is defined (§4) as *"a numeric array whose first axis is N rows, each
row carrying a complete set of spatiotemporal identifiers `{time, unit}`."*
`MetricFrame` is keyed by `(target, step, unit)` (§4.2) — its key axis is **not**
`(time, unit)`. A metric like CRPS for a `(target, step)` pair aggregated over
units and time has **no row-level spatiotemporal identity at all**. The claimed
shared core — `SpatioTemporalIndex` — therefore simply does not apply to
`MetricFrame`.

This matters because the reporting perspective leans on `MetricFrame` as *"the
type that fixes the worst thing `views-reporting` does"* (§3.3), while the README
correctly marks it merely *"exploratory"* (§4.2 priority column). The
highest-value consumer fix depends on the frame that fits the central abstraction
**least** — an unacknowledged tension.

**Resolution options (pick one explicitly):**

- Define a more general `Index`/key protocol that **both** `SpatioTemporalIndex`
  and a `MetricKey` (`(target, step, unit)`) satisfy. Then the package's "the
  shared primitive is `SpatioTemporalIndex`" claim must be **restated** at that
  higher level of generality.
- Keep `MetricFrame` **out** of this package and let `views-evaluation` own it
  alongside `EvaluationFrame` (the doc already declines to rebuild
  `EvaluationFrame`, §4.2 — `MetricFrame` is the same family of decision).

Silently treating `MetricFrame` as a peer frame with the others is the one thing
not to do.

---

## 3. The headline reporting win (C-48) is repeatedly admitted *not* to be solved here

**Verdict: honest, but it means the marquee reporting benefit is contingent on a
separate, currently-unowned cross-repo decision.**

C-48 (the confirmed 22/25 "not calculated" bug — the eval report scraping the
wrong WandB run) is one of the most prominent motivating defects (§1, §4.2, and
all over the reporting perspective). Yet:

- README §12: views-frames *"does **not** by itself resolve C-22 … or C-27 …
  `views-frames` only gives their output a typed home."* and the C-48 entry is
  about *enabling* the fix.
- reporting perspective §4: *"the run-identity / where-it-is-stored decision is
  **still cross-repo** — frames give it a home, they don't auto-resolve it."*
- reporting perspective §8.1: the **stamped, stable run/eval identity in frame
  metadata** is *"the single highest-value open decision"* from the consumer's
  view.

The thing that actually fixes C-48 is the **provenance / run-identity** decision
(README §13.5), which is currently buried as open-decision #5 and an "ask." If
that decision does not land, views-frames delivers materially less to reporting
than the framing implies.

**Recommendation:** promote provenance/run-identity from "open decision #5" to a
first-class part of the contract **or** explicitly scope C-48 out of what this
package claims to fix. As written, the document both features C-48 prominently and
disclaims it — pick one posture.

---

## 4. "Move verbatim" collides with "unify the twins" and with the sample-axis decision

**Verdict: three load-bearing statements cannot all hold at once; the sequencing
is unstated.**

These three cannot be simultaneously true:

1. **§10.2** — move `PredictionFrame` here **verbatim**, *preserve its contract*.
2. **§10.3 / datafactory §8.1** — unify with `FeatureFrame`, which carries
   `feature_names` + `metadata` that `PredictionFrame` lacks.
3. **§13.6** — decide the **sample-axis convention** once (is `S=1` an explicit
   axis or absent?) — which §13.6 *itself* says *"affects `collapse`, `is_sample`,
   and every shape check."*

You cannot relocate `PredictionFrame` unchanged **and** resolve a convention that
rewrites its shape semantics **and** fold it into a shared base that adds fields.
§10 reads as if the whole migration is back-compatible; §13.6 quietly contradicts
that for the sample-axis case.

The verbatim move (§10.2) is a fine **first** step *only if* the
convention/unification decisions are explicitly sequenced **after** it, each with
its own MAJOR version bump and a `from_legacy_*` shim (§8). Right now the order is
implicit.

**Recommendation:** decide the sample-axis convention (§13.6) **before first
code**, because it is upstream of the `protocols.py` and `_validation.py` that
§10.1 says to build first. Then state explicitly: relocate verbatim → unify
fields → apply convention, with the version bump at each contract change.

---

## 5. The unified twin base is under-specified on the exact fields that differ

**Verdict: resolvable, but unresolved, and on the critical path for *both* twin
migrations (§10.2 and §10.3).**

`FeatureFrame` has `feature_names: list[str]` + `metadata: dict`; `PredictionFrame`
has neither (§4.1). datafactory §8.1 flags this as *"the §13 open decision that
most directly affects datafactory"* and §8.2 adds that `save/load` must preserve
both as sidecars. The doc never says whether the unified base:

- carries `feature_names`/`metadata` as **optional** fields (then
  `PredictionFrame` "verbatim" silently **gains** fields — contradicting §10.2's
  "preserve its contract"), or
- keeps them **per-frame** (then the "shared base" is thinner than the §4.3 / §5
  framing implies).

Either is defensible; neither is chosen. And because `metadata` is also the home
proposed for provenance (§13.5, finding #3 above), this decision is entangled with
the C-48 fix.

**Recommendation:** specify the unified field set and the serialization contract
(does the frame serialize `feature_names`/`metadata` itself, or does the
`Persistable` protocol allow consumer extensions?) before relocating either twin.

---

## 6. `SpatialLevel` is a slippery slope that should be marked, not just relocated

**Verdict: same boundary question as finding #1, surfacing at a different point.**

The progression is: `SpatialLevel` → `entity_column` (`country_id` / `priogrid_id`)
→ cm↔pgm mapping → GAUL hierarchy. Each step is "just a bit more domain." The
leaf's purity constraint (§3, §11: no domain) is in direct tension with §4.3's
claim that the identifier vocabulary — and the alignment disagreements over it —
*belong here*. README §13.3 ("does `SpatialLevel` move here or come from a shared
`views-domain`?") is where this is nominally open, but it is treated as
low-stakes; in fact it is the **same decision** as the cross-level alignment scope
(#1) and should be resolved **with** it, not separately. All three perspectives
want `SpatialLevel` here (pipeline-core §3.5, reporting §3.5, datafactory §3.3),
which is fine — but the line past which "more domain" gets refused must be written
down, or scope-creep is guaranteed (this is literally README R5-style scope creep,
the failure mode the sibling appwrite repo names as most likely).

---

## 7. Smaller but real

- **One concrete cross-document inconsistency (fix this).** The cross-repo
  `reconciled_dataframe` mutation defect is **C-184** in the README (§1, §12) and
  in the reporting perspective (§4) — but the **pipeline-core perspective §4 table
  calls the identical defect** (same file and lines, `dataset_export.py:103,122`)
  **C-182**. One of them is a typo; given the README explicitly maps C-184 to this
  exact mutation and reporting agrees, the pipeline-core perspective's "C-182"
  looks wrong.

- **The name "frame" fights the thesis.** The whole package argues *against*
  DataFrames as transport, then names the replacement `…Frame`. A reader's first
  instinct is "`FeatureFrame` is a DataFrame subclass" — the exact conflation §0
  is trying to kill. Probably too late to rename, but a one-line up-front
  disambiguation in the glossary (§14) would help. (The glossary defines "Frame"
  but does not contrast it against "DataFrame," which is the confusion to pre-empt.)

- **Conformance-suite packaging is unstated.** §9 makes the conformance suite the
  cross-repo safety net (closes C-30), and datafactory §7.7 + §8.5 want to run it
  in CI against `grid_to_feature_frame()` output. That requires shipping
  `tests/conformance/` as an **importable** artifact (an installable subpackage or
  a pytest plugin) — a packaging decision absent from the §6 layout and the
  pyproject notes. As laid out (`tests/conformance/` as a sibling of `src/`), it
  is not importable by consumers.

- **Dependency-graph diagram imprecision (§2).** The diagram shows
  `views-evaluation` depending on `views-frames` like the others, but §4.2 says
  `EvaluationFrame` *stays* in views-evaluation and views-frames merely *defines a
  protocol it conforms to*. That is a different (and weaker, possibly mutual-
  knowledge) relationship than "depends toward." Minor, but the diagram overstates
  the uniformity.

- **"model repos" as consumers is asserted but not closed.** The §2 diagram lists
  hydranet/bayesian/stepshifter/etc. as depending on the leaf. pipeline-core §9.5
  implies it: the engine extension points (`_train/_evaluate/_forecast_model_
  artifact`) return `-> any` today and frames would type them — so model repos
  *would* import frames. That is actually a strong CRP argument (a model wanting a
  `PredictionFrame` must not transitively install pandas, §3.1) and worth making
  explicit rather than leaving in a diagram.

---

## 8. Two meta-observations

### 8.1 Governance inconsistency with the `views-appwrite` sibling

The same platform/author just built a full governance stack for `views-appwrite`
(constitutional ADRs 000–010, a technical risk register, contributor protocols)
for a leaf with ~3 consumers. `views-frames` is a **more** critical leaf — N
consumers, and `PredictionFrame` is described as *"the #1 coupling hub in the
codebase (graphify)"* (pipeline-core §3.1) — yet has **none** of that, only the
README. The §13 open decisions are essentially un-numbered ADRs, and the
perspectives already cite cross-repo register IDs as if a register exists. If the
appwrite governance posture is the house style, this repo is **under-governed
relative to its blast radius.** At minimum: the §13 open decisions should become
ADRs, and views-frames should have its own risk register (or a clearly-shared
one) given how much the perspectives lean on register IDs.

### 8.2 "Buildable against this doc" is slightly oversold

§0 of the README claims it is written *"so the package can be built against it."*
§10.1 says step one is *"stand up the package with `SpatioTemporalIndex`,
`protocols.py`, `_validation.py`, and `io/npz.py`."* But:

- `SpatioTemporalIndex` cannot be finalized without the cross-level alignment
  scope decision (#1).
- `protocols.py` cannot be finalized without the sample-axis convention (#4,
  §13.6).
- the unified frame fields cannot be finalized without the
  `feature_names`/`metadata`/provenance decision (#3, #5).

So you can scaffold the trivial shell, but you **cannot build *the product*** (the
index/alignment contract and the protocols) from this document as it stands. This
is the *same finding* the `views-appwrite` falsification produced ("enough
information to start?" → enough to scaffold, not enough to build the load-bearing
piece). The honest restatement: at least the alignment scope (#1), `SpatialLevel`
home (#6/§13.3), and sample-axis convention (#4/§13.6) are **blocking** and should
move from "resolve before/at first code" to "resolve **before** first code."

---

## 9. The through-line

The thesis is right, the principle work is genuinely good, and the honesty about
scope limits is exemplary. The structural gap is consistent across findings:

> **The package's real value — cross-level alignment, a domain-clean identifier
> vocabulary, and a typed evaluation-output/run identity — sits in exactly the
> places the documents are least decided. The parts that are most fleshed out
> (relocate the two twins behind shims) are the parts that were already easy.**

Three decisions unblock most of it:

1. **Alignment scope + `SpatialLevel`/domain line** (#1, #6) — where does the
   country↔grid mapping live, and what is the exact boundary between identifier
   vocabulary and reference data?
2. **`MetricFrame` placement** (#2) — generalise the index protocol, or hand it to
   views-evaluation.
3. **Sample-axis convention + unified field set + provenance** (#3, #4, #5) — the
   cluster that defines the actual frame contract and the C-48 cure.

Resolve those, fix the C-182/C-184 typo, and the rest of the package is
executable.

---

## 10. Suggested next steps (not done here)

- **`/falsify`** a sharp claim — candidates: *"the §13 open decisions are
  non-blocking for first code"* (§8.2 predicts this falsifies), *"views-frames as
  specified stays domain-free"* (#1/#6), or *"`SpatioTemporalIndex` is the shared
  primitive of every frame in the family"* (#2 predicts this falsifies on
  `MetricFrame`). The user has flagged this as the planned follow-up.
- Consider standing up a views-frames risk register and converting §13 into ADRs
  (#8.1), to match the platform's house governance style — *if* the platform
  churn the user flagged has settled enough to be worth it.

*Reflection only — no code written, no docs altered, no risks registered.*
