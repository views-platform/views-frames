"""The tower-family config (ADR-019) — fail-loud, no silent defaults (ADR-008/009).

Categories per ADR-005:
  🟩 Green — the shipped config is complete; accessors return the set values.
  🟥 Red — a missing key fails loud naming it; an unknown key fails loud.
"""

from __future__ import annotations

import numpy as np
import pytest

from views_frames_summarize import config

# ============================ 🟩 GREEN — happy path ==========================


def test_green_shipped_config_is_complete():
    # The shipped TOWER_CONFIG passes validation (no missing keys); import-time too.
    config.validate_config(config.TOWER_CONFIG)


def test_green_get_returns_the_set_value():
    assert config.get("tip_mass") == 0.5
    assert config.get("zero_cutoff") is None  # magnitude rule off by default (C-45)
    assert config.get("row_block") == (1 << 16)


def test_green_disabled_zero_cutoff_still_passes_validation():
    # A present-but-None tunable is "disabled", not "missing" — completeness holds.
    config.validate_config({**config.TOWER_CONFIG, "zero_cutoff": None})


def test_green_required_keys_match_config_keys():
    # The manifest and the shipped dict agree exactly — guards drift either way.
    assert set(config.TOWER_CONFIG) == set(config.REQUIRED_KEYS)


def test_green_canonical_floors_are_rounded_literals_not_arange():
    # Reproducible grid (register C-24): rounded literals, never np.arange drift.
    floors = config.canonical_floors()
    expected = np.array(
        [round(0.05 * i, 2) for i in range(1, 19)]
        + [0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99],
        dtype=np.float64,
    )
    assert np.array_equal(floors, expected)
    assert floors.dtype == np.float64


# =========================== 🟥 RED — adversarial ============================


@pytest.mark.parametrize("key", sorted(config.REQUIRED_KEYS))
def test_red_missing_required_key_fails_loud_naming_it(key):
    # ADR-009: a missing key raises ValueError naming it — no silent default.
    cfg = dict(config.TOWER_CONFIG)
    del cfg[key]
    with pytest.raises(ValueError, match=key):
        config.validate_config(cfg)


def test_red_get_unknown_key_fails_loud():
    with pytest.raises(ValueError, match="not set"):
        config.get("nonexistent_key")


def test_red_get_missing_key_in_custom_cfg_fails_loud():
    with pytest.raises(ValueError, match="tip_mass"):
        config.get("tip_mass", {"zero_cutoff": 1.0})


def test_red_canonical_floors_missing_key_fails_loud():
    with pytest.raises(ValueError, match="canonical_floors"):
        config.canonical_floors({"tip_mass": 0.5})
