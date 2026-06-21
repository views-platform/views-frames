# `views-frames` from the `views-appwrite` perspective

> The **storage-client** repo's view of `views-frames`. Unlike pipeline-core (which
> donates `PredictionFrame` and carries the #181 OOM), reporting (which consumes
> everything downstream), and datafactory (the other twin owner), `views-appwrite`
> is **neither a consumer nor an owner of any frame type.** It is the *other leaf* —
> a second root-of-the-DAG package that, like `views-frames`, depends on nothing
> internal and is imported by everyone who persists data. The two leaves **never
> import each other.** They meet only inside a consumer's saver/loader, at the
> moment a frame becomes bytes-in-a-store (and back).
>
> Companion to the `views-frames` README (the design bible). Where they disagree,
> the README wins on the contract; this document wins on "what the storage client
> actually does, and why coupling it to frames would be a mistake." Reconcile before
> building.
>
> **Status note (2026-06-21):** both packages are pre-implementation — `views-frames`
> is a design bible, `views-appwrite` is a roadmap + governance scaffold (ADRs
> 000–010, a risk register, contributor protocols; no code yet). This perspective is
> therefore doubly anticipatory: two not-yet-built leaves describing the boundary
> at which they will meet.

---

## 0. TL;DR for a hurried reader

- `views-appwrite` is the VIEWS platform's **generic Appwrite storage client**:
  upload/download/search of opaque **bytes + a metadata dict**, against the
  cloud forecast store. It is a leaf — numpy/SDK-only, no domain logic, no pandas,
  no `views_*` imports — extracted from the duplicated Appwrite code in
  pipeline-core and faoapi.
- It will **own no frame and consume no frame.** It moves bytes; it does not know
  (or want to know) that a blob is a serialized `PredictionFrame`. `views-frames`
  decides **how** an array is laid out on disk (its `io/arrow` flat-columnar and
  `io/npz` formats); `views-appwrite` decides **where** those bytes go. Orthogonal
  concerns, two leaves, one bridge.
- **The bridge is the consumer's saver**, not either leaf. pipeline-core's
  `AppwriteSaver`/`ViewsForecastsSaver` takes a frame, serializes it via
  `views-frames`' `io/`, and uploads it via `views-appwrite`'s `DatastoreManager`.
  faoapi does the inverse on read. Neither leaf appears in the other's import graph.
- **The quiet punchline (§6):** `views-appwrite` is already *frame-ready* precisely
  **because it knows nothing about frames.** Its contract is opaque bytes + opaque
  `Dict[str, Any]` metadata. Frames serialize to bytes and carry a metadata dict.
  The boundary already fits; the only thing that changes when frames arrive is what
  the *consumer* does with the bytes it gets back.
- **Where the two leaves jointly enable a fix:** the C-48 "wrong evaluation run"
  bug needs a *stamped, searchable run identity*. `views-frames` §13.5 gives that
  identity a home **in the frame's metadata**; `views-appwrite`'s `get_latest` /
  `search` give it a home **in the store's queryable metadata**. Two ends of the
  same provenance story; neither closes C-48 alone.

---

## 1. Who `views-appwrite` is (so the boundary serves the right storage client)

Per its own governance (ADR-001 ontology: a *generic* Appwrite client, domain
concepts are explicit non-entities; ADR-002 topology: a leaf, everyone depends
*down* onto it; ADR-003 authority: the **consumer owns metadata meaning**; ADR-008
fail-loud; ADR-009 the validated `AppwriteConfig` boundary), `views-appwrite` is the
**persistence-transport** layer of VIEWS:

- It owns **"how to talk to Appwrite"** and nothing else: a `DatastoreManager`
  facade (`upload`, `download`, `get_latest`, `search`, `delete`, `list_all`) over
  `StorageManager` (files), `MetadataManager` (a metadata database/collection),
  `CacheManager` (local disk cache with TTL), and an SDK-version `compat` layer.
- It is the **single source of truth for the forecast store** — the Appwrite
  buckets (`prod_forecasts`, the UNFAO bucket) that pipeline-core writes and faoapi
  reads. It exists to de-duplicate the ~5,000 lines of Appwrite client code that
  drifted between those two repos.
- It is **deliberately ignorant of payload shape.** `download()` returns raw bytes
  (or streams to a path); metadata is an opaque `Dict[str, Any]` passed through
  unmodified; the consumer deserializes. ADR-003 is explicit: the package must not
  infer that a metadata field means anything, and must not guess a payload's format.

`views-frames` matters to this repo **only at the seam** where a frame is persisted
to, or loaded from, the Appwrite store. Everywhere else the two are strangers — and
that is the design, not an accident.

---

## 2. The relationship in one line (two leaves, one bridge)

```
        views-frames (leaf)                         views-appwrite (leaf)
   numpy-only, the data contract              numpy/SDK-only, the storage client
   owns HOW an array serializes               owns WHERE bytes are stored
   (io/npz, io/arrow flat-columnar)           (DatastoreManager over Appwrite)
            ▲                                            ▲
            │  consumer imports both                     │
            └───────────────┬────────────────────────────┘
                            │  bridges them in its saver/loader
              views-pipeline-core / views-faoapi (consumers)
              frame ──serialize(views-frames.io)──▶ bytes ──upload(views-appwrite)──▶ store
              store ──download(views-appwrite)──▶ bytes ──load(views-frames.io)──▶ frame
```

`views-appwrite` **imports nothing from `views-frames`; `views-frames` imports
nothing from `views-appwrite`, ever.** This is not two arrows that happen to be
absent — it is a load-bearing rule on *both* sides:

- If `views-appwrite` imported `views-frames`, a non-VIEWS user of the Appwrite
  client (or one storing non-frame data) would transitively acquire the data
  contract for no reason (CRP violation; and it would make `views-appwrite` no
  longer a *generic* client — ADR-001).
- If `views-frames` imported `views-appwrite`, the data contract would be welded to
  one specific store — exactly what `views-frames` §7/§11 forbids ("adapters to …
  appwrite … live in consumer repos"). The frame must be storable to disk, to a
  parquet store, to S3, to Appwrite, with no preference baked in.

Both leaves stay leaves. The consumer is the only place that knows both names.

---

## 3. Where the two leaves actually meet (not "frame by frame")

The other perspectives have a "what we hand off / consume, frame by frame" section.
This one cannot: `views-appwrite` neither produces nor consumes a frame type. The
honest analogue is **three meeting points at the persistence boundary**, all owned
by the *consumer*, not by either leaf.

### 3.1 The write path — frame → bytes → store
A consumer holding a `PredictionFrame` (or any frame) serializes it with
`views-frames`' `io/arrow` (the flat-columnar parquet that `views-frames` §7 calls
"what crosses to the forecasts store / delivery") and hands the resulting bytes +
a metadata dict to `views-appwrite`'s `DatastoreManager.upload(file, filename,
metadata)`. `views-appwrite` hashes, deduplicates, and stores the bytes; it never
parses them. The flat-columnar choice is a `views-frames` decision; the upload is a
`views-appwrite` decision; the **saver that composes them is pipeline-core's**
(`AppwriteSaver` / `ViewsForecastsSaver`).

### 3.2 The read path — store → bytes → frame
faoapi (or any reader) calls `DatastoreManager.download(file_id, save_path,
use_cache=True)`; `views-appwrite` streams the bytes (cache-validated) and returns
them; the consumer deserializes via `views-frames`' `io` into a frame. Today faoapi
deserializes into a pandas DataFrame (`pd.read_parquet(BytesIO(...))`); with frames
it deserializes into a `PredictionFrame` instead. **From `views-appwrite`'s side
this is a no-op change** — it returned bytes before and returns bytes after.

### 3.3 The metadata handoff — `frame.metadata` → opaque store metadata
This is the only semantically interesting seam. A `views-frames` frame carries a
`metadata` dict (README §4.1, and the §13.5 provenance proposal: model, run_type,
timestamp, seed). `views-appwrite` stores an opaque `Dict[str, Any]` of metadata
**alongside** the bytes and makes it queryable via `get_latest(filters)` /
`search(filters)`. The natural, *consumer-mediated* handoff is:

```
frame.metadata  ──(consumer saver maps keys)──▶  DatastoreManager.upload(..., metadata=...)
```

Crucially, **neither leaf may collapse this seam**: `views-appwrite` must not learn
that a metadata key named `run_type` came from a frame (ADR-003: it stays generic),
and `views-frames` must not learn that its metadata ends up searchable in Appwrite
(it stays store-agnostic). The key mapping is the consumer's, and it is exactly the
join that the C-48 fix needs (§4).

---

## 4. The concrete things the two leaves jointly untangle

> Register IDs: `C-xx` unprefixed are **views-appwrite's** own register; cross-repo
> IDs are named with their repo.

| Pain | Where it lives | What the frames↔appwrite pairing does |
|---|---|---|
| **Scalable bytes crossing the store** (the #181/C-186 object-dtype blow-up, pipeline-core) | pipeline-core report/persist path; the forecast store | `views-frames` standardizes the dense **flat-columnar** on-disk format (§7) and *bans list-in-cell*; `views-appwrite` streams those dense bytes (it would just as happily store a bloated object-DataFrame parquet — it doesn't police shape). The scalable **format** is the frames win; the scalable **transport** is already appwrite's. They reinforce; neither alone is sufficient. |
| **C-48 — eval report renders the wrong run** (reporting) | reporting scrapes WandB `get_latest_run` | **Two ends of the cure.** `views-frames` §13.5 puts a stamped run/eval identity in `frame.metadata`; `views-appwrite` makes that identity a **searchable** store key (`get_latest`/`search` over metadata) so a reader selects *the* evaluation by filter, not "whatever the tracker surfaced last." Neither leaf resolves C-48 alone — the *consumer* must map `frame.metadata → upload(metadata=…)` and query by it. |
| **RAM never holds the whole array** | consumer read paths | `views-frames` `io/npz` supports `mmap` load (peak RAM = working set); `views-appwrite` `StorageManager` streams downloads to disk. A consumer can download-stream then mmap-load a frame and never materialize the full array — a complementarity, owned at neither leaf but enabled by both. |
| **Duplicated store clients drift** (views-appwrite's reason to exist) | pipeline-core + faoapi each carried a copy | Orthogonal to frames, but worth stating: `views-appwrite` de-duplicates the *transport*; `views-frames` de-duplicates the *contract*. Together they replace "every repo reimplements both how-to-shape-it and how-to-store-it." |

**The honest line:** `views-appwrite` *solves nothing about frames* and *frames
solve nothing about Appwrite* — by design. What the pairing buys is a clean two-leaf
factoring of the persist boundary: shape on one side, transport on the other,
bridged by a thin consumer saver. The one genuinely *joint* enabler is provenance
(C-48), and even there each leaf only provides a home; the cross-repo decision about
*what* the run identity is, and the consumer code that maps it across the seam,
remain outside both.

---

## 5. What stays in `views-appwrite` (explicitly NOT `views-frames`), and the mirror

Per `views-frames` §11 (which already names "adapters to … appwrite … → consumer
repos") and `views-appwrite`'s ADR-001/ADR-002, the division is symmetric:

**Stays in `views-appwrite` (the storage client):**
- Authentication, SDK-version `compat`, timeouts, the `AppwriteConfig` boundary.
- Bytes I/O: upload/download/dedupe-by-hash, bucket auto-provision, streaming.
- The metadata **store** (CRUD + search/pagination over an opaque `Dict[str, Any]`).
- The disk **cache** (TTL, staleness, mmap-friendly streaming to a path).

**Stays in `views-frames` (the data contract):**
- The frame types, the `SpatioTemporalIndex`, the serialization **formats**
  (`io/npz`, `io/arrow`) — i.e. how an array *becomes* bytes, never where they go.

**Stays in the consumer (the bridge — NOT either leaf):**
- The saver/loader that composes "serialize a frame" with "upload bytes" (and the
  inverse). pipeline-core's `AppwriteSaver` is precisely this — and it is also where
  views-appwrite's **C-06** (the catch-all that swallows upload exceptions) lives:
  that saver is the frame↔store bridge, and its graceful-degradation policy is a
  *consumer* decision, not a leaf one (views-appwrite ADR-008 says the package
  *raises*; the consumer may choose to degrade).
- The `frame.metadata → store metadata` key mapping.

If `views-appwrite` ever grows a `from_frame()` / `to_frame()` helper, or
`views-frames` ever grows an `to_appwrite()` adapter, **a boundary has been
crossed** — extract it back to the consumer. Each leaf importing the other is the
canonical anti-pattern here (the mirror of views-appwrite's ADR-002 "never import a
consumer" and views-frames §3 "never import `views_*`").

---

## 6. How `views-appwrite`'s existing design already fits frames

- **It is frame-ready *because* it is frame-ignorant.** The `DatastoreManager`
  contract is `upload(bytes, filename, Dict[str, Any])` / `download(...) -> bytes`.
  A serialized frame is bytes; a frame's provenance is a dict. Nothing in the
  storage contract needs to change to carry frames — the opacity that ADR-003
  mandates is exactly what makes it payload-agnostic.
- **Opaque metadata is the right shape for `frame.metadata`.** views-appwrite
  already refuses to enforce a metadata schema (ADR-003 / Decision D-3); a frame's
  metadata dict drops straight in, and the consumer owns which keys become
  searchable. The frames §13.5 provenance question and the appwrite "consumer owns
  metadata meaning" rule are the same principle seen from two leaves.
- **`get_latest` / `search` are the storage-side of provenance.** They already
  exist to select a stored object by metadata filter — the precise capability the
  C-48 fix needs once frames stamp a run identity. No new appwrite surface required.
- **`download → bytes` already matches "consumer deserializes."** views-appwrite's
  README already says a consumer wanting a DataFrame does `pd.read_parquet(BytesIO(
  result.data["file_bytes"]))` itself. Swap `pd.read_parquet` for
  `views_frames.io.arrow.load` and the same seam yields a frame. The boundary was
  drawn for frames before frames existed.

---

## 7. Migration implications for `views-appwrite` (essentially none)

`views-appwrite` does **none** of `views-frames` §10 and needs no migration of its
own to support frames. Concretely:

1. **No code change to adopt frames.** The byte/metadata contract is unchanged; a
   frame is just another payload. The migration work is entirely in the *consumers'*
   savers (pipeline-core, faoapi), where the serialize/deserialize call swaps from
   pandas to `views-frames.io`.
2. **No dependency added.** `views-appwrite` must **not** add `views-frames` to its
   `pyproject.toml`. The two leaves stay independent; only consumers list both.
3. **The one thing to confirm (not change):** that the consumer's flat-columnar
   bytes (`views-frames` `io/arrow`) round-trip through `upload`/`download`
   unmodified — which they will, because views-appwrite treats them as an opaque
   blob and dedupes by hash, not by content.
4. **Sequencing is independent.** views-appwrite's own Phase 1 (extract the client
   from pipeline-core/faoapi) and views-frames' Phase 1 (stand up the contract) do
   not block each other. They converge later, in the consumer savers, after both
   leaves exist.

---

## 8. What `views-appwrite` needs the contract to guarantee (asks / open questions)

These are the things this leaf would raise on the `views-frames` design, all about
the *seam*, never about the frame internals:

1. **Self-describing bytes.** A frame serialized by `io/arrow` / `io/npz` must
   round-trip from a single stored blob (or a documented small set of blobs)
   **without out-of-band schema.** views-appwrite stores opaque bytes; if loading a
   frame back requires information that wasn't in the uploaded payload, the consumer
   has to thread it through appwrite's metadata — so frames should state exactly
   what the consumer must persist as metadata vs. what is inside the bytes.
   (datafactory's perspective §8.2 raises the sibling concern: `feature_names` +
   `metadata` must serialize *with* the frame.)
2. **A single-blob (or few-blob) on-disk form for the store path.** views-appwrite's
   `upload` takes one file + one metadata dict. The native `io/npz` form is
   `values.npy` + `identifiers.npz` (+ sidecars) — multiple files. Confirm the
   **`io/arrow` flat-columnar** form is the one that crosses to the store (one
   parquet blob), with the native multi-file form reserved for local disk. The
   forecast-store path should be single-blob.
3. **A documented `frame.metadata` → searchable-key convention.** Not in the leaf
   (the mapping is the consumer's), but `views-frames` §13.5 should specify the
   provenance keys (`model`, `run_type`, `timestamp`, `data_version`, …) precisely
   enough that every consumer maps them to appwrite metadata *the same way* — else
   `get_latest`/`search` filters diverge per consumer and C-48 re-emerges store-side.
4. **Deterministic serialization.** views-appwrite dedupes by content hash; a frame
   that serializes non-deterministically (dict key order, float formatting) would
   defeat dedup and store redundant blobs. Confirm `io/arrow` writes are byte-stable
   for identical frames.
5. **Confirm the non-dependency is mutual and permanent.** `views-frames` §11
   already says appwrite adapters live in consumers; this perspective asks that the
   reverse be equally explicit somewhere — that `views-frames` will never grow an
   Appwrite-aware `io` backend. (The right place is a one-line scope note; it
   protects both leaves from the slow slide into mutual coupling.)

---

## 9. The two-leaves question (unique to this perspective)

Pipeline-core, reporting, and datafactory all have a *vertical* relationship to
`views-frames` (they depend up onto it, or donate a type to it). `views-appwrite`'s
relationship is *lateral*: **two independent leaves at the same depth.** That raises
a question the other perspectives don't.

**Why have two leaves instead of one "platform-core" leaf?** Because they have
**orthogonal reasons to change and orthogonal dependency closures.** `views-frames`
changes when the *data contract* changes (a new frame, a new identifier, an
alignment law) and depends only on `numpy`. `views-appwrite` changes when the
*storage substrate* changes (an Appwrite SDK bump, a new bucket policy, a cache
fix) and depends only on the Appwrite SDK. Merging them would (a) force a numpy-only
data contract to carry the Appwrite SDK (CRP violation — a model that wants a
`PredictionFrame` would transitively install the Appwrite client), and (b) couple
two release cadences that have nothing to do with each other. Two narrow leaves,
each maximally stable in its own axis, is the correct factoring (SDP + CRP).

**Why is this the safe kind of lateral pair?** Because the non-dependency is
*enforceable by construction*: neither leaf has any reason to name the other, and
both governance sets already forbid it (views-appwrite ADR-002 forbids importing a
consumer or sibling; views-frames §3/§11 forbid `views_*` imports and push store
adapters to consumers). The only place they can be coupled is a consumer saver —
which is exactly where coupling *belongs*, because the consumer is the only actor
that legitimately knows both "this is a frame" and "it goes to Appwrite."

**The risk to watch:** convenience pressure to "just add a `DatastoreManager.upload_frame()`
helper" or a `views_frames.io.appwrite` backend. Either would collapse the lateral
independence into a diamond and re-import the exact drift these leaves exist to
kill. The litmus test mirrors both repos' existing ones: *would a non-VIEWS user of
the Appwrite client want frames? would a non-Appwrite user of frames want the
Appwrite SDK?* Both answers are no; the helper belongs in the consumer.

---

## 10. Cross-references

- `views-frames` README: §2 (DAG position — both are leaves), §3 (hard constraints —
  numpy-only, no `views_*`), §4.1 (`metadata` field), §7 (serialization — the
  flat-columnar form that "crosses to the forecasts store"), §11 (scope — "adapters
  to … appwrite → consumer repos," the boundary this document is the appwrite side
  of), §13.5 (provenance — the joint C-48 enabler).
- `views-frames` perspectives: `from_views-pipeline-core_perspective.md` (owns the
  `AppwriteSaver` that bridges the two leaves; §3.4 `MetricFrame` producer),
  `from_views-reporting_perspective.md` (the C-48 consumer of record; §8.1
  provenance ask).
- `views-appwrite` governance: ADR-001 (ontology — generic client, domain
  non-entities), ADR-002 (topology — leaf, depend down, never import a
  sibling/consumer), ADR-003 (consumer owns metadata meaning — opaque
  `Dict[str, Any]`), ADR-008 (fail loud; consumer owns degradation), ADR-009
  (`AppwriteConfig` boundary). Risk register: **C-06** (the pipeline-core
  `AppwriteSaver` catch-all — the frame↔store bridge), C-21 (integration-test
  isolation — relevant when a test round-trips a frame through a real bucket).
- `views-appwrite` README: the `DatastoreManager` facade (`upload`/`download`/
  `get_latest`/`search`/`delete`/`list_all`), the "download returns bytes; consumer
  deserializes" boundary that already fits frames.
