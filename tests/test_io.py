"""Tests for the serialization adapters (G1 io/npz, G2 io/arrow)."""

from __future__ import annotations

import numpy as np
import pytest

from views_frames import FeatureFrame, SpatialLevel, SpatioTemporalIndex
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


# --- G1 RED: io/npz failure modes (C-29) -------------------------------------
# 🟥 Red team: a corrupt / missing sidecar or a feature_names-less state must
# fail loud, never load a wrong frame silently.


def test_npz_load_missing_values_file_raises(tmp_path):
    st = _state_2d()
    npz.save(tmp_path, **st)
    (tmp_path / "values.npy").unlink()
    with pytest.raises(FileNotFoundError):
        npz.load(tmp_path)


def test_npz_load_missing_header_raises(tmp_path):
    st = _state_2d()
    npz.save(tmp_path, **st)
    (tmp_path / "header.json").unlink()
    with pytest.raises(FileNotFoundError):
        npz.load(tmp_path)


def test_feature_frame_load_without_feature_names_raises(tmp_path):
    # A state saved without feature_names cannot rebuild a FeatureFrame.
    st = _state_2d()  # feature_names is None
    npz.save(tmp_path, **st)
    with pytest.raises(ValueError, match="feature_names"):
        FeatureFrame.load(tmp_path)


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


# --- G2 RED: io/arrow failure modes (C-29) -----------------------------------
# 🟥 Red team: only 2-D/3-D state serializes; a non-frame parquet must not load.


@pytest.mark.parametrize(
    "bad_values",
    [
        np.zeros(3, dtype=np.float32),  # 1-D
        np.zeros((2, 2, 2, 2), dtype=np.float32),  # 4-D
    ],
)
def test_arrow_save_rejects_unsupported_ndim(tmp_path, bad_values):
    st = {**_state_2d(), "values": bad_values}
    with pytest.raises(ValueError, match="unsupported values.ndim"):
        arrow.save(tmp_path / "frame.parquet", **st)


def test_arrow_load_non_frame_parquet_raises(tmp_path):
    # A parquet without the views_frames schema metadata is not a frame.
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "plain.parquet"
    pq.write_table(pa.table({"x": [1, 2, 3]}), str(path))
    with pytest.raises(KeyError):
        arrow.load(path)
