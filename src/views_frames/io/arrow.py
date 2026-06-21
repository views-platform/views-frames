"""Flat-columnar (parquet) serialization — the scalable interchange format.

One row per ``(time, unit[, sample])``, scalar cells only, zero-copy Arrow write;
the scalable replacement for the banned list-in-cell encoding (README §7). This
is the **only** module permitted to import ``pyarrow`` (an optional extra).
STUB — implementation lands in Epic 2.
"""

from __future__ import annotations

from typing import Any


def save(frame: Any, path: str) -> None:  # noqa: ANN401 — generic frame state
    """Write a frame to ``path`` as flat-columnar parquet (one scalar cell per row)."""
    raise NotImplementedError(
        "views-frames is a stub skeleton (Epic 1); io.arrow lands in Epic 2"
    )


def load(path: str) -> Any:  # noqa: ANN401
    """Read a frame from a flat-columnar parquet ``path``."""
    raise NotImplementedError(
        "views-frames is a stub skeleton (Epic 1); io.arrow lands in Epic 2"
    )
