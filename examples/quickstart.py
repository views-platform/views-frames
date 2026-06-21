"""views-frames quickstart — build, summarize, serialize, and contract-check a frame.

Run it with::

    uv run examples/quickstart.py

Everything here is numpy-only: the leaf (`views_frames`) is the immutable
array+identifier contract; the sibling (`views_frames_summarize`) reduces the
sample axis. No pandas, no domain data.
"""

from __future__ import annotations

import tempfile

import numpy as np

from views_frames import (
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
)
from views_frames.conformance import assert_frame_contract
from views_frames_summarize import collapse, hdi, map_estimate

# 1. An index: integer (time, unit) identifiers at one spatial level (here pgm).
index = SpatioTemporalIndex(
    time=np.array([1, 1, 2], dtype=np.int64),
    unit=np.array([10, 11, 10], dtype=np.int32),
    level=SpatialLevel.PGM,
)

# 2. A PredictionFrame: float32 values shaped (N rows, S posterior samples).
rng = np.random.default_rng(0)
pf = PredictionFrame(rng.gamma(2.0, 1.0, size=(3, 500)).astype(np.float32), index)
print(f"frame: {pf.n_rows} rows x {pf.sample_count} samples, is_sample={pf.is_sample}")

# 3. Summarize the sample axis (the sibling package; the statistic is injected).
mean = collapse(pf, np.mean)  # (N, S) -> (N, 1) frame
mode = map_estimate(pf)  # per-row MAP -> (N, 1) frame
interval = hdi(pf, mass=0.9)  # per-row 90% HDI -> (N, 2) numpy array (index-aligned)
print(f"mean[0]={mean.values[0, 0]:.3f}  MAP[0]={mode.values[0, 0]:.3f}")
print(f"90% HDI[0]=[{interval[0, 0]:.3f}, {interval[0, 1]:.3f}]")

# 4. Serialize and reload (npz here; `.save(dir)` also has an [arrow] parquet path).
with tempfile.TemporaryDirectory() as directory:
    pf.save(directory)
    reloaded = PredictionFrame.load(directory)
    assert np.array_equal(reloaded.values, pf.values)
    print("save/load round-trip: ok")

# 5. The published contract check a consumer runs in its own CI against its frames.
assert_frame_contract(pf)
print("assert_frame_contract: ok")
