# Reconciliation migration & cutover runbook

How to relocate a reconciliation implementation into `views_frames_reconcile` (or move the
platform onto a new reconciler) **without a silent change to served numbers**. This is the
procedural companion to ADR-023 and the `views_frames_reconcile` package; it captures the
order, the verification gates, and the rollback so the next cutover is boring.

> **Status — the Epic 11 instance is COMPLETE.** This runbook was written from, and is the
> record of, the first cutover (the relocation out of views-postprocessing). Every step
> below is marked ✅ with its actual PR/commit. Re-use it as the template for any future
> reconciler change.

## What is special about reconciliation (read once)

- It is a **frame→frame numpy operation** (`views_frames_reconcile`, ADR-023) — make grid
  (`pgm`) predictions sum, per posterior draw, to country (`cm`) totals. It must stay
  numpy-only and `views_frames`-only (import-DAG enforced).
- It is a **re-baseline of served numbers.** Repointing a consumer from one reconciler to
  another changes a production code path. Even at *intended* bit-identity, that is a
  consumer-visible change and must be verified, versioned, and reversible — never silent.
- The mapping is **injected, never fetched** (ADR-014). A cutover never moves geography into
  the leaf; it only swaps which `ReconciliationModule` the composition root injects.
- There can be **several copies in flight** (during Epic 11: views-reporting torch = the
  oracle source; views-postprocessing numpy = the stranded copy; views_frames_reconcile =
  the new canonical). Know which one production actually serves before you touch anything.

## The order (never reorder these)

**Release → repoint → verify green → delete → (optional) collapse the injection.** The two
hard rules:

1. **Never delete the old copy before the consumer repoint is merged, green, and observed.**
   The old copy is the rollback.
2. **Sequence each consumer/injection change as its own deploy** — never batch the repoint
   and the injection-collapse, so a regression is attributable.

## Prerequisites

- [ ] The new reconciler is **released** on PyPI and pinned by the consumers (`views-frames`
      ≥ the version that carries it). _Epic 11: ✅ v1.7.0._
- [ ] **In-repo parity is green** in views-frames: the frozen views-reporting **torch oracle**
      fixtures (`tests/fixtures/reconciliation_*.npz`) pass, and the **new-vs-old bit-identity
      head-to-head** (`tests/test_reconcile_head_to_head.py`, 136 cases, `np.array_equal`)
      passes. _Epic 11: ✅._
- [ ] You can run the verifier: `uv run python scripts/verify_reconcile_parity.py --oracle`
      reports **PASS**. _Epic 11: ✅ (0.000e+00 abs/rel error vs the torch oracle)._

## Phase 1 — Verify before you move anything

```bash
# 1. the canonical copy still reproduces the torch oracle the cutover is validated against
uv run python scripts/verify_reconcile_parity.py --oracle      # expect: VERDICT: PASS

# 2. the new == old bit-identity gate (needs the old sibling repo checked out adjacently)
uv run pytest tests/test_reconcile_head_to_head.py -q          # expect: all green
```

> The head-to-head is **transitional** — it `importorskip`s the old reconciler, so it only
> runs while both copies coexist (during the cutover window). Once the old copy is retired
> (Phase 4) it skips permanently; that is expected. The durable, always-runnable gate is the
> `--oracle` check above, which needs no sibling repo.

The safety argument is a **chain**: `new (views_frames_reconcile) == old vpp copy`
(head-to-head, bit-identical) and `old vpp == views-reporting torch oracle` (the frozen
`.npz`), therefore `new == torch oracle` — the numbers production was built on. Do not
proceed if either link is red.

## Phase 2 — Production-slice check (belt-and-suspenders)

The oracle is synthetic-but-real (captured from the torch path). For extra assurance, compare
the **old served output** against the **new reconciler** on an actual production slice:

```bash
# old_served.parquet = what the current path produced; new_served.parquet = a run through
# views_frames_reconcile on the same inputs. Align on the served identity columns.
uv run --with pandas python scripts/verify_reconcile_parity.py \
    --compare old_served.parquet new_served.parquet --keys month_id priogrid_id
# expect: VERDICT: PASS (drift within rtol=1e-5 / atol=1e-6)
```

If this diverges, **stop** — the in-repo oracle and the live path have drifted; investigate
before repointing.

## Phase 3 — Repoint the consumer (one deploy)

Repoint the **single concrete-import seam** to `views_frames_reconcile`. By ADR-014 there is
exactly one such file per consumer (the composition root / factory), so this is a one-line
import change plus its tests.

- views-models: `reconciliation/reconciler_factory.py` →
  `from views_frames_reconcile import ReconciliationModule`. _Epic 11: ✅ views-models #191,
  PR #202 (commit `97a66ed`)._
- **Bump the consumer's methodology / re-baseline version** (e.g. faoapi's methodology-version
  field) so the change in numbers is auditable from the served output, not reconstructed.
- Merge, run the consumer's own reconciliation tests, and **observe it green in the consumer's
  CI/production** before Phase 4.

## Phase 4 — Retire the old copy (a later, separate deploy)

Only after Phase 3 is merged + green + observed: delete the stranded copy.

- views-postprocessing: remove `views_postprocessing/reconciliation/`, drop its CIC entry,
  and confirm **no live `import` of the old module remains** — grep for `import.*<old_module>`
  (or run the consumers' suites). Note that *transitional* `pytest.importorskip("<old_module>")`
  calls and docstring/ADR/test-name mentions are **not** live imports and may linger; sweep that
  prose in a follow-up, but it does not block the delete. _Epic 11: ✅ views-postprocessing #62,
  PR #63 (commit `6af2020`); residual stale prose references remain in views-models, tracked as a
  doc-hygiene follow-up._

## Phase 5 — (Optional) collapse the cycle-dodging injection

If the old home sat *above* a consumer in the DAG, a DIP port + adapter may have been built to
inject the reconciler and dodge a cycle. Once the new reconciler is *below* the consumer, that
port can collapse to a direct import — but it is its **own** deploy, sequenced last.

- _Epic 11: the pipeline-core injection (DIP port + adapter, PRs #195/#217) already breaks the
  cycle cleanly — the reconciler is injected at the composition root and the concrete is never
  imported — so #221's collapse is **optional, not required**, and was deferred as a pure
  simplification._

## Rollback

- **Before Phase 4:** revert the Phase 3 repoint PR; the old copy still exists and the consumer
  falls back to it. Single-commit revert, no data migration.
- **After Phase 4:** restore the deleted copy from git history, then revert the repoint. This is
  why Phase 4 must never precede a green, observed Phase 3.

## Verification gates (the checklist)

| Gate | Tool | Pass condition |
|---|---|---|
| Oracle parity | `verify_reconcile_parity.py --oracle` | `PASS` (abs/rel err ≈ 0 vs torch oracle) |
| New == old bit-identity | `pytest tests/test_reconcile_head_to_head.py` | all `np.array_equal` |
| Production slice | `verify_reconcile_parity.py --compare` | within `rtol=1e-5/atol=1e-6` |
| Consumer repoint | the consumer's reconciliation tests | green in the consumer's CI |
| No stranded imports | `grep -rn "import.*<old_module>"` | no live `import` after Phase 4 (transitional `importorskip`/prose may linger) |
| Re-baseline audit | methodology-version field | bumped + visible in served output |

## Provenance

ADR-023 (reconciliation is a sibling package); `reports/postmortems/2026-06_views_frames_reconcile.md`
(building the package) and `2026-06_reconciliation_cutover_epic11.md` (this cutover);
Epic 11 tracker `#138`; cross-repo issues views-models #191, views-postprocessing #62,
pipeline-core #221; register C-58 (the production-slice verification residual).
