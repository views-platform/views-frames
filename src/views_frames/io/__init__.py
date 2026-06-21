"""Serialization adapters — frame ↔ bytes *format*, never *transport* (ADR-009).

Two scalable formats; list-in-cell object-dtype is banned (README §7):

- `npz` — native ``values.npy`` + ``identifiers.npz`` (mmap-capable).
- `arrow` — flat-columnar parquet (the scalable interchange format).

`pyarrow` is imported only inside this subpackage, never in the core frames.
"""

from __future__ import annotations

__all__: list[str] = []
