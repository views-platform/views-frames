"""Native serialization: ``values.npy`` + ``identifiers.npz`` (mmap-capable).

Round-trips the frame plus its typed header via a frame-declared state contract,
so this module stays generic and does not accrete per-frame schema (register
C-09). STUB — implementation lands in Epic 2.
"""

from __future__ import annotations

from typing import Any


def save(frame: Any, directory: str) -> None:  # noqa: ANN401 — generic frame state
    """Write a frame to ``directory`` as ``.npy`` + ``.npz`` (+ header sidecars)."""
    raise NotImplementedError(
        "views-frames is a stub skeleton (Epic 1); io.npz lands in Epic 2"
    )


def load(directory: str, mmap: bool = False) -> Any:  # noqa: ANN401
    """Read a frame from ``directory``; ``mmap`` keeps peak RAM at the working set."""
    raise NotImplementedError(
        "views-frames is a stub skeleton (Epic 1); io.npz lands in Epic 2"
    )
