"""Tests for the serialization adapters (G1 io/npz, G2 io/arrow)."""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import SpatialLevel, SpatioTemporalIndex
from views_frames.io import arrow, npz


def _state_2d():
    return {
        "values": np.arange(6, dtype=np.float32).reshape(3, 2),
        "time": np.array([1, 1, 2], dtype=np.int64),
        "unit": np.array([10, 11, 10], dtype=np.int32),
        "level": "pgm",
        "metadata": {"model": "m"},
        "feature_names": None,
    }


def _state_3d():
    return {
        "values": np.arange(12, dtype=np.float32).reshape(2, 3, 2),
        "time": np.array([1, 2], dtype=np.int64),
        "unit": np.array([10, 20], dtype=np.int32),
        "level": "pgm",
        "metadata": {},
        "feature_names": ["a", "b", "c"],
    }


# --- G1: io/npz --------------------------------------------------------------


def test_npz_roundtrip_2d(tmp_path):
    st = _state_2d()
    npz.save(tmp_path, **st)
    out = npz.load(tmp_path)
    assert np.array_equal(out["values"], st["values"])
    assert np.array_equal(out["time"], st["time"])
    assert out["level"] == "pgm"
    assert out["metadata"] == {"model": "m"}


def test_npz_roundtrip_with_feature_names(tmp_path):
    st = _state_3d()
    npz.save(tmp_path, **st)
    out = npz.load(tmp_path)
    assert out["feature_names"] == ["a", "b", "c"]
    assert np.array_equal(out["values"], st["values"])


def test_npz_mmap_returns_memmap(tmp_path):
    st = _state_2d()
    npz.save(tmp_path, **st)
    out = npz.load(tmp_path, mmap=True)
    assert isinstance(out["values"], np.memmap)


def test_npz_builds_index_from_state(tmp_path):
    st = _state_2d()
    npz.save(tmp_path, **st)
    out = npz.load(tmp_path)
    idx = SpatioTemporalIndex(out["time"], out["unit"], SpatialLevel(out["level"]))
    assert idx.n_rows == 3


# --- G2: io/arrow ------------------------------------------------------------

pytest.importorskip("pyarrow")


def test_arrow_roundtrip_2d(tmp_path):
    st = _state_2d()
    path = tmp_path / "frame.parquet"
    arrow.save(path, **st)
    out = arrow.load(path)
    assert np.array_equal(out["values"], st["values"])
    assert np.array_equal(out["time"], st["time"])
    assert np.array_equal(out["unit"], st["unit"])
    assert out["level"] == "pgm"
    assert out["metadata"] == {"model": "m"}


def test_arrow_roundtrip_3d_features(tmp_path):
    st = _state_3d()
    path = tmp_path / "frame.parquet"
    arrow.save(path, **st)
    out = arrow.load(path)
    assert out["values"].shape == (2, 3, 2)
    assert np.array_equal(out["values"], st["values"])
    assert out["feature_names"] == ["a", "b", "c"]


def test_arrow_is_flat_columnar(tmp_path):
    import pyarrow.parquet as pq

    st = _state_2d()
    path = tmp_path / "frame.parquet"
    arrow.save(path, **st)
    table = pq.read_table(path)
    # one scalar row per (time, unit, sample): 3 rows x 2 samples = 6
    assert table.num_rows == 6
    assert set(table.column_names) == {"time", "unit", "sample", "value"}
