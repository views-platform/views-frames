"""`FrameMetadata` — the typed, optional-extensible provenance header (ADR-013).

Not a free-form dict: a frozen dataclass with all-optional, *declared* fields, so
adding a field is a MINOR change and consumers cannot diverge on key names (the
store-side cause of reporting's C-48). It is the typed home for run/eval identity.

The field **values** are not validated — ADR-013's as-built amendment records that
"validated at construction" applies to the frames and identifiers, not to the header's
own fields, and checking them here would be the semantic inference ADR-003 forbids.
See ``docs/CICs/FrameMetadata.md`` §4.

Provenance fields are **generic only** (``run_id``, ``data_version``): meaningful for
any frame. Evaluation-specific provenance (``scoring_code_version``, full-precision
``evaluation_timestamp``) stays in views-evaluation's ``MetricFrame`` and must not leak
into this generic header (ADR-020, register C-47).
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
    run_id: str | None = None
    data_version: str | None = None

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
