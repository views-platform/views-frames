# Postmortem — `views_frames_reconcile`, the reconciliation sibling (Epic 11, v1.7.0)

| Field | Value |
|---|---|
| Subject | The third sibling package: a faithful **WET relocation** of the forecast reconciler from a repo where it was mis-homed, into the frames foundation — proven bit-identical, released as v1.7.0 |
| Window | 2026-06-26 (one focused session: ADR-023 → S1–S6 → published to PyPI), including a mid-effort process crash and a clean recovery |
| Repos | `views-frames` (where the code now lives); `views-postprocessing` (the **read-only** source it was relocated from); downstream `views-pipeline-core`, `views-models` (the gated cutover, not part of this effort) |
| Governing docs | ADR-023 (reconciliation is a sibling); the reconcile conformance suite; views-postprocessing risk C-42 (the stranded migration this completes); the Epic 11 tracking issue (#131–#138) |
| Outcome | A numpy-only, `views_frames`-only reconciler in the foundation, **100% coverage, mypy-strict, import-enforced**, proven bit-identical to its source by both the frozen torch oracle and a 136-case new-vs-old head-to-head. The work was almost entirely *discipline*: no algorithm was written, only relocated and proven. The only friction was tooling (the recurring numpy-floor mypy skew) and the leftover divergence of a multi-release branch graph. |

---

## 1. What we did, and why

Forecast **reconciliation** — making grid (`pgm`) predictions sum, per posterior draw, to their
country (`cm`) totals — is a numpy-only frame→frame operation, structurally the *same kind of thing*
as `views_frames_summarize` (ADR-017). But it lived in **views-postprocessing**, a partner-delivery
repo that does not even use it (the UN-FAO path sums by construction). Housing it there *stretched*
that repo's scope and forced an **injection dance**: views-postprocessing sits *above* pipeline-core
in the DAG, so pipeline-core could not import the reconciler directly and had to have it injected
(pipeline-core #195 / PR #217). The migration had been parity-proven there (vpp PR #30) but
**stranded** — pipeline-core was never repointed to it (vpp risk C-42).

ADR-023 ratified the fix, mirroring ADR-017: reconciliation is a **third sibling package**,
`views_frames_reconcile`, depending on `views_frames` + numpy only. Landing it **low** in the DAG
(SDP) is the structural payoff — pipeline-core already depends on `views_frames`, so the
cycle-dodging injection can later collapse to a direct import; the port's only reason to exist
vanishes. The charter, like summarize's, is bounded: frame-reconciliation algorithms only; **never
fetch the `(time, unit) → country` mapping** (it is injected as arrays, exactly like
`cross_level_align` — ADR-014); no IO, scoring, plotting, or foreign `views_*`.

The non-negotiable constraint was **WET before DRY**: a *faithful move + parity first*, not a
rewrite. The ported algorithm files had to differ from their source by **import lines only**.

## 2. How it unfolded — the arc

Six stories, executed in dependency order on one epic branch, each gated and committed separately.

- **S1 — ADR-023.** The sibling charter, mirroring ADR-017; import-DAG `→ {views_frames}`; additive
  MINOR (1.6.0 → 1.7.0); `CONFORMANCE_FLOOR` stays `1.0.0`.
- **S2 — scaffold.** A flat package mirroring summarize (one concept per file); `pyproject` wheel
  packages; the import-enforcement allow-list entry. The empty scaffold had to keep the 100% gate
  green — solved by making the stubs docstring-only (zero countable statements) rather than carrying
  an uncovered `from __future__ import annotations`.
- **S3 — the faithful port.** The 6 reconciler files copied verbatim, then a single substitution
  (`views_postprocessing.reconciliation → views_frames_reconcile`) applied only where it occurs (the
  import lines). `diff` against the source proved it: `proportional`/`frames`/`validation`
  byte-identical; `grouping`/`module`/`__init__` differ on import lines only. `grouping.py` was
  *deliberately not* folded into the leaf's overlapping `cross_level_align` — that DRY pass is a
  later story.
- **S4 — the parity + bit-identity gate.** Relocated the 6 parity tests + 2 frozen oracle fixtures +
  2 regeneration scripts (pointed at the new package), and added a **transitional 136-case
  head-to-head**: the new package vs the old `views_postprocessing.reconciliation`, on fresh
  synthetic seeds (probabilistic + point + edge cases, both the leaf function and the full module),
  asserting `np.array_equal` (float32). All bit-identical. Closed the lint/type/coverage gaps the
  port surfaced (import-sort, two fail-loud branches vpp's tests missed) → 100% line+branch.
- **S5 — conformance.** `assert_reconcile_contract` mirroring the summarizer contract: sum-to-country
  per draw (with the all-zero-draw edge), zero-preservation, non-negativity, level correctness, and
  an injected-mapping sensitivity check (a permuted mapping changes the result — proof the mapping is
  used, not fetched).
- **S6 — release v1.7.0.** Version bump, README §6a charter + layout, CHANGELOG. **The crash hit
  here** (see below). On recovery: full gate, PR → development → main (merge commit, trial-merged
  first), tag `v1.7.0`, GitHub Release → PyPI; clean-env install verified.

## 3. What went well

- **WET-before-DRY done right, with two independent proofs.** The *import-lines-only diff* proves the
  relocation introduced no algorithmic change by construction; the *136-case bit-identity head-to-head*
  proves it behaviourally. Belt and suspenders — and exactly the right rigor for "this is now the
  canonical copy."
- **Per-story commits made the crash a non-event.** A full process crash struck mid-S4, with the
  head-to-head test unwritten. Because S1–S3 were committed and S4's work was on disk, the damage
  assessment was a five-minute `git status` + gate re-run; nothing was lost, and the only remaining
  work was the one unwritten test. Incremental, gated commits are cheap insurance that paid out.
- **Verifying against the repo, not the prose.** The story said "8 parity tests"; the repo had **6**.
  The quest had explicitly warned that planning prose drifts from reality — and it had. Porting what
  *actually existed* (verified by `find`), not what the card claimed, avoided a phantom-file hunt.
- **The conformance suite earned its keep on the mapping charter.** The sensitivity check (permute
  the mapping → output must change) turns "the mapping is injected, never fetched" from a docstring
  claim into an executed assertion.
- **The release machinery was boring.** The dev→main trial-merge-first / merge-commit discipline and
  the Trusted-Publishing workflow made the irreversible steps uneventful. PyPI went 1.6.0 → 1.7.0
  with a passing version guard and a clean-env import check.

## 4. What went wrong, and what we missed

- **The numpy-floor mypy skew bit again — the same class of bug as the leaf's first week.** The
  vpp-ported type hints used bare generics (`NDArray[np.floating]`, `NDArray[np.integer]`). Local
  `mypy src/` (numpy 2.x) passed; the CI **floor** job (`mypy --strict` under py3.10 + numpy 1.26.4)
  failed with `type-arg` errors. I had run the floor *pytest* locally but **not the floor *mypy***,
  so the first PR CI run was red. Fixed by parametrising to `np.floating[Any]` / `np.integer[Any]`
  (the leaf's house idiom) — annotations only, re-confirmed by the bit-identity gate. This is the
  third time this family has eaten this exact lesson; it is now written into the pre-push checklist.
- **The "import-lines-only" ideal collided with the destination's stricter bar.** The source passed
  *its* CI; the leaf's CI is stricter (ruff line-length, B905 `zip(strict=)`, mypy-strict floor, 100%
  *branch* coverage). So the pristine S3 diff could not also be "ruff + mypy clean" — those gaps had
  to close in S4. The honest resolution was to keep S3 a pristine relocation and isolate the
  mechanical conformance in S4, but it is a genuine tension: a faithful port into a stricter home is
  *not* import-lines-only end-to-end, and the story card's acceptance criteria overstated that.
- **The source's tests had real coverage gaps the port inherited.** Two fail-loud branches (the
  pgm-level guard; the `map_vals`-shape guard) were never exercised by vpp's suite. 100% coverage in
  the new home required writing the adversarial tests the source lacked. A relocation is only as good
  as the tests that come with it — and these needed topping up.
- **Branch-graph divergence is a standing tax at release.** `main` carries squash release-commits
  that `development` never receives, so dev→main is always a *divergent merge*, never a fast-forward.
  The plan assumed "main is strictly behind"; it wasn't. A non-destructive trial-merge caught it and
  it merged cleanly, but the assumption was wrong and would have been a surprise without the check.

## 5. What surprised us

- **The head-to-head was guaranteed to pass — and that was the point.** Because the port is
  byte-identical to the source except for import lines, the algorithm *is* literally the same code;
  `np.array_equal` could not fail. The value of the 136-case gate is not that it might find a
  difference, but that it *proves the absence* of one on the record, on fresh seeds, for the release
  note and the downstream consumers who will trust this as canonical.
- **The hardest part of a "no new code" effort was the tooling, not the code.** Zero algorithm was
  authored. The entire cost was in the destination's stricter gate (floor mypy, branch coverage,
  lint) and in release mechanics. A faithful relocation is a *conformance* exercise, not an
  engineering one — and conformance to a stricter home is where the friction lives.
- **An empty package can fail a 100% coverage gate.** The scaffold's only countable line was a
  `from __future__` import; with no test importing it, coverage dropped below 100%. Making the stubs
  truly statement-free (docstring only) was the fix. A small, instructive reminder that `source =
  ["src"]` + a 100% gate sees *every* file, including the empty ones.

## 6. What would be easier next time

- **Run the full mypy matrix — floor *and* ceiling — before pushing, every time.** This is now the
  single most repeated lesson across all three packages. Running the floor *pytest* is not running
  the floor *mypy*; they catch different errors. Make both a pre-push reflex, not a CI discovery.
- **State the WET acceptance criterion honestly: "import-lines-only diff *plus* mechanical
  conformance to the destination gate, no algorithmic change — proven by bit-identity."** The pure
  "import-lines-only" framing is the right *intent* but cannot survive a stricter home end-to-end;
  the bit-identity gate, not the diff shape, is the real guarantee of "no behaviour change."
- **Budget for the source's test debt up front.** Assume a relocated component's tests do not meet
  the new home's bar (branch coverage, direct reject-path tests) and plan the gap-closing as part of
  the port, not a surprise.
- **Trial-merge dev→main before every release** (a non-destructive `--no-commit --no-ff` then abort)
  and promote with a **merge commit**. The divergence is permanent and expected; verify it is clean
  rather than assuming a fast-forward.
- **Verify the work-list against the repo, never the planning prose.** "8 tests" was 6. A 30-second
  `find` beats trusting a stale card — the quest warned about this and it was right.

## 7. Final state

`views-frames==1.7.0` is on PyPI, shipping `views_frames_reconcile` (`ReconciliationModule`,
`reconcile_proportional`, `assert_reconcile_contract`) alongside the leaf and the summarize sibling —
numpy + `views_frames` only, import-enforced, 100% line+branch, mypy-strict at the floor and ceiling,
proven bit-identical to its views-postprocessing source. ADR-023 is merged; the Epic 11 stories
(#132–#137) and the epic (#131) are closed; `CONFORMANCE_FLOOR` stayed `1.0.0`. The **cross-repo
cutover** — repointing views-models and deleting views-postprocessing's now-redundant copy — is
explicitly *gated on this release* and out of scope here; the injection that existed only to dodge
the old cycle can now collapse to a direct import, which was the whole structural point.

The one-sentence lesson: **relocating a proven component is an exercise in *discipline, not
invention* — its risks are bit-identity, the destination's stricter gate, and release mechanics, not
the algorithm — so prove "nothing changed" two ways, hold the algorithm byte-stable, and let the
tooling, not the code, be where you spend the effort.**
