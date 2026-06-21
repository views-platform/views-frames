# Physical Architecture Standard — views-frames

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

## 2. Directory Ontology (the `src/views_frames/` layout)

This repository uses a **single-package layout** under `src/views_frames/`. Each file maps
to an ADR-001 ontological category, with the dependency layering of ADR-002 (lowest layer
first):

```
src/views_frames/
├── __init__.py          # EXPLICIT re-exports only (no `import *`)
├── index.py             # SpatioTemporalIndex value object + same-level alignment   (Category 1)
├── spatial_level.py     # SpatialLevel enum (cm/pgm) — identifier vocabulary         (Category 2)
├── protocols.py         # Frame / SpatioTemporalIndexed / Sampled / Persistable      (Category 4)
├── _validation.py       # shared construction-time invariants (private helper)       (Category 6)
├── feature_frame.py     # FeatureFrame      ── one concept per file                   (Category 3)
├── prediction_frame.py  # PredictionFrame                                            (Category 3)
├── target_frame.py      # TargetFrame      (anticipated)                             (Category 3)
├── weight_frame.py      # WeightFrame      (anticipated)                             (Category 3)
├── mask_frame.py        # MaskFrame        (anticipated)                             (Category 3)
└── io/                  # serialization adapters — SEPARATE from frames (SRP)        (Category 7)
    ├── __init__.py
    ├── npz.py           # native save()/load() (.npy + .npz)
    └── arrow.py         # flat columnar (.parquet) — the scalable disk format
```

Layering (ADR-002): `index`/`spatial_level`/`protocols`/`_validation` are the lowest layer;
the frame files depend on them; `io/` sits on top and imports the frames. Nothing lower may
import `io/`; a frame must not know how it is serialized.

A new developer should infer every responsibility from this tree **without reading bodies**.

---

## 3. No Dumping Grounds

A file accumulating loose helpers, types, constants, or unrelated classes means a boundary
is wrong — split it. There is no `utils.py`, no `helpers.py`, no `models.py`. The
construction-validation helper is `_validation.py` and is a focused private module, not a
catch-all; it must not grow into a god-class (ADR-001 Category 6).

---

## 4. Import Conventions

- **Explicit Imports:** Avoid `from module import *`. `__init__.py` uses named re-exports so the public API is statically analyzable.
- **Circular Dependency Guard:** Follow ADR-002. Dependencies flow strictly toward the lowest layer; `index.py`/`_validation.py` must never import a frame, and no core module may import `io/`.
- **No `views_*`, no pandas in the core:** the numbered constraint of ADR-001/002 is also a physical rule — `pyarrow` appears only under `io/`.

---

## 5. Enforcement

Compliance with this standard is verified during code review (and, once the leaf is stood
up, an ADR-compliance audit). PRs violating this standard will be rejected until the
structure is rectified.

**"The structure of the files is as rigorous as the logic of the code."**
