"""Tests for the serialization adapters (G1 io/npz, G2 io/arrow)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from views_frames import (
    FeatureFrame,
    PredictionFrame,
    SpatialLevel,
    SpatioTemporalIndex,
)
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


def test_npz_mmap_is_read_only(tmp_path):
    # The mmap load opens with mmap_mode="r": the buffer must be non-writeable and
    # an in-place write must raise — previously asserted only as isinstance(memmap)
    # (2026-07 audit, F2 / register C-70; the read-only-ness is the safety property).
    st = _state_2d()
    npz.save(tmp_path, **st)
    out = npz.load(tmp_path, mmap=True)
    assert out["values"].flags.writeable is False
    with pytest.raises(ValueError, match="read-only"):
        out["values"][0, 0] = 99.0


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


# --- G2 RED: wire-contract ordering validation on load (#199, ADR-013 §4.5b) --
# 🟥 Red team: `load` reshapes positionally, so the row order IS the contract.
# A reordered / truncated / cross-swapped table previously reshaped plausible
# floats into the wrong sample slots silently; every such violation must raise.


def _saved_table(tmp_path):
    import pyarrow.parquet as pq

    st = _state_2d()
    path = tmp_path / "frame.parquet"
    arrow.save(path, **st)
    return path, pq.read_table(str(path))


def test_arrow_load_reordered_rows_raise(tmp_path):
    # Reversing the rows breaks the written tile(arange(S), N) sample order.
    import pyarrow.parquet as pq

    path, table = _saved_table(tmp_path)
    pq.write_table(table.take(list(range(table.num_rows - 1, -1, -1))), str(path))
    with pytest.raises(ValueError, match="reordered"):
        arrow.load(path)


def test_arrow_load_truncated_table_raises(tmp_path):
    # Dropping a row makes the row count a non-multiple of n_samples.
    import pyarrow.parquet as pq

    path, table = _saved_table(tmp_path)
    pq.write_table(table.slice(0, table.num_rows - 1), str(path))
    with pytest.raises(ValueError, match="truncated or filtered"):
        arrow.load(path)


def test_arrow_load_cross_cell_row_swap_raises(tmp_path):
    # Swap the sample-0 rows of two different (time, unit) cells: the sample
    # column still reads tile(arange(S), N), so the tile check alone passes —
    # only the block-constancy check catches the identifier/value misalignment.
    import pyarrow.parquet as pq

    path, table = _saved_table(tmp_path)
    order = list(range(table.num_rows))
    order[0], order[2] = order[2], order[0]  # (1,10,s0) <-> (1,11,s0)
    pq.write_table(table.take(order), str(path))
    with pytest.raises(ValueError, match="not constant within"):
        arrow.load(path)


def test_arrow_load_whole_cell_reorder_still_loads(tmp_path):
    # 🟩 Boundary of the contract: moving a WHOLE cell block (identifiers travel
    # with their draws) is a consistent table — a reordered-but-valid frame
    # loads, with the identifiers following the moved values.
    import pyarrow.parquet as pq

    path, table = _saved_table(tmp_path)
    order = [2, 3, 0, 1, 4, 5]  # swap the first two complete (time, unit) blocks
    pq.write_table(table.take(order), str(path))
    out = arrow.load(path)
    assert np.array_equal(out["unit"], np.array([11, 10, 10]))
    assert np.array_equal(out["values"][0], np.array([2.0, 3.0], dtype=np.float32))


# 🟩 Cross-version load (register C-79). Every other IO test writes and reads in ONE
# process at ONE version. That proves the codec is self-consistent and nothing about
# the property that matters for a data-contract package: that a file written by an
# EARLIER release still loads.
#
# The fixtures were written by the `save` functions extracted from the `v1.8.0` tag
# (see `scripts/gen_arrow_crossversion_fixture.py`), which predates the three
# `ValueError` wire-contract paths v1.10.1 added to `arrow.load` (register C-72). So
# they are evidence that those rules — derived from what `save` writes today — accept a
# file written before they existed. Consumers on this path hold archived shards
# (views-postprocessing, views-faoapi #100).
#
# Metadata deliberately carries `timestamp` and `seed` **ints**, not just strings: a
# JSON type drift on a non-string header field crossing versions is the bug class
# register C-90 is about, and string-only fixtures would not exercise it.
#
# The digests are of `values.tobytes()`, so a reshape producing plausible-but-wrong
# sample slots fails here even though every shape assertion would still pass.

_FIXTURES = Path(__file__).parent / "fixtures"

_ARROW_PREDICTION_SHA = (
    "ed1b8370ff480a85a4f6a81847c194b87a8c8db7c57e4afe5c57bb1b35c15f39"
)
_ARROW_FEATURE_SHA = "5b65d2161fab1cf85c83eaaeadadcb76ca171d2d00006136e727ac170d4ebf15"
_NPZ_PREDICTION_SHA = "74330ba96baa66dc5c6e8bf53d1b00bfe2e46b0749b9ac84cee8b4559fb3815f"


def test_v1_8_0_prediction_parquet_still_loads():
    state = arrow.load(_FIXTURES / "arrow_v1_8_0_prediction.parquet")

    assert state["values"].shape == (4, 3)
    assert state["values"].dtype == np.float32
    assert state["level"] == "pgm"
    assert state["metadata"] == {
        "model": "fixture",
        "run_id": "c79",
        "timestamp": 202608,
        "seed": 7,
    }
    assert state["feature_names"] is None
    np.testing.assert_array_equal(state["time"], np.array([1, 1, 2, 2]))
    np.testing.assert_array_equal(state["unit"], np.array([10, 11, 10, 11]))
    assert (
        hashlib.sha256(state["values"].tobytes()).hexdigest() == _ARROW_PREDICTION_SHA
    )


def test_v1_8_0_feature_parquet_still_loads():
    state = arrow.load(_FIXTURES / "arrow_v1_8_0_feature.parquet")

    assert state["values"].shape == (4, 2, 3)
    assert state["values"].dtype == np.float32
    assert state["level"] == "pgm"
    assert state["metadata"] == {
        "model": "fixture",
        "data_version": "c79",
        "seed": 11,
    }
    assert state["feature_names"] == ["ged_sb", "pop"]
    assert hashlib.sha256(state["values"].tobytes()).hexdigest() == _ARROW_FEATURE_SHA


def test_v1_8_0_npz_frame_still_loads_through_the_public_api():
    """The path a consumer actually uses to revive archived data.

    `arrow` is checked above at the codec level. This goes through the whole public
    route — `PredictionFrame.load` -> `npz.load` -> `SpatioTemporalIndex(...)` ->
    `FrameMetadata.from_dict` — so a future construction-time invariant or a
    `SpatialLevel`/dtype tightening that would reject an archived file fails here.
    """
    frame = PredictionFrame.load(_FIXTURES / "npz_v1_8_0_prediction")

    assert frame.values.shape == (4, 3)
    assert frame.values.dtype == np.float32
    assert frame.index.level is SpatialLevel.PGM
    assert frame.metadata.model == "fixture"
    assert frame.metadata.run_id == "c79-npz"
    assert frame.metadata.timestamp == 202608
    assert frame.metadata.seed == 3
    np.testing.assert_array_equal(frame.index.time, np.array([1, 1, 2, 2]))
    assert hashlib.sha256(frame.values.tobytes()).hexdigest() == _NPZ_PREDICTION_SHA


def test_todays_writer_still_reproduces_the_v1_8_0_fixture(tmp_path):
    """The writer-drift guard (register C-79) — and the reason it is a *test*.

    C-79's value was always its trigger: the moment `save` changes, an unmodified
    writer no longer exists to produce a fixture from, so the chance to capture one
    is gone. The first version of this guard compared the *source text* of `save`
    inside the generator script — which nothing ran, so it enforced nothing, and which
    a `ruff format` sweep would have tripped while a module-level change altering the
    written bytes slipped past it.

    This compares **bytes**: today's writer, given the fixture's inputs, must still
    produce the committed file exactly. Reformatting cannot trip it; any change that
    alters output does.
    """
    rng = np.random.default_rng(20260818)
    out = tmp_path / "today.parquet"
    arrow.save(
        out,
        values=rng.random((4, 3), dtype=np.float32),
        time=np.array([1, 1, 2, 2], dtype=np.int64),
        unit=np.array([10, 11, 10, 11], dtype=np.int64),
        level="pgm",
        metadata={"model": "fixture", "run_id": "c79", "timestamp": 202608, "seed": 7},
    )
    committed = (_FIXTURES / "arrow_v1_8_0_prediction.parquet").read_bytes()
    assert out.read_bytes() == committed, (
        "today's `arrow.save` no longer reproduces the v1.8.0 fixture. Before landing "
        "the change to `save`, regenerate the cross-version fixtures from the LAST "
        "release that still carries the old writer — afterwards no unmodified writer "
        "exists to produce one (register C-79)."
    )
