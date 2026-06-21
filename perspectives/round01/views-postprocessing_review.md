# views-frames — round 01 review, from the **views-postprocessing** perspective

> **Reviewer:** Claude (Opus 4.8), acting as the AI-agent developer who maintains
> **views-postprocessing** — a *consumer* of this library: it enriches VIEWS
> predictions with geography and delivers them to the UN FAO. The lens throughout is
> "would I adopt views-frames in my repo, and what would I need from it?"
> **Date:** 2026-06-21. **Reviewed at:** v0.2.0 (two-package release), `main` @ `07beefb`.
> **Method — read-only static inspection.** I read every source module under `src/`
> (both `views_frames` and `views_frames_summarize`), the README / CLAUDE.md /
> GOVERNANCE / CHANGELOG, the ADRs, the CICs, the risk register, the prior
> `critiqus/` falsifications, and the tests; I traced the construct → reduce →
> save/load → conformance path *by reading*. I did **not** run `pytest` / `mypy` /
> `ruff` in this pass (that writes cache dirs, outside the single permitted write), so
> where I discuss those gates I do so from the code/config and treat **CI as the
> authority** on pass/fail. No source modified, nothing staged, no commit, no branch;
> the only file written is this report.
>
> **One-line verdict:** From a consumer's chair this is a library I would *want* to
> adopt — the abstractions match exactly the data my pipeline already moves
> (`(month_id, priogrid_gid)`-indexed prediction arrays), and the contract is clearer
> than my current ad-hoc pandas handling. It is held back from "I'd adopt it tomorrow"
> by missing consumer on-ramps (`py.typed`, a runnable example, a conformance-suite
> usage snippet) and a couple of scale-path loops worth confirming — none architectural.

---

## Why my perspective is relevant

views-postprocessing is precisely the kind of consumer this library is built for. My
pipeline reads predictions indexed by `(month_id, priogrid_gid)`, attaches metadata,
validates fail-loud, serializes to parquet, and uploads. Today I do all of that with
pandas DataFrames and a hand-rolled enricher. So I read views-frames asking: *does this
replace my ad-hoc transport with a typed contract, and would the migration pay for
itself?* That makes four of its decisions land directly on my real problems:

- **`SpatioTemporalIndex(time, unit, level=PGM)`** is exactly my row identity.
- **fail-loud construction** mirrors my own `_validate()` null-gate philosophy.
- **`save`/`load` (npz + arrow)** is the transport I currently improvise.
- **`cross_level_align(mapping, target_level)`** is the pg→country move my FAO
  aggregation needs — and the *injected-mapping* boundary is exactly the right call
  (my repo just spent a long arc establishing that the consumer, not the leaf, owns the
  geography mapping).

---

## 1. Does it do what I need it to do?

**Yes, for transport and identity.** The purpose is unusually clear (README §0: arrays
+ spatiotemporal identifiers as canonical internal transport; DataFrames only at the
boundary), and it is grounded in *named* production defects rather than taste. The
structure is legible at a glance — two packages, one concept per file, ~1.1k LOC,
10 public symbols. As a consumer I can hold the whole surface in my head, which is the
right property for a dependency at the root of the DAG.

**I can see how I'd use it** — from source. Construct an index, wrap values in a
`PredictionFrame` / `TargetFrame`, `save`/`load`, reduce with
`views_frames_summarize`, and self-verify with `assert_frame_contract`. The one thing I
*can't* do is copy a working example: there is none (see §3).

**The abstractions are useful from an agent-dev angle.** The standout is the
**published, pytest-free conformance suite**: as the postprocessing agent I could emit a
frame from my enricher and have an importable oracle (`assert_frame_contract(my_frame)`)
tell me deterministically whether I matched the contract — far better than my current
"hope the columns line up." Combined with fail-loud construction whose error messages
*cite the ADR that explains the fix*, this is genuinely safe for an agent to target.

**Caveat specific to my repo:** the headline consumer win the README front-loads —
a typed evaluation/`MetricFrame` that fixes reporting's C-48 — is correctly **deferred**.
And `FrameMetadata` carries only `model / run_type / timestamp / seed`
(`metadata.py:19–22`); it does **not** yet carry `run_id` / `data_version` /
`code_revision`. That matters to me concretely: views-postprocessing just had to add a
*lookup-version stamp* to its FAO deliveries (our C-35 / provenance work) precisely
because a delivery must be traceable to the exact data version that produced it. If I
adopted frames as my delivery transport today, I'd still have to carry that provenance
out-of-band. This is a deliberate scope line, not an oversight — but since the README
sells C-48/provenance as motivation, it's worth naming that the durable provenance
fields aren't here yet.

---

## 2. Does it do things the way I would want?

**Mostly yes, and in a few places better than I'd build myself.**

- **Interfaces are small and exact.** The index exposes only the alignment surface a
  reconciler needs (`intersect`, `searchsorted`/`reindex`, `is_superset_of`, `argsort`,
  `cross_level_align`); frames expose only `values / index / identifiers / n_rows /
  sample_count / is_sample / with_metadata / save / load`. Nothing extraneous.
- **The immutability + zero-copy model is done right.** `with_metadata` shares the
  values buffer; the index stores read-only views (`index.py:43–44`,
  `setflags(write=False)`); `coerce_values` preserves `np.memmap` on load. This is the
  discipline that prevents the multi-GB blow-up my own pipeline risks, and it's tested
  with `np.shares_memory`, not just asserted.
- **Architecture rules are executable.** `tests/test_import_enforcement.py` AST-walks
  every module and fails the build on a forbidden import (`pandas`, `torch`, `viewser`,
  a foreign `views_*`), `pyarrow` outside `io/`, or a second public class in a file.
  As an agent contributor I literally cannot drift the topology silently — this is the
  single most agent-friendly thing in the repo.
- **`CLAUDE.md` is the right shape** for autonomous work: exact `uv` commands, the hard
  constraints, the two-package map, and a "reconcile code↔README" rule.
- **The why travels with the code** — module docstrings cite the ADR and register ID
  behind each decision.

Where it diverges from what I'd want: the **protocol surface is narrower than a
consumer needs** (§4), the **typed contract isn't shipped** (no `py.typed`, §6), and a
few **hot-path operations are Python-loop-bound** (§6) in a scale-justified package.

---

## 3. What is missing? (ranked by what would unblock my adoption)

1. **A runnable Quickstart / `examples/` (highest-value gap).** The README is an
   excellent design bible but has no runnable "how": no `examples/` dir, no quickstart
   snippet, no usage in the package docstring. The fastest path to "make a frame" is
   reading `tests/test_frames.py`. For me to adopt — and for an agent to act rather than
   guess — a ~15-line construct→reduce→save/load→`assert_frame_contract` example is the
   missing on-ramp.
2. **`py.typed` (PEP 561) — absent.** Neither `src/views_frames/py.typed` nor
   `src/views_frames_summarize/py.typed` exists, yet `pyproject.toml` sets `mypy`
   `strict = true`. Without the marker, *my* type checker gets nothing from the package
   I'd depend on — defeating the point of a typed contract. (Small fix; also needs the
   hatchling include so it ships in the wheel.)
3. **A conformance-suite usage snippet.** ADR-016 makes the suite an importable governed
   floor — exactly what I'd want to run in *my* CI against my enricher's output — but
   nothing shows how to import and run it. Three lines would close this.
4. **A worked consumer/adapter example (the seam).** By design the producing adapter
   lives in the consumer repo (mine), but the hard part of adoption is that seam: "model
   output / enriched predictions → `PredictionFrame` → delivery." One reference example
   would de-risk my migration more than any leaf-internal change.
5. **Durable provenance fields** (`run_id` / `data_version`), or an explicit statement
   that provenance beyond `model/run_type/timestamp/seed` stays out-of-band. As above,
   this is exactly the gap my repo just had to solve for FAO deliveries.

---

## 4. What surprised me?

**Good surprises**
- **The falsification loop actually closed in code.** `critiqus/critique_02.md`
  *hard-falsified* the "domain-free leaf can do cm↔pgm alignment" claim. The repo didn't
  paper over it — `cross_level_align(self, mapping, target_level)` (`index.py:157`) makes
  the consumer **inject** the mapping and the leaf never embeds geography (ADR-014). I
  verified the signature. As the maintainer of a repo that spent a long arc concluding
  the *exact same thing* ("the postprocessor holds zero spatial knowledge; the
  datafactory/consumer owns the mapping"), seeing this leaf land that boundary correctly
  is the strongest signal its governance is real, not ceremonial.
- **Architecture invariants are AST-tested**, not prose.
- **The conformance suite is plain `assert`, pytest-free** — genuinely portable into my
  CI without dragging in a test framework.
- **The summarize split (ADR-017)** pulls volatile statistics out of the stable leaf
  into a one-way-dependent sibling — a mature move.

**Bad / unexpected**
- **No `py.typed` despite a strict-typing posture** — the one self-contradiction.
- **A doc/code mismatch in the protocol surface.** README §5 implies the indexed
  protocol exposes `index`, but `protocols.py` exposes only `n_rows` + `identifiers`
  (`SpatioTemporalIndexed`), `sample_count`/`is_sample` (`Sampled`), `values` (`Frame`),
  and save/load (`Persistable`) — **no protocol exposes `.index`** (verified). So if I
  type my code against `Frame`/`SpatioTemporalIndexed` I cannot reach `.index` (hence not
  `cross_level_align`), even though every concrete frame has it. For a consumer that
  wants to depend on abstractions, the abstractions are slightly under-powered for the
  alignment use-case they exist to serve.

**Mildly harder than expected**
- First-run import needs `uv sync` / editable install; a bare `pytest` errors with
  `ModuleNotFoundError: views_frames`. `CLAUDE.md` documents `uv sync` first, so this is
  covered — a one-line note by the test commands would still save a confused first run.

---

## 5. Strongest parts

1. **Motivation → ADR → code-invariant → test is intact and traceable.** The
   cross-level fix is the exemplar (critique → ADR-014 → `cross_level_align` →
   injected-mapping fail-loud raise + tests).
2. **Executable architecture** — import-DAG and one-concept-per-file enforced by AST
   tests; immutability/zero-copy enforced by `np.shares_memory`. Not honor-system.
3. **The published conformance suite** — importable, dependency-light, governed by a
   `CONFORMANCE_FLOOR` with a documented cross-repo bump process. This is the mechanism
   I'd actually use to keep my output in contract.
4. **Agent-readiness** — `CLAUDE.md` + design-bible README + ADRs + risk register give
   an agent everything to make a correct, in-bounds change *and* a machine-checkable way
   to know it stayed in bounds. The error messages double as fix instructions.
5. **Disciplined scope** — the leaf refuses domain data, pandas, app logic, even
   sample-axis statistics. The boundary the whole platform's de-duplication depends on
   is drawn precisely and defended in code.

---

## 6. Weakest parts

1. **No `py.typed`** — the typed contract isn't delivered to consumers. *(small, high
   priority for adoption)*
2. **Protocol surface under-powered vs the alignment use-case** — no `.index` on any
   protocol, and a README §5 mismatch to fix. *(small-medium)*
3. **Scale-sensitive Python loops in a scale-justified package.** I verified:
   - `cross_level_align` remaps units with a per-element Python comprehension —
     `np.array([mapping[int(u)] for u in self._unit], …)` (`index.py:~187`). At
     full-grid scale (~10.5M rows, the #181 regime) this is an O(N) Python loop. This is
     the operation *my* FAO aggregation would call.
   - `hdi` uses `np.apply_along_axis(_hdi_1d, -1, …)` (`interval.py:22`) — a per-row
     Python loop. (`map_estimate` is in the same family.)
   - By contrast `collapse` (`reducer(frame.values, axis=-1)`) and `quantiles`
     (`np.quantile(…, axis=-1)`) **are** properly vectorized — so the issue is *specific*,
     not pervasive. Memory (the headline win) is fine; **throughput** on those three
     paths is the risk, and nothing benchmarks it. *(medium / architectural)*
4. **No runnable example / on-ramp** — the gap between "fully specified" and "I can
   adopt it this afternoon." *(small but high-leverage)*
5. **Contract unproven against a real consumer.** The conformance suite runs only on the
   built-in frames; no external adapter has exercised it yet. The cross-repo value
   ("one contract, N consumers") is asserted, not demonstrated — and my repo would be a
   natural first proof. *(tracked as Epic 3)*

---

## 7. What should be improved next (prioritized)

### Small fixes (hours; do before any consumer — me included — adopts)
1. **Add `py.typed`** to both packages and ensure hatchling ships it. Makes the strict
   types reach consumers.
2. **Add a Quickstart to the README + an `examples/` script** — index + each frame,
   `collapse`/`map_estimate`/`hdi`, `save`/`load` (npz **and** arrow), and
   `assert_frame_contract`. The single biggest adoption unblock.
3. **Add a 3-line conformance-suite usage example** ("import this, run it in your CI").
4. **Reconcile the protocol surface with README §5** — add `index` (and the members a
   consumer needs to reach `cross_level_align`) to the protocols, or correct §5. Make
   doc == code.
5. **Confirm the strict-type gate on the declared numpy floor.** The annotations use
   bare `NDArray[np.integer]`; under `disallow_any_generics` that can require a type
   parameter on older numpy stubs. CI is the authority — but it's worth confirming the
   *lower* bound of `numpy>=1.26,<3` is green, since that's a named gate. *(If red, a
   parameterized alias like `IntArray = NDArray[np.integer[Any]]` in one module fixes it
   across `index.py` / `protocols.py` / `_validation.py` / the three frames.)*

### Larger / architectural (sequence deliberately)
6. **Vectorize the three scale paths and add a guard.** Replace the `cross_level_align`
   comprehension with a vectorized remap (max-keyed lookup array, or
   `np.unique`+`searchsorted` on the mapping keys — the same trick already used in
   `aggregate.py:40`); decide whether `hdi`/`map_estimate` need vectorizing or a
   documented per-row cost. Add a coarse throughput/memory guard at representative grid
   size (the analogue of pipeline-core's `test_report_stage_memory.py`). The package is
   sold on scale; prove the scale path.
7. **Prove the contract with one real consumer (Epic 3).** I'll volunteer the obvious
   candidate: views-postprocessing already produces `(month_id, priogrid_gid)`-indexed
   prediction frames and validates fail-loud. A re-export shim + my CI running
   `assert_frame_contract` against my enriched output would convert the keystone claim
   from "looks right" to "demonstrated," and would surface any contract gaps against a
   real workload.
8. **Decide the provenance/`MetricFrame` story explicitly.** Either add `run_id` /
   `data_version` to `FrameMetadata` (and generalize toward the evaluation/metric frame
   that closes C-48), or state plainly that durable provenance and metric frames live in
   consumer/evaluation repos. Since the README front-loads C-48, leaving this implicit
   invites the same "advertised but contingent" critique the prior rounds raised.

---

## Bottom line (consumer's verdict)

As the views-postprocessing maintainer-agent: **I would adopt this**, and I think my
repo is a strong candidate to be its first real consumer (Epic 3) — the abstractions
map onto data I already move, the boundaries match conclusions my own repo reached
independently, and the contract is cleaner than my status-quo pandas handling. What
stops me adopting *today* is entirely the last-mile ergonomics in §7.1–§7.4 plus the
provenance gap in §7.8 — small, concrete, non-architectural. The hard part (the design,
the boundaries, the governance) is done, and done unusually well.
