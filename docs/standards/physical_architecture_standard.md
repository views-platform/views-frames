# Physical Architecture Standard — views-frames

**Last reviewed:** 2026-08-17

> The tree in §2 is authoritative and therefore perishable. When a module is added, moved or
> removed, update it in the same change and move this date. It sat unrevised from before the
> package was built until 2026-08-17, by which point it showed one of the three shipped
> packages, omitted the metadata, typing and conformance modules, and listed two files that
> were never written (register C-84).

This standard defines the mandatory structural rules for this repository to ensure
**predictable discovery** and **absolute maintainability**. It operationalizes the
"screaming architecture" requirement of the design bible (README §6): the file tree alone
must scream "data contracts."

---

## 1. The 1-Class-1-File Standard

**Every non-trivial class must live in its own file named after the class in `snake_case`.**

- **Correct:** `SpatioTemporalIndex` lives in `index.py`; `PredictionFrame` lives in `prediction_frame.py`.
- **Incorrect:** Bundling unrelated frames in a `frames.py`, or a `handlers.py`/`file.py`-style multi-class dumping ground (the ~950-LOC `_ViewsDataset` / 13-class file is the failure mode this leaf escapes).
- **Accepted exception:** A small set of genuinely tightly-coupled classes may coexist in one file only when locality meaningfully aids comprehension. The coupling must be real (tight composition), not topical.
- **Trivial exception:** Trivial data containers or exceptions directly related to a class may coexist in the same file.

When in doubt, prefer separate files. The cost of an extra file is lower than the cost of a tangled one.

---

## 2. Directory Ontology (the `src/` layout)

The wheel ships **three packages** under `src/`: the frozen data contract and two sibling
operation packages that depend on it (ADR-017, ADR-023). The siblings never import each
other. Inside `views_frames`, each file maps to an ADR-001 ontological category, ordered by
the dependency layering of ADR-002 (lowest layer first):

```
src/views_frames/           # the data contract — numpy only, depends on nothing, frozen
├── __init__.py             # EXPLICIT re-exports only (no `import *`)
├── _typing.py              # IntArray / Float32Array aliases          (private helper;
│                           #   no ADR-001 category — a typing alias, not an ontological
│                           #   entity; register C-19)
├── metadata.py             # FrameMetadata — the typed provenance header   (Category 5)
├── spatial_level.py        # SpatialLevel enum (cm/pgm)                    (Category 2)
├── _validation.py          # shared construction-time invariants           (Category 6)
├── io/                     # serialization adapters — raw arrays in,       (Category 7)
│   │                       #   files out; never imports a frame
│   ├── __init__.py
│   ├── npz.py              # native save()/load() (.npy + .npz), mmap-capable
│   └── arrow.py            # flat columnar (.parquet); the ONLY place `pyarrow`
│                           #   may be imported
├── index.py                # SpatioTemporalIndex + same-level alignment    (Category 1)
├── protocols.py            # Frame / SpatioTemporalIndexed / Sampled /     (Category 4)
│                           #   Persistable
├── feature_frame.py        # FeatureFrame     (N, F, S)                    (Category 3)
├── prediction_frame.py     # PredictionFrame  (N, S)                       (Category 3)
├── target_frame.py         # TargetFrame      (N, 1)                       (Category 3)
└── conformance/            # the published suite consumers run in THEIR CI (no category —
    └── __init__.py         #   it verifies the ontology rather than belonging to it;
                            #   ADR-016. Imports nothing internal)

src/views_frames_summarize/ # sample-axis summarization OVER frames (ADR-017)
├── __init__.py             # EXPLICIT re-exports
├── _common.py              # block_apply / rebuild — the package's shared spine
├── config.py               # tower-family tunables; fail-loud, no defaults (ADR-019)
├── collapse.py             # the generic sample-axis fold
├── point.py                # point estimates → (N, …, 1) frames
├── interval.py             # hdi / quantiles → index-aligned arrays
├── tower.py                # the constrained-nested HDI tower              (ADR-019)
├── tower_point.py          # the tower-tip point estimate                  (ADR-019)
├── bimodality.py           # per-row multimodality flag                    (ADR-019)
├── summarize_tower.py      # single-pass coherent summary → TowerSummary   (ADR-019)
├── exceedance.py           # threshold exceedance probabilities            (ADR-021)
├── expected_shortfall.py   # worst-case tail mean                          (ADR-022)
├── aggregate.py            # conservation-correct cross-level aggregation
└── conformance.py          # the package's published contract checks (ADR-016/017)

src/views_frames_reconcile/ # top-down pgm→cm reconciliation (ADR-023)
├── __init__.py             # EXPLICIT re-exports
├── module.py               # ReconciliationModule — orchestration, geography injected
├── proportional.py         # the numpy proportional reconciler (the approximation, C-62)
├── grouping.py             # pgm rows grouped to cm totals
├── frames.py               # array → PredictionFrame adapters for this package
├── validation.py           # fail-loud validation of reconciliation inputs
├── result.py               # ReconciliationResult — the frame plus HOW it was made (D-12)
└── conformance.py          # the package's published contract checks (ADR-023)
```

**New frame types are additive (MINOR, ADR-018)** — they belong in this tree the day they
ship, and not before. This document previously listed a `weight_frame.py` and a
`mask_frame.py` as "anticipated"; neither was ever written, and carrying them here made an
authoritative tree describe a repository that did not exist (register C-84).

Layering (ADR-002): `_typing`/`metadata`/`spatial_level` are the lowest layer;
`_validation` and `io/` sit above them and import only `_typing` — both operate on **raw
arrays**, never on a frame; `index` composes `spatial_level`; `protocols` sits above
`index`; the frame files are the top layer and **call down into `io/`** to serialize
themselves. `io/` must never import a frame — that is what keeps a frame's schema from
rippling into the codecs (amended 2026-08-17, register C-82; `Persistable` places
`save`/`load` on the frame, so the frame is what reaches the serializer).

A new developer should infer every responsibility from this tree **without reading bodies**.

---

## 3. No Dumping Grounds

A file accumulating loose helpers, types, constants, or unrelated classes means a boundary
is wrong — split it. There is no `utils.py`, no `helpers.py`, no `models.py`. The
construction-validation helper is `_validation.py` and is a focused private module, not a
catch-all; it must not grow into a god-class (ADR-001 Category 6).

Two private modules carry generic-sounding names and are held to the same bar. `_typing.py`
holds exactly two array aliases (register C-19). `views_frames_summarize/_common.py` holds
exactly two functions — `block_apply` and `rebuild` — which are one responsibility:
applying a reduction block-wise over the sample axis and reassembling the result. Both are
focused modules whose names describe their scope, not dumping grounds. **If either grows a
third unrelated concern, that is the signal to split it, not to widen this exception.**

---

## 4. Import Conventions

- **Explicit Imports:** Avoid `from module import *`. `__init__.py` uses named re-exports so the public API is statically analyzable.
- **Circular Dependency Guard:** Follow ADR-002. Dependencies flow strictly toward the lowest layer; `index.py`, `_validation.py` and anything under `io/` must never import a frame. Machine-enforced by the `import-linter` contracts in `pyproject.toml` (`uv run lint-imports`) and by `tests/test_import_enforcement.py`.
- **No `views_*`, no pandas in the core:** the numbered constraint of ADR-001/002 is also a physical rule — `pyarrow` appears only under `io/`.

---

## 5. Enforcement

Compliance is verified during code review, and the two rules that can be checked mechanically
are: `tests/test_import_enforcement.py::test_one_concept_per_file` enforces §1, and the
`import-linter` contracts in `pyproject.toml` plus `test_package_dependency_dag` enforce §4.
The tree in §2 is **not** machine-checked — it is kept current by the review discipline in the
note at the top of this document. PRs violating this standard will be rejected until the
structure is rectified.

**"The structure of the files is as rigorous as the logic of the code."**
