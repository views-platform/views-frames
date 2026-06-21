# views-frames — round 02 review, from the **views-postprocessing** perspective

> **Reviewer:** Claude (Opus 4.8), acting as the AI-agent developer who maintains
> **views-postprocessing** — a *consumer* of this library (it enriches VIEWS
> predictions with geography and delivers them to the UN FAO). Same lens as round 01:
> "would I adopt views-frames, and what would I need from it?"
> **Reviewed at:** **v0.3.0**, `main` @ `f38e14a` (round 01 reviewed v0.2.0 @ `07beefb`).
> **Method — read-only static inspection.** I read the 5 commits since round 01, every
> changed source module, the quickstart, the new tests, the risk register, the ADRs/CICs,
> and the `CHANGELOG`. I traced the construct → reduce → save/load → conformance path *by
> reading*; I did **not** run `pytest`/`mypy`/`ruff` this pass (that writes caches, outside
> the single permitted write), so I treat **CI as the authority** on gate pass/fail and
> verify resolutions by reading the actual code. No source modified, nothing staged, no
> commit, no branch; the only file written is this report.
>
> **One-line verdict:** This is what a review loop is supposed to look like. Of the ten
> issues I raised in round 01, **eight are resolved in code, one is resolved by an explicit
> documented stance, and one (a durable run-identity/`MetricFrame` cure) is the deliberately
> deferred architectural piece.** The fixes are genuine improvements — correctness *and*
> performance *and* ergonomics — not box-ticking, and each is tied to a registered-and-
> resolved risk (C-19..C-23). I would now adopt this.

---

## How I checked (round 01 → round 02 scorecard)

The 5 commits since round 01 map almost one-to-one onto my round-01 findings:

| Round-01 finding (my report) | Status now | Evidence I verified by reading |
|---|---|---|
| No `py.typed` in either package | **Resolved** | `src/views_frames/py.typed` + `src/views_frames_summarize/py.typed` present; commit `8dfc8a4` (C-23) |
| No protocol exposes `.index` | **Resolved** | `protocols.py:36` `def index(self) -> SpatioTemporalIndex` (C-23) |
| `mypy --strict` red on the numpy floor | **Resolved** (CI-authority) | commit `8dfc8a4` "mypy-strict at the numpy floor" (C-19 marked RESOLVED in register) |
| `cross_level_align` per-element Python comprehension | **Resolved** | the `[mapping[int(u)] for u in self._unit]` loop is **gone**; now `np.searchsorted`/`np.unique` vectorized (`index.py`), commit `de487ef` (C-20) |
| `map_estimate`/`hdi` `apply_along_axis` per-row loops | **Resolved** | `point.py`/`interval.py` now use `np.take_along_axis`, `np.argmax/argmin(axis=…)`, `np.sort(axis=-1)`; commit `371a605` (C-22) |
| `(time, unit)` uniqueness invariant unstated | **Resolved (and well)** | documented stance in `index.py:28` + new `has_unique_rows()` helper at `:167`; commit `371a605` (C-21) |
| No runnable quickstart / examples | **Resolved** | `examples/quickstart.py` (construct → `collapse` → `save`/`load` → `assert_frame_contract`); commit `f38e14a` |
| No conformance-suite usage snippet | **Resolved** | the quickstart calls `assert_frame_contract(pf)` inline (`examples/quickstart.py:53`) |
| Contract unproven against a real consumer | **Substantially de-risked** | new `tests/test_proxy_adapter.py` drives a datafactory-style `[T,H,W,C]` adapter through `assert_frame_contract` + `assert_summarizer_contract`, honestly labelled the *interim* proof |
| No scale/benchmark guard | **Resolved** | `tests/test_summarize_scale.py` added |
| `FrameMetadata` lacks `run_id`/`data_version` | **Resolved by documented stance** | still `model/run_type/timestamp/seed`, but ADR-001 now names this the "typed home for the run-identity cure (C-48/#178)", evolvable by **back-compatible MINOR additions**; consumer owns provenance *resolution* |

That the team also **registered my findings as C-19..C-23 and marked them RESOLVED** is, from a consumer's chair, the most reassuring signal of all: there is a real review → register → fix → resolve loop here, not just a patch.

---

## 1. Does it now do what I need it to do?

**Yes — more so than round 01.** Purpose and structure were already clear; what changed is that I can now *act* without reading the source. `examples/quickstart.py` is the on-ramp I asked for: it constructs an index and frame, reduces with `collapse`, round-trips through `save`/`load`, and self-checks with `assert_frame_contract` — the exact five-line path a consumer (or an agent) needs. The abstractions still map cleanly onto my pipeline's `(month_id, priogrid_gid)` prediction data, and the conformance oracle is now *demonstrated* in a runnable file rather than only described.

The one thing I still cannot get *from the leaf alone* is the durable provenance my FAO deliveries need (`run_id`/`data_version`) — but that is now a **documented, deliberate** boundary (ADR-001: the leaf carries typed optional fields; the consumer owns provenance resolution; new fields are MINOR additions). That is the right call, and it means the leaf is *ready* for the C-48 cure even though the cure itself isn't shipped here.

## 2. Does it do things the way I would want?

**Yes, and the round saw the interfaces get *more* right, not just more complete.**
- The biggest example: `cross_level_align` didn't just get vectorized — it became **time-aware and `(time,unit)`-keyed** (commit `de487ef`, a deliberate `feat(index)!` breaking change). In round 01 the mapping was static; ADR-014 says the pg→country mapping is time-varying. So this change fixed a *latent correctness bug*, not only a perf loop. As the maintainer of the repo that independently concluded "the consumer owns the (time-varying) mapping," I read this as the leaf converging on the correct boundary.
- The **uniqueness stance** is exactly what I asked for: frames *may* contain duplicate rows (needed for pre-aggregation), the same-level joins assume uniqueness and say so, and `has_unique_rows()` lets a careful consumer check before joining. Documented invariant + opt-in guard — textbook.
- The protocol surface is now usable for the alignment case (it exposes `.index`), closing the doc↔code mismatch I flagged.
- Architecture is still executable (AST import-enforcement), immutability still tested with `np.shares_memory`, scope still disciplined. The summarize statistics are now uniformly vectorized — `collapse`/`quantiles` already were, and `map_estimate`/`hdi` joined them, so the whole reduction layer is now bounded.

## 3. What has improved since the previous round?

Everything in the scorecard above, but three improvements *meaningfully change the design*, not just the surface:
1. **Time-aware cross-level alignment** — a correctness fix (mapping is time-varying), delivered as an honest breaking change while pre-1.0.
2. **A uniform, vectorized reduction layer** — the package's headline scale claim now holds on *throughput* as well as memory, and there's a `test_summarize_scale.py` guard so it stays that way.
3. **The in-repo adapter proxy** — `test_proxy_adapter.py` proves the contract end-to-end against a realistic gridded adapter shape with *no sibling-repo change*. It is candid that the real proof is a consumer's migration, but as an interim de-risk it converts "looks right" into "demonstrably composes."

Easier to *use*: the quickstart + `py.typed` together mean I can import, get types in my checker, and copy a working snippet — the two things missing in round 01.

## 4. What is still missing?

Much less than round 01. What remains:
- **A real cross-repo consumer running the conformance suite in *its* CI.** The proxy is a strong interim, but the keystone claim ("one contract, N consumers") is still proven in-repo, not in-the-wild. (Honestly acknowledged in the proxy docstring.)
- **The durable run-identity / `MetricFrame` cure (C-48).** The leaf is now *ready* (extensible typed metadata, documented stance), but the actual fix — a metric/evaluation frame and/or the `run_id`/`data_version` fields populated end-to-end — is not built here and remains the largest unshipped architectural piece. Since the README still front-loads C-48 as motivation, the gap between "enables" and "delivers" persists (smaller now, but present).
- **Minor:** no new ADR records the breaking `cross_level_align` semantics change or the uniqueness stance as first-class decisions — they live in commit messages, the register, and a docstring. For a leaf others will pin, an ADR amendment (or a short ADR-018) capturing "cross_level_align is `(time,unit)`-keyed and time-aware" would make the breaking-change rationale discoverable from the decision record, not just `git log`.

## 5. What surprised me this round?

**Good surprises**
- **The breaking change was the *right* one and was taken willingly.** Teams often vectorize a loop and quietly preserve a wrong signature; here they changed the signature to make the mapping time-varying because the domain demands it. That is maturity.
- **Findings became registered, resolved risks.** Seeing my round-01 points as `C-19..C-23 — RESOLVED` (not just "fixed in a PR") is the strongest evidence the governance loop is real.
- **The reduction layer is now fully vectorized** with a scale guard — the scale story is no longer asserted, it's tested.

**Mild / watch-items (not bad, but worth naming)**
- **Version cadence vs. stability promise.** v0.2.0 → v0.3.0 carried a breaking index change. Pre-1.0 and pre-adoption this is fine (no consumer is pinned yet), but the whole point of this leaf is *stability for N consumers*; once one consumer adopts, breaking changes get expensive. A stated "we will reach 1.0 / freeze `cross_level_align` before the first real consumer pins" would reassure adopters.
- **Decisions living in commit messages.** The substance (time-aware alignment, uniqueness) is excellent, but a future agent reading only `docs/ADRs/` wouldn't find the *why* of the breaking change. (See §4 minor.)

## 6. Strongest parts now

1. **A demonstrably functioning review→register→fix→resolve loop.** Round 01's findings are closed *and* traced in the register. This is the rarest and most valuable property a foundational library can have.
2. **Correctness-grade boundaries.** Time-aware injected cross-level mapping; documented uniqueness; immutability/zero-copy — all enforced or tested, none honor-system.
3. **A bounded, vectorized scale path with a guard test** — the headline claim is now verified, not just argued.
4. **Consumer on-ramps** — quickstart, `py.typed`, the proxy adapter, conformance-in-the-quickstart. I can adopt from the package alone now.
5. **Disciplined, principled scope** — still numpy-only, still domain-free, with the provenance/`MetricFrame` line drawn explicitly in ADR-001 rather than left implicit.

## 7. Weakest parts now

1. **The keystone is still proven by proxy, not by a live consumer.** Highest-value remaining gap; everything else is downstream of it. *(architectural, but really a coordination/adoption task)*
2. **C-48 / durable run-identity is "enabled, not delivered."** The leaf is ready; the cure isn't shipped, and the README still leads with it. *(architectural; partly out of this repo's scope)*
3. **Breaking-change discoverability** — the most consequential semantic change of the round (time-aware `cross_level_align`) is not in the ADR record. *(small/medium)*
4. **No 1.0 / freeze signal** for adopters deciding whether to pin. *(small; governance)*

## 8. What should be improved next (prioritized)

### Small (hours; do before the first real consumer pins)
1. **Add an ADR (or amend ADR-014/015) for the `(time,unit)`-keyed, time-aware `cross_level_align`** and the uniqueness stance, so the breaking-change rationale is in the decision record, not only `git log`/register.
2. **State a path to 1.0 / a `cross_level_align` freeze** in `GOVERNANCE.md` — "this signature is stable from vX; breaking changes after the first consumer pins require a MAJOR + the merge-train process." Adopters need this to commit.
3. **Cross-link the quickstart and the proxy adapter from the README** so a consumer lands on the runnable on-ramp and the "here's how your adapter conforms" example immediately.

### Larger / architectural (sequence deliberately)
4. **Land one real consumer running the conformance suite in its CI.** I'll re-volunteer views-postprocessing: it already emits `(month_id, priogrid_gid)` prediction frames and validates fail-loud, so wiring `assert_frame_contract` against my enriched output (behind a re-export shim) would convert the proxy into a live proof and stress the contract against a real workload. This is the single highest-value next milestone.
5. **Decide and schedule the C-48 endgame.** Either (a) add the `run_id`/`data_version` fields and show the end-to-end run-identity cure with one consumer, or (b) move the metric/evaluation frame to views-evaluation and soften the README's C-48 framing from "the cure" to "the substrate for the cure." Right now it's the one place "enables vs delivers" still reads as overclaim.

---

## Bottom line (consumer's verdict)

Round 01 I said "I would adopt this, but the last mile isn't paved." Round 02 the last mile is paved: `py.typed`, a runnable quickstart, a usable protocol surface, a vectorized + guarded scale path, a documented uniqueness stance, and — best of all — a *correctness* fix to cross-level alignment delivered as an honest breaking change, with every round-01 finding registered and resolved. **I would adopt views-frames now**, and views-postprocessing remains the natural candidate to be its first live consumer (turning the in-repo proxy into the real cross-repo proof). What's left is adoption and the C-48 endgame — coordination and one deferred architectural piece — not leaf-internal quality. This is a strong, well-governed v0.3.0.
