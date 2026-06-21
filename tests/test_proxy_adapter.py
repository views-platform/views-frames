"""I9: an in-repo proxy for the real consumer contract test (register F15).

A datafactory-style adapter produces gridded tensors shaped ``[T, H, W, C]``
(time, grid-height, grid-width, channels/features). The platform's contract is
that such output becomes a `views_frames` frame and satisfies the published
conformance suites. This test fabricates that adapter output and drives it all the
way through `assert_frame_contract` + `assert_summarizer_contract` — proving the
contract end-to-end **with no sibling-repo change**. The real proof (a consumer
running this in *its* CI) is the owner's migration; this is the interim de-risk.
"""

from __future__ import annotations

import numpy as np

from views_frames import FeatureFrame, SpatialLevel, SpatioTemporalIndex
from views_frames.conformance import assert_frame_contract
from views_frames_summarize.conformance import assert_summarizer_contract


def _adapter_output(t: int, h: int, w: int, c: int) -> np.ndarray:
    """A fake gridded adapter tensor ``[T, H, W, C]`` (deterministic, float32)."""
    rng = np.random.default_rng(42)
    return rng.normal(0.0, 1.0, size=(t, h, w, c)).astype(np.float32)


def _to_feature_frame(grid: np.ndarray) -> FeatureFrame:
    """Reshape ``[T, H, W, C]`` adapter output into a `FeatureFrame (N, F, S=1)`.

    Each ``(time, grid-cell)`` becomes a row; ``C`` becomes the feature axis; the
    deterministic adapter has a single (degenerate) sample, the explicit trailing
    axis the contract requires.
    """
    t, h, w, c = grid.shape
    n = t * h * w
    # row identifiers: time repeated per cell, unit = flattened priogrid index.
    time = np.repeat(np.arange(t, dtype=np.int64), h * w)
    unit = np.tile(np.arange(h * w, dtype=np.int32), t)
    index = SpatioTemporalIndex(time=time, unit=unit, level=SpatialLevel.PGM)
    values = grid.reshape(n, c)[..., np.newaxis]  # (N, F, S=1)
    return FeatureFrame(values, index, [f"channel_{i}" for i in range(c)])


def test_grid_adapter_output_satisfies_the_contract():
    grid = _adapter_output(t=3, h=4, w=5, c=2)
    frame = _to_feature_frame(grid)

    assert frame.n_rows == 3 * 4 * 5
    assert frame.values.shape == (60, 2, 1)
    assert frame.index.has_unique_rows()  # (time, cell) rows are unique by construction

    assert_frame_contract(frame)
    assert_summarizer_contract(frame)


def test_grid_adapter_with_samples_satisfies_the_contract():
    # a probabilistic adapter: S > 1 posterior draws per (cell, feature).
    grid = _adapter_output(t=2, h=3, w=3, c=2)
    n, c = 2 * 3 * 3, 2
    rng = np.random.default_rng(7)
    samples = rng.normal(grid.reshape(n, c)[..., np.newaxis], 0.5, size=(n, c, 16))
    time = np.repeat(np.arange(2, dtype=np.int64), 9)
    unit = np.tile(np.arange(9, dtype=np.int32), 2)
    index = SpatioTemporalIndex(time=time, unit=unit, level=SpatialLevel.PGM)
    frame = FeatureFrame(
        samples.astype(np.float32), index, ["channel_0", "channel_1"]
    )

    assert frame.sample_count == 16 and frame.is_sample
    assert_frame_contract(frame)
    assert_summarizer_contract(frame)
