"""Flat-columnar (parquet) serialization — the scalable interchange format.

One scalar cell per ``(time, unit, sample)`` (features become columns for a 3-D
feature frame); the scalable replacement for the banned list-in-cell encoding
(README §7). This is the **only** module permitted to import ``pyarrow`` (the
optional ``[arrow]`` extra). Operates on a frame's state dict (register C-09).

The reconstruction shape (``n_features`` / ``n_samples``) and the header (level,
metadata, feature_names) ride in the parquet schema key-value metadata so the
round-trip is exact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from views_frames._typing import IntArray


def save(
    path: Path | str,
    *,
    values: NDArray[np.float32],
    time: IntArray,
    unit: IntArray,
    level: str,
    metadata: dict[str, Any],
    feature_names: list[str] | None = None,
) -> None:
    """Write a frame's state as flat-columnar parquet (one scalar cell per row)."""
    if values.ndim == 2:
        n, s = values.shape
        n_features = 0
    elif values.ndim == 3:
        n, n_features, s = values.shape
    else:
        raise ValueError(f"unsupported values.ndim={values.ndim}")

    time_col = np.repeat(time, s)
    unit_col = np.repeat(unit, s)
    sample_col = np.tile(np.arange(s, dtype=np.int32), n)
    columns: dict[str, NDArray[Any]] = {
        "time": time_col,
        "unit": unit_col,
        "sample": sample_col,
    }
    if values.ndim == 2:
        columns["value"] = values.reshape(n * s)
    else:
        for f in range(n_features):
            columns[f"f{f}"] = np.ascontiguousarray(values[:, f, :]).reshape(n * s)

    header = {
        "level": level,
        "metadata": metadata,
        "feature_names": feature_names,
        "n_features": n_features,
        "n_samples": s,
        "ndim": int(values.ndim),
    }
    table = pa.table(columns)
    table = table.replace_schema_metadata({"views_frames": json.dumps(header)})
    pq.write_table(table, str(path))


def load(path: Path | str) -> dict[str, Any]:
    """Read a flat-columnar parquet frame state written by :func:`save`."""
    table = pq.read_table(str(path))
    raw = table.schema.metadata or {}
    header = json.loads(raw[b"views_frames"].decode())
    s = int(header["n_samples"])
    ndim = int(header["ndim"])

    time_col = table.column("time").to_numpy()
    unit_col = table.column("unit").to_numpy()
    n = time_col.shape[0] // s
    time = time_col.reshape(n, s)[:, 0]
    unit = unit_col.reshape(n, s)[:, 0]

    if ndim == 2:
        values = table.column("value").to_numpy().reshape(n, s).astype(np.float32)
    else:
        n_features = int(header["n_features"])
        stacked = [
            table.column(f"f{f}").to_numpy().reshape(n, s) for f in range(n_features)
        ]
        values = np.stack(stacked, axis=1).astype(np.float32)

    return {
        "values": values,
        "time": np.ascontiguousarray(time),
        "unit": np.ascontiguousarray(unit),
        "level": header["level"],
        "metadata": header.get("metadata", {}),
        "feature_names": header.get("feature_names"),
    }
