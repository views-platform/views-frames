# Critique 02 — Falsification: the domain-free cross-level alignment claim

> **Source:** a Popperian falsification audit (`/falsify`) run on 2026-06-20,
> grounded empirically in the *actual* reconciliation code of the consumer repos
> (`views-reporting`, `views-pipeline-core`) read read-only via `gh`. Reviewer:
> Claude (Opus 4.8).
>
> **Relationship to the other critiques:** `critique_00.md` is the broad reflection
> across all four design documents; its **finding #1** (the `SpatioTemporalIndex`
> domain-purity fork) and **finding #5** (cross-level alignment specified vs merely
> motivated) flagged this as the package's biggest *unresolved decision*. This
> document upgrades that from "unresolved" to **"the strong form of the claim is
> provably false,"** with empirical evidence from the live code.
>
> **Artifact:** the failing test stubs that enforce the fix live in
> `tests/test_falsification_domain_free_crosslevel.py` (5 stubs, TDD-red against the
> current README). This document is the human-readable write-up.

---

## 0. The claim under audit

> **views-frames can be a numpy-only, domain-free, maximally-stable leaf *and*
> deliver the cross-level cm↔pgm alignment its consumers require.**

Reformulated to be falsifiable:

> *The country→cells alignment that views-reporting and views-pipeline-core require
> can be implemented inside views-frames using only pure-numpy operations over the
> declared `SpatioTemporalIndex` fields (`time:int[N]`, `unit:int[N]`, `level`),
> with no `views_*` import and no embedded versioned domain mapping — and therefore
> without forcing the leaf to change for data reasons.*

This is **the package's own conjoined self-claim**: the purity constraints of
README §3 / §11, joined to the value proposition of §4.3 (*"this is what gives
arrays the label-alignment that today drags pandas back in — cm↔pgm
reconciliation…"*) and the explicit consumer requirements (reporting perspective
§8.2; pipeline-core perspective §9.3). It is not a strawman — it is what the
documents promise.

---

## 1. Verdict

# FALSIFIED — 5 hard falsifications, 0 soft.

The claim is disproven **as a conjunction**. A numpy-only, domain-free,
maximally-stable leaf **cannot** deliver cross-level cm↔pgm alignment, because that
alignment provably requires an external, viewser-sourced, **time-varying**
`priogrid→country` mapping that is:

1. **not in the identifier arrays** — unrecoverable from `time[N]`/`unit[N]`/`level`;
2. **forbidden domain data** under §3 (no `views_*`, no domain data) and §11 (GAUL
   mapping → consumer repos);
3. **versioned** (priogrid-metadata revisions; month-varying country assignment),
   so embedding it makes the leaf change for **data** reasons, breaking the §8
   maximal-stability contract.

The two halves of the claim are not merely both hard — **they are mutually
exclusive.** Deliver the cross-level join → you must embed forbidden, versioned
data → you break "domain-free" and "maximally stable." Stay domain-free and stable
→ you cannot deliver the join. There is no configuration of the leaf, as specified,
that satisfies both.

---

## 2. The decisive empirical evidence (Probe 1)

The audit did not reason from the README's prose; it read what cm↔pgm
reconciliation **actually does today**.

- `views-reporting/reconciliation/reconciliation.py` drives the country↔grid join
  off `build_country_to_grids_cache` / `_country_to_grids_cache`
  (`:15`, `:74`, `:96`).
- That cache is built in `views-reporting/metadata/entity_metadata.py:147`
  (`build_country_to_grids_cache`) from `get_country_id()`, which reads a
  `priogrid_gid → country_id` association.
- That association is **fetched from viewser**:
  `Queryset("pg_metadata", "priogrid_month") … .fetch()`
  (`entity_metadata.py:10,45–75`).
- The association is **time-aware**: the code carries `previous_country_id` and a
  `(time_id, country_id)` MultiIndex because *which country a grid cell belongs to
  varies by month* (borders/assignments change). The reconciliation cache happens
  to collapse it with `.first()`, but the source data is `(time, priogrid) →
  country`, not a static table.

So the mapping the cross-level join needs is external domain reference data,
acquired through the exact dependency (`viewser`) the leaf's §3 forbids, and it is
not even a static constant one could ship as a frozen array — it is versioned and
time-varying. This is **stronger than `critique_00` anticipated**: it rules out the
easy escape of "just ship a static `priogrid→country` constant inside the leaf."

`SpatialLevel` itself (pipeline-core `domain/spatial.py`, 50 LOC, the value object
README §4.3/§13.3 proposes relocating into the leaf) confirms the boundary is
narrow: it carries only `index_names` and `entity_column`
(cm→`country_id`, pgm→`priogrid_id`). It is genuinely a tiny stable enum — **but it
does not contain, and cannot derive, the cross-level mapping.** Relocating
`SpatialLevel` is safe; it just doesn't buy the cross-level alignment the pitch
attributes to "the index."

---

## 3. Probe-by-probe

| # | Cat | Probe | Verdict |
|---|-----|-------|---------|
| 1 | A/H | What does real cm↔pgm reconciliation depend on? | **HARD** — viewser-sourced, time-varying `priogrid→country` mapping; not in the arrays. |
| 2 | C | Can the declared numpy ops express one-to-many cross-level expansion? | **HARD** — `intersect`/`align`/`is_superset_of`/`argsort`/`searchsorted` are all same-axis set ops; country→cells is a lookup against an external table. |
| 3 | B | §4.3 (alignment belongs here) vs §3/§11 (no domain data) | **HARD** — direct contradiction on exactly the consumer-required case; no logic/data boundary is drawn. |
| 4 | B | Does embedding the mapping preserve §8 maximal stability? | **HARD** — the mapping is versioned reference data; embedding it makes the leaf change for data reasons. The conjunction is self-defeating. |
| 5 | H | Is cross-level alignment specified, or only motivated? | **HARD** — present only as §4.3 prose; absent from the §4.3 operation list **and** from the §13 open-decisions list. Required by both consumers, specified nowhere, tracked nowhere. |

**Risky predictions (recorded before execution):** every probe predicted the
*claim-true* outcome (mapping derivable from arrays / a declared op suffices / a
clean logic-data split exists / any embedded mapping is static / cross-level is
specified). All five predictions were refuted. None was a confirmation-shaped probe.

---

## 4. Pattern

All five probes converge on one structural fact the design documents never
confront:

> **The operation the package is sold on — "giving arrays the label-alignment that
> today drags pandas back in" — is, for the cross-level case, not an alignment
> algorithm at all. It is a lookup against time-varying, viewser-sourced, domain
> reference data.**

Each probe is a different face of that single fact: the data isn't in the arrays
(P2), it's forbidden (P1, P3), it's versioned so it breaks stability (P4), and the
document quietly demoted it from *requirement* to *prose* (P5) — which is precisely
what let the contradiction stay invisible. This is the same failure shape the
`views-appwrite` audits found (*the hard part lives at the boundary the document
waves at*), but sharper here, because the boundary being waved at sits inside the
package's own one-paragraph thesis.

---

## 5. The salvage path (what survives)

The audit is not a verdict against the package — it is a verdict against the
**strong form** of one claim. Two weaker claims survive intact and are enough to
keep the architecture:

1. **Same-level alignment, domain-free — survives unconditionally.** Intersect /
   align / reindex over `(time, unit)` at a single `SpatialLevel` needs no external
   data and is exactly the pandas-killing win §4.3 wants. This was never in dispute.
2. **The leaf owns the cross-level *protocol*; the consumer injects the *mapping*.**
   views-frames can declare a `cross_level_align(index, mapping)` signature (or a
   `CrossLevelAligner` protocol) where the `(time, priogrid)→country` mapping is a
   **parameter supplied by the consumer** (or by a separate `views-domain` /
   reference package the leaf does not depend on). The *logic* (one-to-many
   expansion, conservation-respecting reindex) is generic and domain-free; the
   *data* stays out. This keeps both conjuncts true.

The catch: option 2 is a **different, weaker claim** than "the leaf delivers the
cross-level alignment its consumers require," which is what §4.3 currently
promises. The fix is therefore primarily a **documentation/contract** change, not a
redesign — but it must be made, because as written the README over-promises a
capability that is provably unbuildable under its own constraints.

---

## 6. Required edits to the README (to turn the stubs green)

1. **§4.3** — split the operation list into *same-level* (owned, domain-free) and
   *cross-level* (protocol owned here; mapping injected). Stop attributing the
   cross-level/pandas-killing win to "the index" without qualification.
2. **§3 / §11** — state the explicit line: **alignment logic** lives in the leaf;
   **alignment data** (the `priogrid→country` mapping, viewser-sourced and
   time-varying) does not, and is injected by the consumer. Name it.
3. **§8** — confirm the mapping's exclusion is *what* preserves maximal stability
   (the leaf never versions with GAUL/priogrid-metadata).
4. **§13** — add the cross-level alignment / mapping-home question as a **blocking
   open decision** (it is currently absent). Recommended resolution: consumer-
   injected mapping + leaf-owned protocol.
5. Optionally note the empirical anchor: the mapping is `(time, priogrid)→country`
   (time-varying), per `views-reporting/metadata/entity_metadata.py`, so a static
   constant table is not a valid shortcut.

---

## 7. Register-compatible finding (for a future views-frames register)

| Field | Value |
|-------|-------|
| Tier | 2 |
| Source | falsification-audit (2026-06-20) |
| Trigger | When implementing `SpatioTemporalIndex` cross-level (cm↔pgm) alignment, confirm the `priogrid→country` mapping is a consumer-injected parameter (or lives in a non-leaf reference package), never embedded or viewser-fetched in the leaf. |
| Location | README §4.3 (alignment ops), §3/§11 (no-domain-data), §8 (stability), §13 (open decisions — currently omits this); evidence: `views-reporting/reconciliation/reconciliation.py:15,74,96`, `views-reporting/metadata/entity_metadata.py:10,45-75,147` |

A core value proposition — cross-level cm↔pgm alignment delivered by a domain-free
leaf — is unbuildable as specified: the join requires an external, viewser-sourced,
time-varying `priogrid→country` mapping that violates the leaf's no-domain-data
(§3/§11) and maximal-stability (§8) constraints, and §4.3 (alignment belongs here)
directly contradicts §3/§11 on this case. The capability is required by both
consumers (reporting perspective §8.2, pipeline-core perspective §9.3) yet specified
nowhere and absent from the §13 open-decision list. Mitigation is a contract change:
leaf owns the cross-level protocol; consumer injects the mapping. Maps to
`critique_00` findings #1 and #5.

---

## 8. Bottom line

`critique_00` ranked the domain-purity of the index as the package's #1 risk but
left it as a decision to be made. This audit closes that: **the decision is forced,
not open** — the strong claim is false, and the only viable shape is "leaf owns the
protocol, consumer injects the mapping." Make that the stated design, fix §4.3's
over-promise, add the §13 open decision, and re-run `/falsify` with the same claim
to verify. The rest of the package's thesis is untouched by this finding.

*Audit only — README and perspectives unchanged; the sole new files are this
critique and the failing test stubs it references.*
