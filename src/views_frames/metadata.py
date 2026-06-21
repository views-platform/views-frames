"""`FrameMetadata` — the typed, optional-extensible provenance header (ADR-013).

Not a free-form dict: a frozen dataclass with all-optional, validated fields, so
adding a field is a MINOR change and consumers cannot diverge on key names (the
store-side cause of reporting's C-48). It is the typed home for run/eval identity.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any


@dataclass(frozen=True)
class FrameMetadata:
    """Optional provenance carried by a frame. All fields default to ``None``."""

    model: str | None = None
    run_type: str | None = None
    timestamp: int | None = None
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict, omitting unset (``None``) fields."""
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if getattr(self, f.name) is not None
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FrameMetadata:
        """Reconstruct from a dict, ignoring unknown keys (forward-compatible)."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
