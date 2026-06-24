"""Tower-family tunables (ADR-019) — a fail-loud config dict, no silent defaults.

views-models style: a plain dict of tunables, validated at entry, with **no defaults
anywhere downstream**. ADR-008 (explicit failure) + ADR-009 ("No semantic defaults may
exist silently"): a tower-family function reads each parameter from here, and a missing
key raises a ``ValueError`` naming it rather than falling back to a hidden literal.

``masses`` is **not** here — it stays a per-call argument (it is *what* a caller asks
for, not a tunable). The frozen estimators (``map_estimate``/``hdi``/``quantiles``,
ADR-018) are **out of scope**; this config governs only the tower family
(``hdi_tower``/``tower_point``/``bimodality``/``summarize_tower``).
"""

from __future__ import annotations

from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

# The single source of truth for every tower-family tunable. Edit values here; the
# algorithm code carries no fallback literals (ADR-009).
TOWER_CONFIG: Final[dict[str, Any]] = {
    # The fixed canonical mass grid: a 5% body + a fine high-mass tail to 0.99. Built
    # from rounded literals — never ``np.arange`` (which drifts ~1 ulp across numpy
    # versions and would make every pinned interval non-reproducible; register C-24).
    "canonical_floors": tuple(
        [round(0.05 * i, 2) for i in range(1, 19)]  # 0.05 … 0.90
        + [0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99]  # fine high-mass tail
    ),
    # The tower-tip reads the median of the floor at this mass — the "shorth". 0.5 is
    # the maximally-robust choice: a duplicate would need ~half the draws to hijack it.
    "tip_mass": 0.5,
    # Raw-count zero rule: a row whose every draw is <= this collapses to 0 (the quiet
    # cell). A *count* rule, distinct from ``map_estimate``'s zero-mass-fraction rule.
    "zero_cutoff": 1.0,
    # Bimodality detector (coarse histogram + light smoothing; see bimodality.py).
    "bimodality_bins": 16,
    "bimodality_prominence": 0.40,
    "bimodality_min_mass": 0.15,
    "bimodality_smooth": 3,
    # Row-block size for the memory-bounded estimators (register C-22/C-25).
    "row_block": 1 << 16,
}

# Every key a tower-family function may read. The completeness check is keyed off this,
# so adding a reader without a corresponding key fails the test suite, not production.
REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "canonical_floors",
        "tip_mass",
        "zero_cutoff",
        "bimodality_bins",
        "bimodality_prominence",
        "bimodality_min_mass",
        "bimodality_smooth",
        "row_block",
    }
)


def validate_config(cfg: dict[str, Any]) -> None:
    """Raise ``ValueError`` listing any missing required key (ADR-009 completeness)."""
    missing = REQUIRED_KEYS - cfg.keys()
    if missing:
        raise ValueError(
            f"tower config is missing required key(s): {sorted(missing)}; "
            "no semantic defaults may exist silently (ADR-009)"
        )


def get(key: str, cfg: dict[str, Any] | None = None) -> Any:
    """Fail-loud accessor: raise naming the key rather than returning a default."""
    cfg = TOWER_CONFIG if cfg is None else cfg
    if key not in cfg:
        raise ValueError(
            f"tower config key {key!r} is not set; no silent default (ADR-008/009). "
            f"known keys: {sorted(cfg)}"
        )
    return cfg[key]


def canonical_floors(cfg: dict[str, Any] | None = None) -> NDArray[np.float64]:
    """The fixed grid as a float64 array (rounded literals; never ``np.arange``)."""
    return np.asarray(get("canonical_floors", cfg), dtype=np.float64)


# Import-time guarantee: the shipped config is itself complete.
validate_config(TOWER_CONFIG)
