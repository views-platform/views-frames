# Class Intent Contract: FrameMetadata

**Status:** Active
**Owner:** VIEWS platform maintainers
**Last reviewed:** 2026-08-18
**Related ADRs:** ADR-001, ADR-003, ADR-013, ADR-018, ADR-020

> Implemented in v0.1.0 (`src/views_frames/metadata.py`). This contract governs that
> implementation.
>
> Written 2026-08-18 (register **C-85**, epic #240 / S5). It was missing while
> `docs/CICs/README.md` claimed "fully contracted" — the **third** time that claim was
> wrong, after `Reconcile.md` (C-64) and `Conformance.md` (C-81).

---

## 1. Purpose

`FrameMetadata` is the **typed provenance header** every frame carries. It answers "where
did this array come from" in declared fields rather than a free-form dict, so consumers
cannot diverge on key names (ADR-013).

It is a frozen dataclass of six all-optional fields plus a symmetric dict codec. It is small
on purpose: the header travels with the frame through `save`/`load` and across the wire, and
every field in it is a field every consumer must agree on.

---

## 2. Non-Goals (Explicit Exclusions)

- **Not a free-form dict.** A `Dict[str, Any]` was rejected precisely because it cannot be
  validated and re-opens the run-identity ambiguity (ADR-003; views-reporting's C-48).
- **Not a place for evaluation-specific provenance.** `scoring_code_version`, full-precision
  `evaluation_timestamp` and friends stay in views-evaluation's `MetricFrame`. The header is
  **generic-only** — meaningful for *any* frame (ADR-020, register C-47).
- **It does not resolve provenance.** It records what a producer declared. Deciding which run
  is authoritative, or reconciling two frames that disagree, is consumer policy (ADR-001
  Category 5).
- **It does not validate its own field *values*.** See §4.
- **`feature_names` is not a header field.** It is a `FeatureFrame` constructor argument,
  validated there against the feature axis (ADR-013 as-built amendment).

---

## 3. Responsibilities and Guarantees

- **Frozen and hashable-by-value.** `@dataclass(frozen=True)`; two headers with equal fields
  are equal. A frame's `with_metadata` returns a new frame sharing the values buffer.
- **All six fields are optional and default to `None`:** `model`, `run_type`, `timestamp`,
  `seed`, `run_id`, `data_version`. A frame constructed without metadata gets an empty header,
  not `None` — `frame.metadata` always returns a `FrameMetadata`.
- **`to_dict()` omits unset fields.** Only fields that are not `None` appear. An empty header
  serializes to `{}`.
- **`from_dict()` ignores unknown keys.** This is deliberate forward-compatibility (ADR-013
  as-built amendment): a header written by a newer version loads under an older one instead of
  raising. **The consequence is that the unknown fields are silently dropped** — see §6.
- **Round-trip is lossless for known, set fields.** `from_dict(to_dict())` reproduces the
  header. This is the property `save`/`load` relies on, via the frame-state contract that keeps
  `io/` free of per-frame schema (register C-09).
- **Adding a field is MINOR; removing or renaming one is MAJOR** (ADR-018, GOVERNANCE.md).

---

## 4. Inputs and Assumptions

- Field values are taken **as declared**. The header does not check that `timestamp` is a
  plausible epoch, that `seed` is non-negative, or that `run_id` matches any registry. Those
  are producer concerns, and inventing a validation rule here would be the semantic inference
  ADR-003 forbids.
- `from_dict` accepts any `Mapping[str, Any]`. Values are not coerced: a `timestamp` arriving
  as a string stays a string.
- **The type annotations are a declaration, not an enforcement.** Nothing raises if a field is
  set to the wrong type. `mypy --strict` catches it at the call site; runtime does not.

---

## 5. Outputs and Side Effects

- `to_dict() -> dict[str, Any]` — a plain dict of set fields. No side effects.
- `from_dict(mapping) -> FrameMetadata` — a new header. No side effects.
- **Serialization path:** the frame's `save` calls `metadata.to_dict()` and the codec writes it
  into `header.json`; `load` passes the parsed dict back through `from_dict`. The header never
  reaches `io/` as a `FrameMetadata` instance — `io/` sees a plain dict and carries no per-frame
  schema (C-09, ADR-002 as amended).

---

## 6. Failure Modes and Loudness

| Situation | Behaviour | Loud? |
|---|---|---|
| Unknown key in `from_dict` | **Dropped silently** | ❌ **no** |
| Field set to the wrong type | Accepted at runtime | ❌ no (caught by `mypy --strict`) |
| Mutating a field after construction | `FrozenInstanceError` | ✅ yes |
| Field left unset | Defaults to `None`, omitted by `to_dict` | n/a — by design |

**The unknown-key drop is the one worth understanding.** It is the deliberate cost of
forward-compatibility, and it has a directional consequence: **a header written by a newer
version and read by an older one loses the fields the older version does not know about, with
no signal.** If that frame is then re-saved, the loss is persisted.

This is accepted (ADR-013) and pinned by a test (`tests/test_frames.py`), and it is the reason
adding a field is MINOR rather than free: the *writer* gains a field, and every older reader
silently drops it until it upgrades. It is also why register **C-79** — no test that today's
loader reads a file written by an older release — matters more here than the header's small
size suggests.

---

## 7. Boundaries and Interactions

- **Composed into every frame.** `FeatureFrame` / `PredictionFrame` / `TargetFrame` each hold
  one and expose it as `.metadata`; `with_metadata(new)` returns a new frame sharing the values
  buffer (C-07).
- **`views_frames_reconcile` reads it, and deliberately does not write to it.** The
  reconciliation *mode* is reported on `ReconciliationResult`, never stamped on the leaf frame's
  header (D-12).
- **views-evaluation's `MetricFrame` reuses the type**, rather than the leaf growing evaluation
  fields (ADR-020, C-47). That reuse is the boundary C-46 tracks.
- **`io/` never sees the class** — only the dict.

---

## 8. Examples of Correct Usage

```python
from views_frames import FrameMetadata, PredictionFrame

md = FrameMetadata(model="hydranet", run_type="forecast", run_id="2026-08-run-14")
frame = PredictionFrame(y_pred, index, md)

frame.metadata.model                 # "hydranet"
frame.metadata.to_dict()             # {"model": ..., "run_type": ..., "run_id": ...}

# Replace the header without copying the values buffer:
relabelled = frame.with_metadata(FrameMetadata(model="hydranet", run_type="calibration"))
```

---

## 9. Examples of Incorrect Usage

```python
md.model = "other"                   # raises FrozenInstanceError — headers are immutable

FrameMetadata(scoring_code_version="abc")   # TypeError — evaluation provenance is not
                                            # generic; it belongs in views-evaluation's
                                            # MetricFrame (ADR-020, C-47)

FrameMetadata.from_dict({"model": "x", "future_field": 1}).future_field
                                     # AttributeError — unknown keys are dropped, not stored

# Do not infer domain meaning from a field the leaf declares as opaque:
level = frame.metadata.run_type.split("_")[0]   # ADR-003: no semantic inference
```

---

## 10. Test Alignment

- **Green:** `to_dict`/`from_dict` round-trip preserves set fields
  (`test_metadata_to_from_dict_roundtrip`, `test_metadata_provenance_roundtrip`); unset fields
  are omitted from `to_dict` (`test_metadata_generic_provenance_fields_default_none`) — all in
  `tests/test_frames.py`. Metadata survives row selection (`tests/test_select.py:88`).
- **Beige:** `with_metadata` allocates no second `values` buffer — the copy-vs-view property
  (`tests/test_properties.py::test_with_metadata_shares_the_values_buffer`, register C-07).
- **Red:** mutation raises `FrozenInstanceError` (`test_metadata_is_frozen`); unknown keys are
  dropped rather than raising (`test_metadata_ignores_unknown_keys`). The second is a red test
  pinning a *deliberate silent* behaviour, so the day someone decides it should be loud, this
  contract and that test have to change together.

**Two guarantees in §3 are not pinned by any test**, found while writing this contract and
recorded rather than glossed:

1. **The `save`/`load` header round-trip is pinned for `PredictionFrame` only**
   (`tests/test_frames.py:107`, `assert loaded.metadata == pf.metadata`). `FeatureFrame` and
   `TargetFrame` have no equivalent assertion — `test_feature_frame_save_load_preserves_names`
   covers `feature_names`, not the header.
2. **Nothing asserts that a frame built without metadata exposes an empty header** rather than
   `None`, though §3 guarantees it and every consumer reading `.metadata` depends on it.

Both are one-line additions to an existing test file. They belong to **S9 (#249)**, which owns
the test suite's self-description under register C-80; noted there. This contract states the
guarantee regardless — that is what a CIC is for (ADR-006: tests are derived *from* the
contract), and naming the gap is better than a §10 that reads complete.

---

## 11. Evolution Notes

- **Adding an optional field is MINOR** and does not bump `CONFORMANCE_FLOOR` (ADR-018,
  GOVERNANCE.md). Adding one has a cost older readers pay silently — see §6.
- **Making unknown keys loud would be MAJOR**, and would need a versioned wire schema to be
  useful rather than merely strict. That is the `schema_version` marker C-46 is waiting on.
- **Provenance fields deferred by decision**, not oversight: anything evaluation-specific
  (ADR-020) and anything the consumer should resolve rather than record (ADR-001 Category 5).

---

## End of Contract
