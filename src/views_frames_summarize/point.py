"""Point estimates over the sample axis (ADR-017) — return a `(N, …, 1)` frame.

`map_estimate` is the maximum-a-posteriori estimate as faoapi/reporting compute it:
the empirical density peak (histogram), with a zero-mass→0 rule for the
zero-inflated conflict distributions. The mechanism reduces the **trailing** axis;
the leaf guarantees that axis is the sample axis (ADR-012).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import AnyFrame, rebuild


def map_estimate(
    frame: AnyFrame, *, bins: int = 100, zero_mass_threshold: float = 0.3
) -> AnyFrame:
    """Per-row MAP estimate over the sample axis → a `(N, …, 1)` frame.

    For each row: if a fraction ``>= zero_mass_threshold`` of the samples is ~0 the
    MAP is ``0.0``; otherwise it is the centre of the densest histogram bin.
    """
    mapped = np.apply_along_axis(
        _map_1d, -1, frame.values, bins, zero_mass_threshold
    )
    reduced = np.asarray(mapped, dtype=np.float32)[..., np.newaxis]
    return rebuild(frame, reduced)


def _map_1d(
    samples: NDArray[np.float32], bins: int, zero_mass_threshold: float
) -> float:
    mass_at_zero = float(np.mean(np.isclose(samples, 0.0, atol=1e-8)))
    if mass_at_zero >= zero_mass_threshold:
        return 0.0
    hist, edges = np.histogram(samples, bins=bins, density=True)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return float(centers[int(np.argmax(hist))])
