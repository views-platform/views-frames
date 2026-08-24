# ADR-029: The frames are numpy arrays plus explicit identifier arrays — not xarray, not a DataFrame, not a tensor

**Status:** Accepted (a live decision — see *What would change the answer*)
**Date:** 2026-08-24
**Deciders:** VIEWS platform maintainers
**Consulted:** ADR-002's dependency rules; the 2026-06 leaf and summarize postmortems; ADR-028's measured evidence on structural typing; live PyPI metadata for every candidate named
**Informed:** every repository that pins `views-frames`

---

## In short

A frame is a numpy array with a small object holding two integer identifier arrays beside it.
Nothing else. The only runtime dependency this package has is `numpy>=1.26,<3`.

**numpy was chosen because it was free.** Every repository on this platform already depended on
it, so adding the contract added no transitive dependency at all. That is the whole argument, and
everything below is the working that supports it.

**The obvious question is why this is not xarray**, which does labeled dimensions and
coordinate alignment properly, is maintained by people who think about it full time, and
would have replaced most of `SpatioTemporalIndex` with `.sel()`. This ADR answers that, and
the nine other alternatives a reasonable person would raise.

It was never written down before. Roughly 9,400 lines of governance prose in this repository
and the word "xarray" appeared nowhere in it until this document — so a newcomer asking the
first question anyone asks found no answer, which is how a settled decision gets relitigated
by accident.

**Nothing changes as a result of this ADR.** It records a decision already made, measures what
each alternative would have cost, and names the evidence that would reopen it.

**It has a visible expiry.** *The scaling wall, with numbers* below sizes the data this platform
expects to hold — hundreds of gigabytes for a single global feature set — and concludes that
per-month sharding plus `numpy.memmap` carries the current access pattern further than the raw
totals suggest, but not past densification or storage volume. This decision is live, not closed,
and `dask[array]` is deferred on design grounds rather than on cost: it measures at three
megabytes over numpy.

---

## What the leaf actually has to be

Every alternative below is judged against one constraint, so it is worth stating first.

`views-frames` sits at the **root of the platform dependency DAG**. Every other repository
depends toward it and nothing depends away from it. That is not an accident of layout, it is
ADR-002's decision, and it has a consequence most container choices ignore:

> **Every dependency this package takes, every consumer takes.**

### numpy was chosen because it was free

This is the primary reason, and it is worth stating before any comparison of features.

**Every repository on this platform already depends on numpy.** Adding `views-frames` to a repo
therefore adds no new transitive dependency at all — the array library was already installed,
already resolved, already pinned. The contract arrived at zero dependency cost.

That property is what the whole repository separation exists to protect. The model repos are
deliberately allowed to hold *wildly* different libraries — that is the point of separating
them, and it is why they need not share an environment; orchestration calls across repo
boundaries rather than importing across them. The price of that freedom is that anything
imported by *most* repos must be nearly free, because it is the one place where their dependency
sets are forced to agree.

**So the question for every alternative is not "is it a better array container".** Several are.
The question is what it costs to make every repository on the platform carry it — in bytes, and
more importantly in *version coupling*.

### The two costs are different, and the second is the one that bites

- **Weight** is what a repo downloads and ships. It matters when it is large in absolute terms.
- **Coupling** is whether the dependency has a version that some repo *already pins for its own
  reasons*. A package that many repos already use at their own chosen version is expensive to
  put at the DAG root even when it is small, because from then on every repo's pin must satisfy
  the leaf's floor too.

pandas is the clearest case of the second: it is small enough, and it is exactly the kind of
library a model repo already pins. torch is the rare case where both costs apply at once.

`ADR-002` states the rule directly:

> The numpy-only floor (CRP) means a model that wants a `PredictionFrame` does not
> transitively install the pandas/reporting world.

The consumers are not all research code. **views-faoapi is an HTTP API server.** Whatever this
package imports, that server installs and ships. So the question for each alternative is not
"is it a better array container" — several are — but "is it a better array container *by
enough* to justify putting itself, its transitive dependencies, its release cadence and its
pin surface into every repository on the platform, including the ones that only want to
describe a forecast over HTTP".

Two further constraints, both earned rather than assumed:

- **The axis meaning must not be able to drift.** ADR-012 fixes the trailing axis as the sample
  axis. The platform's worst incidents traced to code that inferred which axis was time or
  space and then drifted silently when the data changed shape. A container where an axis is
  identified by a string that anyone can rename is a container where that can happen again.
- **Failure must be loud and at construction.** ADR-008. A container that accepts and coerces
  by default is working against this.

---

## Decision

The three frames hold a `float32` numpy array and a `SpatioTemporalIndex`, which holds two
`int64` identifier arrays and a `SpatialLevel`. Alignment is hand-written numpy
(`searchsorted` over a packed row view). The only runtime dependency is numpy.

`pyarrow` is permitted, as an **optional extra**, **only** under `io/` — it is a codec, never
the frame type. That boundary is enforced by `tests/test_import_enforcement.py` and by the
`import-linter` contracts in `pyproject.toml`.

---

## What each alternative actually costs

Measured on 2026-08-24 by resolving each candidate's full transitive closure with
`pip install --dry-run --report` on Python 3.11 and summing the manylinux wheel sizes from PyPI.
Download size, not installed size; the ranking is what matters, not the absolute figures.

| Candidate | Packages | Download | Over numpy | Drags in a commonly-pinned library? |
|---|---:|---:|---:|---|
| **numpy** — the baseline, already present in every repo | 1 | 18.6 MB | — | — |
| `dask[array]` | 12 | 21.6 MB | **+3.0 MB** | no |
| `awkward` | 8 | 21.8 MB | +3.2 MB | no |
| `zarr` | 5 | 27.7 MB | +9.1 MB | no |
| `xarray` | 8 | 35.1 MB | +16.5 MB | **yes — pandas** |
| `pyarrow` | 1 | 53.1 MB | +34.5 MB | no |
| `polars` | 2 | 59.4 MB | +40.8 MB | no |
| `jax` | 6 | 151.8 MB | +133.2 MB | **yes — scipy** |
| `cupy-cuda12x` | 3 | 166.9 MB | +148.3 MB | a CUDA runtime |
| **`torch`** | **29** | **3,022.8 MB** | **+3,004 MB (162×)** | **CUDA stack, unconditional on Linux** |

Three things this table settles that argument alone did not:

- **`dask[array]` is essentially free** — twelve small pure-Python packages, three megabytes over
  numpy, cheaper than zarr and half the weight of xarray. Any framing that treats adopting dask
  as an expensive step is wrong on the evidence. Its objections are about design, not cost.
- **xarray is not heavy.** At 35 MB the weight argument against it is weak. The real cost is the
  pandas coupling in the last column.
- **torch is in a different category entirely** — 162× numpy, and the only entry whose transitive
  closure is dominated by things unrelated to arrays (`nvidia-cublas` 543 MB, `torch` 527 MB,
  `nvidia-cudnn` 445 MB).

---

## Alternatives considered

### 1. xarray — the real contender

`xr.DataArray` with dims `(row, sample)` and coordinates for `time` and `unit` is very close to
what this package hand-rolls. `.sel()` replaces `searchsorted`. Automatic coordinate alignment
replaces `reindex`. `xr.align` replaces the same-level join. The cross-level remap would still
be consumer-injected, because that is a domain rule rather than a container feature. Broadcast
semantics, `groupby`, `resample`, and unit-aware slicing all arrive free, and several of them
are things this package deliberately does not offer.

**It loses on the dependency, and only on the dependency — but not for the reason weight would
suggest.** At 35 MB total, xarray is not a heavy install; an earlier draft of this ADR leaned on
size and that was the weaker argument.

The real cost is **coupling**. xarray declares `pandas>=2.2` as a hard requirement (checked
against xarray 2026.7.0 on 2026-08-24). pandas is precisely the kind of library a model repo
*already pins for its own reasons* — so putting a pandas floor at the DAG root means every
repository's pandas pin must from then on also satisfy the leaf's. That is the dependency
alignment work the repo separation exists to avoid, reintroduced at the one point in the graph
that touches everything.

It is also the outcome `ADR-002` names as the reason for the numpy floor, and the thing
views-faoapi #242 is still working to undo on the consumer side. A leaf that re-imports what its
consumers are removing is not a leaf.

**The secondary loss is that xarray's flexibility is this package's liability.** In xarray a
dimension is a string. Nothing prevents `sample` becoming `draw`, nothing prevents it moving
position, nothing prevents a frame arriving with the dimension absent. ADR-012 exists because
that class of drift already cost this platform real incidents. Enforcing the sample-axis
invariant on top of xarray would mean validating at every boundary — which is the work this
package does anyway, minus the dependency.

**What is genuinely lost by declining it** — stated plainly, because this is the alternative
that costs the most to refuse:

- ~~lazy and out-of-core evaluation via dask~~ — **struck. This was wrong in the first draft and
  the correction matters.** Out-of-core is not xarray's to give: `dask.array` provides it with a
  numpy-compatible API and no pandas (see §9). Declining xarray costs less than this ADR first
  claimed; the out-of-core question is a separate, cheaper decision that the draft never posed;
- zarr and netCDF, which would make `io/` mostly disappear;
- `groupby`/`resample`/interpolation, all currently absent or hand-rolled;
- roughly 3,700 lines of source that someone else would maintain.

This is the alternative most likely to come back, and *What would change the answer* below says
under exactly what evidence.

### 2. No in-memory type at all — the file format is the contract

Publish a schema (parquet, zarr or netCDF plus a written layout spec) and let every consumer
use whatever container it likes. ADR-013's wire contract is already half of this.

It is the most intellectually honest alternative, because a *data contract* arguably should be
about bytes rather than Python objects, and it is the only option here that serves a non-Python
consumer.

**It loses because the contract stops being executable.** ADR-016's mechanism is that consumers
run *the same* `assert_*` functions in their own CI, so "all consumers agree" is checked rather
than asserted. With format-as-contract every consumer writes its own loader and its own
validation, and the drift this repository spent two audits closing reappears in six places at
once instead of one. It also gives up fail-loud-at-construction entirely: a malformed frame
becomes a malformed *file*, discovered whenever someone happens to look.

The strongest evidence against it is local. 2.0.0 exists because a frame could be built with a
non-index and the published checker certified it. That was caught because there *is* a shared
constructor and a shared checker to attack. Under format-as-contract there would have been six
independent versions of that bug and no single place to fix it.

### 3. torch.Tensor

Superficially attractive: the model repositories already live in torch, so a torch-native frame
would remove a conversion at the boundary that matters most.

**It loses twice, and the second reason is the interesting one.**

First, weight — and the measurement is worse than the intuition. torch 2.13.0 declares the CUDA
stack as **unconditional** hard dependencies on Linux, not as an optional extra:
`cuda-toolkit[cublas,cudart,cufft,cufile,cupti,curand,cusolver,cusparse,nvjitlink,nvrtc,nvtx]`,
`nvidia-cudnn-cu13`, `nvidia-cusparselt-cu13`, `nvidia-nccl-cu13`, `nvidia-nvshmem-cu13` and
`triton` (checked 2026-08-24). Putting that at the DAG root means views-faoapi — an API server
whose job is to serialize a forecast over HTTP — pulls the CUDA toolchain to do it, on every
deploy, with no way to opt out short of a fork. This is the xarray argument about two orders of
magnitude worse.

Second, and more decisive: **this platform already migrated away from torch in exactly this
domain.** `views_frames_reconcile` exists to be a *numpy* reconciler with bit-parity against
views-reporting's *torch* oracle. The parity test's own docstring records that it "needs neither
torch" at runtime, because the oracle's output is captured as a generated fixture. Torch is not
a runtime dependency, not a test dependency, and not an optional extra — it is a historical
reference implementation that was deliberately replaced. Reintroducing it as the frame type
would reverse a completed migration.

There is also no technical pull. The leaf does no gradient work: `views_frames_summarize` is
sample-axis reduction, not a differentiable path, by charter (ADR-017). A tensor buys autograd
and device placement, and this package needs neither.

### 4. pyarrow `Table` as the frame type

Nearly free, since `io/arrow` already exists. Zero-copy, language-neutral, excellent IO, and it
would collapse the in-memory type and the wire format into one thing.

**It loses on memory model.** Arrow is columnar; a posterior is a dense `(N, S)` float32 block
and a feature frame is `(N, F, S)`. Every estimator in `views_frames_summarize` sorts, slices
and reduces along the trailing axis — operations that are natural on a strided buffer and
awkward on a column store. The tower estimators in particular work in row blocks to bound peak
memory (C-22); expressing that over Arrow columns would be a fight on every function.

Note this was already decided implicitly: `pyarrow` is an optional extra restricted to `io/` by
`pyproject.toml` and enforced by two independent mechanisms. This ADR makes that explicit rather
than leaving it inferable from an import contract.

### 5. Protocols only — no concrete frame type

Ship `Frame`, `Sampled`, `SpatioTemporalIndexed` and `Persistable` as `Protocol`s and let each
consumer bring its own container. Maximum flexibility, zero opinion about storage, and the
protocols already exist in `protocols.py`.

**This one is closed by measurement rather than argument.** ADR-028 records what happened when
the contract relied on structural typing: the frame constructors accepted anything exposing
`n_rows`, so a *frame* passed as an *index* for eleven releases, and the published conformance
suite certified the result. `runtime_checkable` protocols check member **presence**, never
member type or semantics — which is exactly the hole.

A protocols-only design makes that failure mode the whole design rather than a bug in it. The
protocols remain valuable as the surface consumers *type against* (ADR-009); they are not
sufficient as the surface consumers *construct*.

### 6. pandas DataFrame with a MultiIndex

The historical baseline, and the thing the platform actively left.

A `(time, unit)` MultiIndex over a wide frame of `S` sample columns is the natural encoding, and
it is what several consumers used before the leaf existed. It loses on three counts, all with
receipts in this repository:

- **The list-in-cell encoding.** Storing a posterior as a Python list per cell is the obvious
  pandas move and it is a memory catastrophe — register C-40/C-66 record the blow-up, and
  README §7 bans object dtype outright as a result.
- **Dependency weight**, the same CRP argument as xarray, with pandas being the specific package
  named in ADR-002.
- **Index semantics that are too permissive.** A pandas index silently accepts duplicates,
  reorders on join, and coerces dtypes — every one of which is a behaviour this package has an
  explicit fail-loud rule against (C-21 on row uniqueness, ADR-008 on coercion).

### 7. polars

Arrow-backed, fast, and notably *without* pandas' index concept — which removes one of the three
objections above. Identifier columns would carry `time` and `unit` explicitly, which is closer
to this package's philosophy than pandas is.

It loses for the same reason pyarrow does — columnar memory against a dense sample axis.

**The dependency argument does not apply here, and saying so matters.** An earlier draft of this
ADR grouped polars with pandas and xarray on weight; that was wrong. polars 1.44.0 declares one
hard dependency, its own compiled runtime — no pandas, no numpy requirement of its own. It is a
genuinely light install. The case against it is the memory model alone, and it is the closest
any DataFrame library comes to being viable here.

### 8. awkward-array

The ragged-data library. Dismissed in a sentence: it would make the variable-length per-cell
encoding *efficient*, and this package bans that encoding on purpose. The data is rectangular by
construction — a dense grid of cells by a fixed sample count — and a container optimised for
raggedness would legitimize the shape C-40 exists to prevent.

---

### 9. The numpy-API-compatible backends — Dask Array, JAX, CuPy

A class the first draft of this ADR missed entirely, and the omission was worth catching. The
eight alternatives above all propose a *different container with a different API*. These three
propose **the same API with a different backend**: `dask.array`, `jax.numpy` and `cupy` are each
close enough to numpy that most of this package would port with modest edits. That is a
materially different question, and it deserved asking.

**One filter removes most of the class before any design argument.** This package declares
`numpy>=1.26,<3` and runs a dedicated `floor` CI job at numpy 1.26.4, because consumers pin
conservatively and the floor is the boundary they actually pin to (registers C-19, C-24).
Measured on 2026-08-24:

| Candidate | numpy requirement | Against the `>=1.26` floor |
|---|---|---|
| `zarr` 3.3.0 | `numpy>=2` | forces every consumer to numpy 2 |
| `jax` 0.11.1 | `numpy>=2.1`, plus `scipy` | forces every consumer to numpy 2 |
| `cupy-cuda12x` 14.2.0 | `numpy<2.6,>=2.0` | forces every consumer to numpy 2 |
| `dask` 2026.7.1 | none in core | **compatible** |

Adopting any of the first three would move the floor for the whole platform as a side effect of
a container choice. That is not automatically disqualifying — the floor can be raised
deliberately — but it converts "swap the array backend" into a coordinated cross-repo bump,
which is the cost this package exists to avoid.

**Dask Array** is the one that survives the filter, and it is the strongest missed alternative
by a distance. `dask` 2026.7.1's hard dependencies are `click`, `cloudpickle`, `fsspec`,
`packaging`, `partd`, `pyyaml`, `toolz` and `importlib_metadata` — all pure-Python, and **no
pandas**. Measured: `dask[array]` resolves to twelve packages totalling **21.6 MB, three
megabytes over numpy** — cheaper than zarr, half the weight of xarray, and nothing in the
closure is a library another repo is likely to be pinning.

**On the platform's own cost test, dask is nearly as free as numpy was.** It answers C-71 (the
dense-grid allocation) and C-73 (read-all-to-RAM) directly, which is exactly what this ADR first
mis-attributed to xarray. Every objection to it below is about **design**, not cost — and that
distinction should be kept sharp, because a cheap dependency deferred on design grounds can be
revisited by changing the design, whereas an expensive one cannot be revisited at all.

It loses **as the frame type** for a reason that is about this package's philosophy rather than
about dask: **laziness is incompatible with fail-loud-at-construction.** ADR-008 requires that a
frame is never returned half-valid — `validate_values` runs in `__init__`, before the object is
usable. On a lazy array that check either triggers computation, defeating the laziness that was
the whole point, or defers, defeating ADR-008. `frame.values` would stop being a numpy array,
breaking every consumer's expectation and the `assert_frame_envelope` contract with it. And
chunk boundaries would interact with the row-blocking discipline the tower estimators use to
bound peak memory (C-22) in ways that need re-derivation rather than porting.

**Dask belongs in `io/`, not in the frame** — and that is now the sharpest form of this ADR's
main revisit trigger, sharper than the xarray version the first draft recorded, precisely
because it costs no pandas.

**JAX** deserves one honest paragraph beyond the floor objection, because it would have given
this package something it wanted and had to build. **JAX arrays are immutable natively.** The
entire C-66 saga — write-protection recorded as a deferred MAJOR-rider on 2026-06-28, carried
unshipped through eleven releases, finally landed in 2.0.0, and then only after discovering that
the one-line `setflags` fix ADR-025 recorded would have made the *caller's* array read-only —
would not have existed. Immutability would have been a property of the container rather than an
invariant this package enforces by hand.

That is a real loss and it is worth naming. It does not outweigh forcing numpy 2 and scipy on
every consumer for a package that needs neither autograd nor XLA (ADR-017 puts estimation
outside the leaf's charter, and none of it is differentiable), but the trade should be recorded
rather than glossed.

**CuPy** loses on the same grounds as torch, with one addition. The DAG-root argument applies —
a GPU array library at the root means views-faoapi needs a CUDA runtime to serialize a forecast
— though cupy's *declared* footprint is far lighter than torch's. The addition is capacity: GPU
memory is scarcer than host RAM, and C-71's motivating case is a full-pgm dense grid (~259k
cells × months × samples) that does not fit comfortably in host memory, let alone device memory.
The leaf's work is alignment and sample-axis reduction, not the dense linear algebra a GPU
exists for.

### 10. zarr as the storage layer (not as the contract)

Distinct from option 2, where the *format is* the contract. Here the frames stay numpy and
`io/` gains a chunked, compressed, partially-readable format alongside `npz` and `arrow`.

This is a complement rather than a competitor, and it is the natural companion to `dask.array`
above — chunked storage feeding a chunked reader. It is not adopted today only because C-73's
trigger has not fired: nothing has yet reported an OOM despite per-month sharding, and `io/`
already has two formats to maintain.

The floor objection applies to zarr 3 (`numpy>=2`), so if this arrives it either waits for the
platform's numpy floor to move on its own schedule, or pins `zarr<3`.

---

## The scaling wall, with numbers

The decision above is correct for the data this platform holds today. It is worth writing down
what the data is expected to become, because the honest reason this ADR is *live* rather than
closed is that the current answer has a visible expiry.

Take a plausible near-future shape — ten features, 128 samples each, a global 0.5 degree grid
(720 x 360 = 259,200 cells), five hundred months:

```
10 features x 128 samples x 259,200 cells x 500 months = 165,888,000,000 cells
                                       x 4 bytes (float32) =  663.6 GB
```

Excluding ocean cells helps but does not rescue it. If roughly 80% of cells are water and are
dropped, **20% remains**:

| | cells | float32 |
|---|---:|---:|
| Full 0.5 degree grid | 165.9 billion | **663.6 GB** |
| Land only (20% of cells retained) | 33.2 billion | **132.7 GB** |

Neither fits in memory, and ten features at 128 samples is nowhere near a ceiling.

**But the per-shard figure is the one that explains why nothing has broken yet**, and it is the
number to watch:

| One month, all features and samples | float32 |
|---|---:|
| 10 features x 128 samples, full grid | **1.33 GB** |
| 10 features x 128 samples, land only | 265 MB |
| 50 features x 512 samples, full grid | **26.5 GB** |

Per-month sharding is load-bearing — it is what keeps a working set in the low gigabytes, and it
is exactly the precondition register **C-73** names ("an OOM *despite* per-month sharding").
**The wall arrives through feature count and sample count, not through months.** Adding months
adds shards; adding features or samples multiplies every shard.

### Is `numpy.memmap` enough?

Partly, and for longer than the raw totals suggest — but not for the thing likely to break first.

**Where it works.** A frame is `(N, S)` row-major with samples contiguous, so a per-row
sample-axis reduction reads sequentially. That is the dominant access pattern in
`views_frames_summarize`, and the tower estimators already work in row blocks to bound peak
memory (C-22) — precisely the pattern memmap rewards. Reduction over a frame far larger than RAM
streams acceptably today.

**Where it does not.**

1. **Densification writes, it does not read.** `reindex_fill` allocates the full dense buffer up
   front (register **C-71**). memmap does not help build a dense grid; it helps read one.
2. **No compression.** 663 GB stored raw, against what a chunked compressed format would hold.
   On present trends this is the binding constraint *before* RAM is — a storage-volume problem
   rather than a memory problem.
3. **No chunked parallelism.** memmap gives lazy paging, not a scheduler, and not partial reads
   of a compressed chunk.

So the expected order of failure is **storage volume first, densification second, reduction
last** — which matters, because the first fix needed is then a chunked compressed format in
`io/` (zarr), not a new frame type. That is additive, behind the existing `io/` boundary, and it
does not touch the public surface.

## What would change the answer

This is a live decision. Each trigger names evidence, not opinion, and none of them is met today.

| If this happens | Then re-cost | Scope |
|---|---|---|
| **A real OOM at grid scale** — register **C-71** (a full-pgm `cartesian` target, ~259k cells × months, fed to `reindex_fill` on a sampled frame) or **C-73** (an OOM *despite* per-month sharding) | **`dask.array` inside `io/`**, with `zarr` as its storage format | Additive. The frame type does not change; the storage layer gains a lazy path. Prefer dask over xarray here: it answers the same need and requires no pandas (§9). `io/` is the designated place for evolving formats (ADR-002). |
| **A non-Python consumer** appears on the contract | **format-as-contract** (option 2) | Would supersede this ADR. The executable-conformance argument only holds while every consumer can run Python. |
| **The leaf is required on an autograd path** | **torch** | Would first require amending ADR-017, which puts estimation outside the leaf's charter. Very unlikely by construction. |
| **The wire format becomes the dominant access path** — consumers reading parquet directly more often than they construct frames | **pyarrow as the frame type** | Would supersede this ADR and probably ADR-013 with it. |

**The dask trigger deserves a caveat the others do not.** Every alternative above is deferred on
some mix of cost and design. `dask[array]` is deferred on **design alone** — it costs three
megabytes. That makes it the one entry here whose deferral could be undone by changing this
package's mind rather than by waiting for the world to change, and the scaling section above
suggests the world will not wait long.

**No trigger is recorded for pandas, polars, protocols-only or awkward-array.** Those lose on
grounds that do not change with evidence: a dependency the DAG root cannot take, a memory model
that fights the sample axis, a typing discipline ADR-028 measured as insufficient, and an
encoding this package bans.

**The bar is deliberately high**, consistent with `GOVERNANCE.md`'s closing note that a package
needing frequent MAJOR bumps is not abstract enough. Changing the frame's container type would
be a MAJOR affecting every consumer simultaneously — a far larger event than 2.0.0, which only
narrowed what construction accepts.

---

## Consequences

### Positive

- The runtime dependency surface is one line: `numpy>=1.26,<3`. A consumer that wants a
  `PredictionFrame` installs numpy and nothing else.
- The sample axis cannot be renamed or moved, because it is a position rather than a label.
- Construction validates and fails loud, because there is one constructor to validate in.
- The conformance suite is executable and shared, so "all consumers agree" is checked.

### Negative — accepted deliberately

- **Alignment is hand-written.** `searchsorted` over a packed row view, plus the cross-level
  remap, is code this package maintains and xarray would have provided.
- **No out-of-core path.** C-71 and C-73 are open for this reason. Both would be closed by
  `dask.array` — which, unlike xarray, costs no pandas. This is the cheapest capability this
  ADR declines, and the first draft mislabelled it as xarray's.
- **No `groupby`, `resample` or interpolation.** Consumers do this themselves or go without.
- **numpy version skew is this package's problem.** The `floor` CI job exists because numpy
  1.26.4 and 2.x differ in generic stubs *and* in ~1-ulp histogram binning (registers C-19 and
  C-24). A higher-level container would have absorbed that.
- **Roughly 3,700 lines of source and 9,400 of governance are maintained here** that a
  third-party container would have carried.

These are real costs and they are worth naming rather than minimising. The judgement is that a
contract at the root of a dependency DAG is the one place where owning the code is cheaper than
owning the dependency.

---

## References

- **ADR-002** — the dependency rules and the CRP/SDP argument this ADR applies to a container
  choice; its "numpy-only floor" line is the direct ancestor of this decision.
- **ADR-008** — fail loud at construction, which permissive containers work against.
- **ADR-009** — protocols are the surface consumers type against.
- **ADR-012** — the trailing sample axis, the invariant a label-based container cannot hold.
- **ADR-013** — the wire contract, which is format-as-contract for the serialized form.
- **ADR-016** — executable conformance, the mechanism format-as-contract would give up.
- **ADR-017** — estimation is a sibling package and is not differentiable, which removes torch's
  technical pull.
- **ADR-028** — the measured evidence that structural typing alone is insufficient.
- Registers **C-19**/**C-24** (numpy version skew), **C-21** (row uniqueness), **C-22** (row
  blocking), **C-40**/**C-66** (the list-in-cell blow-up), **C-71**/**C-73** (the memory-wall
  triggers above).
- `pyproject.toml` — `dependencies = ["numpy>=1.26,<3"]`, and the `arrow` optional extra.
