# Postmortem — the Epic 11 reconciliation cutover (cross-repo migration onto `views_frames_reconcile`)

| Field | Value |
|---|---|
| Subject | The cross-repo half of Epic 11: the platform migrating *onto* the relocated reconciler and retiring the old copies — what it took to flip a live, served code path safely, and the stale-tracking gap that hid that it was already done |
| Window | 2026-06-26 — package released (v1.7.0), consumer repointed (views-models #191), old copy retired (views-postprocessing #62), all within the same window |
| Repos | `views-frames` (the canonical copy + the verification evidence + this record); `views-models` (the consumer repoint, C1); `views-postprocessing` (the retired copy, C2); `views-reporting` (the torch oracle source, now stranded); `views-pipeline-core` (the DIP-injection that made the cycle moot) |
| Governing docs | ADR-023; the Epic 11 tracker `#138`; cross-repo issues views-models #191, views-postprocessing #62, pipeline-core #221; the companion build postmortem `2026-06_views_frames_reconcile.md` |
| Outcome | The live reconciliation path is now served by `views_frames_reconcile` (numpy), injected at the views-models composition root; the stranded views-postprocessing copy is deleted; the views-reporting torch path is retired. The cutover was **safe by an established bit-identity chain** and landed as **phased** PRs (repoint, then delete), exactly as a re-baseline of served numbers should. The one real miss was process, not engineering: the in-repo `#138` tracker was never ticked when the sibling work landed, so a "go execute the cutover" request found it already complete. |

---

## 1. What we did, and why

The companion postmortem (`2026-06_views_frames_reconcile.md`) covers *building* the sibling
package — the faithful WET relocation of the reconciler into `views_frames_reconcile`, proven
bit-identical, released as v1.7.0. This one covers the **cross-repo cutover that followed**:
moving the platform's consumers onto the new canonical copy and retiring the old ones, so the
relocation actually *takes effect* rather than shipping a second unused copy.

The work matters because reconciliation is a **served, production code path**. At the start of
Epic 11 there were three reconciler copies in flight: views-reporting (torch — the oracle
source), views-postprocessing (numpy — parity-proven but stranded, never repointed-to), and
views_frames_reconcile (the new numpy canonical). A cutover that simply "ships and hopes" would
re-baseline served numbers silently. The goal was the opposite: flip the path with an explicit
verification chain, in a reversible order, with the change auditable from the output.

## 2. How it unfolded — the arc

The cutover order was the one the runbook now codifies — **release → repoint → delete** — each
step its own PR:

- **Release (✅ v1.7.0).** `views_frames_reconcile` published, pinned by the consumers. The
  in-repo gates were green: the frozen views-reporting torch-oracle fixtures
  (`tests/fixtures/reconciliation_*.npz`) and the 136-case new-vs-old bit-identity head-to-head
  (`tests/test_reconcile_head_to_head.py`).
- **C1 — repoint the consumer (✅ views-models #191, PR #202, commit `97a66ed`).** The single
  concrete-import seam — `views-models/reconciliation/reconciler_factory.py` — was repointed to
  `from views_frames_reconcile import ReconciliationModule`. By ADR-014 that factory is the only
  file that names the concrete, so C1 was a one-line import change plus its tests; the reconciler
  is injected at the composition root (the ensemble `main`), not imported at module scope.
- **C2 — retire the old copy (✅ views-postprocessing #62, PR #63, commit `6af2020`).** Only after
  C1 was merged and green: `views_postprocessing/reconciliation/` was deleted and its CIC entry
  dropped, with a grep confirming no live imports of the old module remained anywhere.
- **The cycle was already moot.** pipeline-core's DIP port + adapter (PRs #195/#217) already break
  the views-reporting/views-postprocessing cycle: the adapter imports only `views_frames`, and the
  reconciler is injected, so pipeline-core never imports the concrete. Issue #221 ("collapse the
  injection to a direct import") is therefore an *optional* simplification, not a required step,
  and was deferred.

The whole cutover was verified, after the fact, by re-running the parity verifier
(`scripts/verify_reconcile_parity.py --oracle`): the canonical copy reproduces the torch oracle
at **0.000e+00** absolute and relative error, with conservation within float32 summation noise.

## 3. What went well

- **The safety chain held end-to-end.** `new (views_frames_reconcile) == old vpp copy`
  (bit-identical, 136 cases) and `old vpp == views-reporting torch oracle` (the frozen `.npz`),
  therefore `new == the numbers production was built on`. The cutover never relied on "trust me" —
  it relied on a transitive, re-runnable equality.
- **The order was right and the steps were phased.** Repoint (PR #202) and delete (PR #63) were
  *separate* PRs, never batched. The old copy stayed as the rollback until the repoint was green.
  This is exactly the discipline a served-numbers re-baseline needs, and it was followed without
  drama.
- **ADR-014's single-seam design paid off.** Because the concrete is named in exactly one file per
  consumer (the factory / composition root), C1 was genuinely a one-line change — not a
  repo-wide find-and-replace. The injected-mapping boundary meant no geography moved anywhere.
- **The injection was already the right shape.** pipeline-core's DIP port (built earlier, #195/#217)
  meant the cutover did *not* require a risky pipeline-core change — the consumer just swapped which
  concrete the composition root injects. The earlier investment in decoupling de-risked this.

## 4. What went wrong, and what we missed

- **The in-repo tracker went stale — the cutover was *done* and `#138` didn't know.** C1 and C2
  merged and their sibling issues (views-models #191, views-postprocessing #62) closed, but the
  views-frames `#138` checklist was never ticked and the issue stayed open. A later "investigate
  and execute the cutover" request had to *discover by grep* that there was nothing left to execute.
  Cross-repo tracking that lives in one repo but is satisfied in others drifts unless someone closes
  the loop explicitly. (This postmortem + the `#138` closeout are that loop, late.)
- **Verification was against the oracle, not a live production slice.** The cutover was validated by
  the frozen torch-oracle fixtures + the synthetic head-to-head — strong evidence, since the oracle
  *is* the torch path's output — but no comparison was run against an actual served production
  parquet (old path vs new path) at the repoint. The risk is low (the oracle chain is sound), but it
  is a belt the runbook now provides a buckle for: `verify_reconcile_parity.py --compare`. Registered
  as **C-58**.
- **Stale references were left in the consumer's docs.** views-models still carries
  `views_postprocessing.reconciliation` mentions in a package docstring, an ADR, and test names
  (the live import is correct; only the prose lags). Cosmetic, cross-repo, but the kind of residue a
  cutover should sweep.

## 5. What surprised us

- **The hardest part of a "flip the path" cutover was *knowing it had already happened*.** The
  engineering was a one-line import (C1) and a directory deletion (C2); the actual difficulty was
  reconstructing the true state across four repos because the central tracker had drifted. The work
  was trivial; the *bookkeeping* was where the time went.
- **The cycle never needed collapsing.** The instinct was that the cutover would unlock a satisfying
  "delete the injection" simplification (#221). But the DIP port was already clean — it imports only
  `views_frames` and injects the concrete — so there was nothing to fix, only an optional cosmetic
  tidy. The earlier decoupling had already done the load-bearing work.
- **"Bit-identical" was, again, guaranteed by construction.** As in the build effort, the relocation
  was byte-identical code modulo imports, so the verifier's `0.000e+00` was never in doubt — its
  value is the *record*, not the discovery.

## 6. What would be easier next time

- **Close the cross-repo loop the moment the sibling work merges.** A tracker in repo A satisfied by
  PRs in repos B and C must be ticked/closed deliberately — wire it into the consumer PR's checklist
  ("update views-frames #138") so it never drifts into "is this done?" Add it to the runbook's
  Phase 3/4 exit criteria.
- **Run the production-slice check at the repoint, not retrospectively.** `verify_reconcile_parity.py
  --compare old_served.parquet new_served.parquet` is one command; make it a Phase-2 gate on every
  future cutover so the evidence is live, not reconstructed.
- **Sweep the consumer's prose in the same PR as the code.** A repoint PR that updates the import
  should also update the docstring/ADR/test-name references to the old module — otherwise the
  cutover looks half-done in the consumer for months.
- **Keep the phased order and the rollback discipline.** Release → repoint → (green, observed) →
  delete, each its own deploy, old copy retained until the repoint is proven. It cost nothing here
  and it is the whole reason a served-numbers re-baseline can be undone with a single revert.

## 7. Final state

The platform's reconciliation is served by `views_frames_reconcile` (numpy, injected via the
views-models composition root, consumed by pipeline-core's EnsembleManager without importing the
concrete). The stranded views-postprocessing copy is deleted (#62); the views-reporting torch path is
retired but preserved as the parity oracle. views-models #191 and views-postprocessing #62 are closed;
the views-frames tracker `#138` is now closed too, with this record. The cutover's safety evidence is
re-runnable via `scripts/verify_reconcile_parity.py --oracle` (PASS, exact). The optional
injection-collapse (pipeline-core #221) remains a deferred cosmetic simplification, not a blocker.
`CONFORMANCE_FLOOR` stayed `1.0.0`; the frozen v1 surface was untouched throughout.

The one-sentence lesson: **a cross-repo cutover is finished in the sibling repos but not *closed*
until the tracker that lives somewhere else is deliberately shut — the riskiest part of flipping a
served path turned out to be not the flip, which a one-line seam and a bit-identity chain made safe,
but knowing, across four repos, that it was already done.**
