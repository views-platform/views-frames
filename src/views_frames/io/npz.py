"""Native serialization: ``values.npy`` + ``identifiers.npz`` (+ JSON header).

Operates on a frame's **state dict** — it carries no per-frame schema (register
C-09); each frame maps its fields to/from the state. The ``mmap`` path returns a
read-only memmap and preserves the subclass so peak RAM stays the working set
(register C-07, README §7) — the proven ``PredictionFrame`` idiom.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from views_frames._typing import IntArray


def save(
    directory: Path | str,
    *,
    values: NDArray[np.float32],
    time: IntArray,
    unit: IntArray,
    level: str,
    metadata: dict[str, Any],
    feature_names: list[str] | None = None,
) -> None:
    """Write a frame's state (npy values + npz identifiers + json header)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    np.save(directory / "values.npy", values)
    np.savez(directory / "identifiers.npz", time=time, unit=unit)
    header: dict[str, Any] = {"level": level, "metadata": metadata}
    if feature_names is not None:
        header["feature_names"] = feature_names
    payload = json.dumps(header, sort_keys=True, default=str)
    (directory / "header.json").write_text(payload)


def load(directory: Path | str, *, mmap: bool = False) -> dict[str, Any]:
    """Read a frame's state; ``mmap=True`` returns ``values`` as a read-only memmap."""
    directory = Path(directory)
    mmap_mode: Literal["r"] | None = "r" if mmap else None
    values = np.load(directory / "values.npy", mmap_mode=mmap_mode)
    with np.load(directory / "identifiers.npz") as npz:
        time = npz["time"]
        unit = npz["unit"]
    header = json.loads((directory / "header.json").read_text())
    return {
        "values": values,
        "time": time,
        "unit": unit,
        "level": header["level"],
        "metadata": header.get("metadata", {}),
        "feature_names": header.get("feature_names"),
    }
