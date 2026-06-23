"""Cross-frame parity matrix (C-31).

The three frames are separate siblings (ADR-011 Option C) carrying byte-identical
shared methods (`reindex`/`select`/`with_metadata`/`save`-`load`) with no shared
base. The suite previously tested `reindex` on `PredictionFrame` only, so a
divergent edit to a twin's `reindex` would pass CI. This module parametrizes the
shared surface over ALL THREE frame types so divergence fails loud here.

🟫 Beige: realistic alignment/selection a consumer performs every request.
🟥 Red:   a non-superset `reindex` must raise, never silently truncate (C-26).
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import (
    FeatureFrame,
    FrameMetadata,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
    TargetFrame,
)


def _index(times, units, level=SpatialLevel.PGM):
    return SpatioTemporalIndex(
        np.array(times, dtype=np.int64), np.array(units, dtype=np.int32), level
    )


# Each builder fills every cell of row ``i`` with ``marker[i]`` so a row can be
# traced through reindex/select via ``_row_marker``.
def _build_prediction(idx, marker):  # (N, S=2)
    return PredictionFrame(np.tile(marker.reshape(-1, 1), (1, 2)), idx)


def _build_feature(idx, marker):  # (N, F=2, S=2)
    return FeatureFrame(np.tile(marker.reshape(-1, 1, 1), (1, 2, 2)), idx, ["a", "b"])


def _build_target(idx, marker):  # (N, 1)
    return TargetFrame(marker.reshape(-1, 1), idx)


BUILDERS = [
    ("prediction", _build_prediction),
    ("feature", _build_feature),
    ("target", _build_target),
]


def _marker(n):
    return (10 + np.arange(n)).astype(np.float32)


def _row_marker(frame):
    """The per-row marker value (all cells in a row are equal)."""
    return frame.values.reshape(frame.n_rows, -1)[:, 0]


# --- reindex (the C-31 gap: FF/TF were untested) -----------------------------


@pytest.mark.parametrize("name,build", BUILDERS)
def test_reindex_to_subset_aligns(name, build):
    a = _index([1, 1, 2], [10, 11, 10])  # 3 rows, markers 10/11/12
    frame = build(a, _marker(3))
    other = _index([2, 1], [10, 11])  # subset, reordered
    out = frame.reindex(other)
    assert out.n_rows == 2
    assert np.array_equal(out.identifiers["time"], [2, 1])
    assert np.array_equal(out.identifiers["unit"], [10, 11])
    # (2,10) was source row 2 (marker 12); (1,11) was source row 1 (marker 11)
    assert np.array_equal(_row_marker(out), [12.0, 11.0])


@pytest.mark.parametrize("name,build", BUILDERS)
def test_reindex_non_superset_raises(name, build):
    # 🟥 partial overlap must fail loud, not silently truncate (C-26).
    a = _index([1, 2], [10, 10])
    frame = build(a, _marker(2))
    other = _index([1, 3], [10, 10])  # (3,10) absent from this frame
    with pytest.raises(ValueError, match="superset"):
        frame.reindex(other)


@pytest.mark.parametrize("name,build", BUILDERS)
def test_reindex_self_is_identity(name, build):
    a = _index([1, 2, 3], [10, 10, 10])
    frame = build(a, _marker(3))
    out = frame.reindex(frame.index)
    assert np.array_equal(out.values, frame.values)
    assert np.array_equal(out.identifiers["time"], frame.identifiers["time"])


# --- select / with_metadata / save-load parity (lock against divergence) -----


@pytest.mark.parametrize("name,build", BUILDERS)
def test_select_positions_parity(name, build):
    a = _index([1, 1, 2], [10, 11, 10])
    frame = build(a, _marker(3))
    out = frame.select(np.array([2, 0], dtype=np.intp))
    assert out.n_rows == 2
    assert np.array_equal(_row_marker(out), [12.0, 10.0])


@pytest.mark.parametrize("name,build", BUILDERS)
def test_select_mask_parity(name, build):
    a = _index([1, 1, 2], [10, 11, 10])
    frame = build(a, _marker(3))
    out = frame.select(np.array([True, False, True]))
    assert out.n_rows == 2
    assert np.array_equal(_row_marker(out), [10.0, 12.0])


@pytest.mark.parametrize("name,build", BUILDERS)
def test_with_metadata_shares_buffer_parity(name, build):
    a = _index([1, 2], [10, 10])
    frame = build(a, _marker(2))
    out = frame.with_metadata(FrameMetadata(model="x"))
    assert np.shares_memory(frame.values, out.values)
    assert out.metadata.model == "x"


@pytest.mark.parametrize("name,build", BUILDERS)
def test_save_load_roundtrip_parity(name, build, tmp_path):
    a = _index([1, 2, 3], [10, 10, 10])
    frame = build(a, _marker(3))
    cls = type(frame)
    frame.save(tmp_path / name)
    loaded = cls.load(tmp_path / name)
    assert np.array_equal(loaded.values, frame.values)
    assert np.array_equal(loaded.identifiers["time"], frame.identifiers["time"])
    assert loaded.index.level is frame.index.level
