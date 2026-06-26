
# ADR README and Governance Map — views-frames

This repository uses Architecture Decision Records (ADRs) to govern structural, semantic,
and operational behavior. Because `views-frames` is currently a **design bible** (a
README, consumer-review findings, design critiques, and falsification stubs — no `src/` yet), these
ADRs describe the **intended** architecture; when the leaf is stood up, code must conform
to them (and to the README, which is itself authoritative).

ADRs are divided into:

1. **Constitutional ADRs (000–009)** — foundational architectural rules.
2. **Governance ADRs (010)** — the technical risk register.
3. **Project-Specific ADRs (011–016)** — the ratified contract decisions.

---

## Constitutional ADRs

- **ADR-000** — [Use of ADRs](000_use_of_adrs.md). Establishes the ADR practice; the design bible is the seed.
- **ADR-001** — [Ontology of the Repository](001_ontology_of_the_repository.md). The closed set of allowed categories (Spatiotemporal Index, Identifier Vocabulary, Frames, Protocols, Metadata Header, Construction Validation, Serialization Adapters) and the explicit non-entities (pandas/`views_*`, the cross-level mapping, `MetricFrame`/`EvaluationFrame`, adapters, the grid, a `_BaseFrame` god-class).
- **ADR-002** — [Topology and Dependency Rules](002_topology_and_dependency_rules.md). The leaf at the root of the platform DAG (every arrow points toward it; imports nothing internal; two-leaves rule with `views-appwrite`) and the intra-package layering (index/spatial_level/protocols/_validation → frames → io).
- **ADR-003** — [Authority of Declarations Over Inference](003_authority_of_declarations_over_inference.md). Typed metadata header (not a free-form dict); `time` opaque; consumer owns the cross-level mapping and provenance resolution; fail loud on ambiguity.
- **ADR-004** — [Rules for Evolution and Stability](004_rules_for_evaluation_and_stability.md) — **Deferred** (activate at `v0.1.0` when a consumer pins the leaf; SemVer for an N-repo contract, README §8).
- **ADR-005** — [Testing as Mandatory Critical Infrastructure](005_testing_as_mandatory_critical_infrastructure.md). Red/beige/green doctrine; the published conformance suite consumers re-run; property tests for alignment laws; the copy-vs-view memory property; falsification stubs.
- **ADR-006** — [Intent Contracts for Non-Trivial Classes](006_intent_contracts_for_non_trivial_classes.md). CIC requirement; first subjects are `SpatioTemporalIndex`, the frames, the protocols.
- **ADR-007** — [Silicon-Based Agents as Untrusted Contributors](007_silicon_based_agents_as_untrusted_contributors.md). Tooling = Claude Code; anti-truncation rule for the contract-preserving relocation of the twins.
- **ADR-008** — [Observability and Explicit Failure](008_observability_and_explicit_failure.md). Fail loud at construction (`ValueError`/`TypeError`); no log-and-continue; minimal runtime logging for a value-object leaf.
- **ADR-009** — [Boundary Contracts and Configuration Validation](009_boundary_contracts_and_configuration_validation.md). The protocols as the published contract; construction-time invariant validation; the injected-mapping boundary; the `io/` round-trip; the uv+hatchling packaging boundary.

## Governance ADRs

- **ADR-010** — Technical Risk Register. Formalises the technical risk register as an internal governance artifact, seeded 2026-06-21 with **17 concerns** (C-01..C-18) + **6 disagreements** (D-01..D-06) from the design critiques and falsification stubs.

---

## Governance Structure (Conceptual Map)

- **Ontology (001)** defines what exists.
- **Topology (002)** defines structural direction.
- **Authority (003)** defines who owns meaning.
- **Boundary Contracts (009)** define interaction rules.
- **Observability (008)** enforces failure semantics.
- **Testing (005)** verifies system integrity.
- **Intent Contracts (006)** bind class-level behavior.
- **Automation Governance (007)** constrains silicon-based agents.
- **Risk Register (010)** tracks known gaps against the above.

Together, these define the invariant layer of the system.

---

## Project-Specific ADRs (011–016) — the ratified contract decisions

These ratify the six resolved decisions from the design bible (README §13a). All **Accepted**
2026-06-21; each cites the risk-register IDs it resolves.

- **ADR-011** — [Twin-unification model (Option C)](011_twin_unification_option_c.md). Share only `SpatioTemporalIndex` + `_validation` + protocols + `io/`; relocate the frames as separate sibling classes; reject the `_BaseFrame` god-class (A); defer the composed header (B). Resolves D-03; relates to C-16, C-03.
- **ADR-012** — [Sample axis convention](012_sample_axis_convention.md). Always an explicit trailing axis (`S ≥ 1`); `is_sample = S > 1`; `collapse` reduces the trailing axis; one shape contract. Relates to C-02, C-16, C-17.
- **ADR-013** — [Metadata / identifier model](013_metadata_and_identifier_model.md). Typed optional-extensible header (not free-form); identifiers fixed `{time, unit}`, future identifiers optional-only. Relates to C-08, C-11, C-09, D-02.
- **ADR-014** — [Cross-level alignment boundary](014_cross_level_alignment_boundary.md). Leaf owns the `cross_level_align(index, mapping)` protocol; consumer injects the time-varying mapping; never embedded/fetched. Resolves C-14, C-15, D-01.
- **ADR-015** — [`SpatialLevel` relocation](015_spatiallevel_relocation.md). Identifier vocabulary only; fix the C-65 time-first index-tuple and the `priogrid_gid`/`priogrid_id` inconsistency, not port them. Resolves C-18.
- **ADR-016** — [Conformance-floor + ownership/release](016_conformance_floor_and_ownership.md). Governed conformance-floor every consumer runs in CI; named owner + cross-repo MAJOR-bump process. Resolves C-05, C-10, C-13; carries deferred ADR-004's scope.
- **ADR-017** — [Posterior/sample summarization is a sibling package](017_summarization_is_a_sibling_package.md). Sample-axis reduction (MAP/HDI/quantiles/collapse) lives in the `views_frames_summarize` sibling package, not the leaf; the leaf keeps only the structural `sample_count`/`is_sample`.
- **ADR-018** — [API freeze at v1.0.0](018_api_freeze_v1.md). v1.0.0 freezes the public surface (frames + index + protocols + conformance + summarizer estimators); ends the pre-1.0 breaking-in-MINOR latitude; records the frozen `(time, unit)` cross-level key, the row-uniqueness stance, and `select`/`reindex`. Resolves C-27 (with GOVERNANCE).
- **ADR-019** — [Coherent posterior summary — the constrained-nested HDI tower](019_coherent_posterior_summary_hdi_tower.md). The `views_frames_summarize` tower estimators (`hdi_tower`/`tower_point`/`bimodality`/`summarize_tower`): nested-by-construction HDIs on a fixed canonical grid, the mass-aware `tip_mass` MAP, and a fail-loud config. Amended for the outside-in rebuild (C-44) and the distribution-agnostic quiet rule (C-45).
- **ADR-020** — [The `MetricFrame` contract lives in views-evaluation, on the views-frames substrate](020_metricframe_contract_home.md). Ratifies (under the GH#109 driver) that evaluation-output types stay out of the leaf; the leaf provides only the `FrameMetadata` substrate and the conformance/IO patterns. Records the provenance split (C-47) and the envelope-drift mitigation (C-46); keeps `CONFORMANCE_FLOOR` at 1.0.0. Extends C-01.
- **ADR-021** — [Threshold exceedance-probability estimator (`exceedance`)](021_exceedance_probability_estimator.md). Adds the `views_frames_summarize` per-row survival-fraction estimators (`exceedance`/`exceedance_reducer`, `P(Y > c)`): caller-supplied required thresholds (no default, no config), strict `>`, fail-loud NaN, geography-blind (country = `aggregate_distributions` → `exceedance`). Settles D-07/D-08; records C-49/C-50; additive/MINOR, `CONFORMANCE_FLOOR` stays 1.0.0.
- **ADR-022** — [Worst-case scenario summary — the `expected_shortfall` tail mean](022_worst_case_expected_shortfall.md). Adds the `views_frames_summarize` worst-case estimator `expected_shortfall` (mean of the worst `⌈t·S⌉` draws — a coherent tail-risk measure, the companion to `exceedance`): caller-supplied required tail levels (no default, no config), upper-tail only, **never `max`**, fail-loud NaN, geography-blind. Best-case ships no code (low quantile + `exceedance(0)`). Settles D-10; records C-55/C-56; additive/MINOR (v1.6.0), `CONFORMANCE_FLOOR` stays 1.0.0.
- **ADR-023** — [Forecast reconciliation is a sibling package (`views_frames_reconcile`)](023_reconciliation_is_a_sibling_package.md). Adds a third sibling package (mirrors ADR-017): the numpy-only, `views_frames`-only forecast reconciler (`reconcile_proportional`/`ReconciliationModule` — make pgm grid forecasts sum to cm country totals per draw), relocated **WET** from views-postprocessing and proven bit-identical. Charter: frame-reconciliation algorithms only; **never fetch the mapping** (injected as arrays, like `cross_level_align`); no IO/scoring/plotting/foreign `views_*`. Import-DAG `views_frames_reconcile → {views_frames}`; additive/MINOR (v1.7.0), `CONFORMANCE_FLOOR` stays 1.0.0.

---

## Recommended Adoption Order

Constitutional ADRs are designed to be adopted incrementally:

- **Foundation:** ADR-000, ADR-003, ADR-008 (load-bearing fail-loud invariants).
- **Structure:** ADR-001, ADR-002.
- **Testing & Intent:** ADR-005, ADR-006.
- **Boundaries & Automation:** ADR-007, ADR-009.

ADR-004 (Evolution & Stability) is intentionally deferred; activate it when `v0.1.0` ships
and consumers begin pinning the leaf.
