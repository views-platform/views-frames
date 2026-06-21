"""Cross-level alignment + conservation-correct aggregation (the subtle surface).

Run it with::

    uv run examples/cross_level.py

The cm↔pgm join is the operation most likely to be misused, so here it is end to
end: build a **consumer-injected** ``(time, unit) -> country`` mapping (the leaf
never embeds geography), remap a PRIO-GRID `PredictionFrame` to country level, and
sum the per-cell posterior **distributions** — preserving the sample index so the
aggregated uncertainty is correct: ``HDI(sum) != sum(HDI)``.
"""

from __future__ import annotations

import numpy as np

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_summarize import aggregate_distributions, hdi

# Four PRIO-GRID cells over two months. The mapping is **time-varying**: cell 11's
# country changes between month 1 and month 2 (a border change) — exactly why the
# key is (time, unit), not unit alone.
time = np.array([1, 1, 2, 2], dtype=np.int64)
unit = np.array([10, 11, 10, 11], dtype=np.int32)
index = SpatioTemporalIndex(time, unit, SpatialLevel.PGM)

rng = np.random.default_rng(0)
pf = PredictionFrame(rng.gamma(2.0, 1.0, size=(4, 500)).astype(np.float32), index)

# Consumer-injected mapping, keyed by (time, unit). Cell 11 -> country 100 in month
# 1, but -> country 200 in month 2. (Pass it as a dict, or as columnar arrays via
# `cross_level_align_arrays` / `aggregate_distributions_arrays` at grid scale.)
mapping = {
    (1, 10): 100,
    (1, 11): 100,  # month 1: cells 10 & 11 both in country 100
    (2, 10): 100,
    (2, 11): 200,  # month 2: cell 11 moved to country 200
}

cm_index = pf.index.cross_level_align(mapping, SpatialLevel.CM)
print("pgm units:", pf.index.unit.tolist(), "->  cm units:", cm_index.unit.tolist())

# Aggregate the sample distributions up to country level (joint sampling).
agg = aggregate_distributions(pf, mapping, SpatialLevel.CM)
print(f"aggregated rows: {agg.n_rows} (time, country) groups")
for t, u in zip(agg.index.time, agg.index.unit, strict=True):
    print(f"  (month={t}, country={u})")

# The conservation point: the HDI of the summed distribution is NOT the sum of the
# per-cell HDI bounds — uncertainty does not add linearly.
month1 = pf.select(np.array([0, 1], dtype=np.intp))  # the two cells in month 1
hdi_of_sum = hdi(agg.select(np.array([0], dtype=np.intp)), 0.9)[0]
sum_of_cell_hdi = hdi(month1, 0.9).sum(axis=0)
print(f"\nHDI(sum)      = [{hdi_of_sum[0]:.2f}, {hdi_of_sum[1]:.2f}]")
print(f"sum(cell HDI) = [{sum_of_cell_hdi[0]:.2f}, {sum_of_cell_hdi[1]:.2f}]")
print("HDI(sum) != sum(HDI) — aggregate distributions, never interval bounds.")
