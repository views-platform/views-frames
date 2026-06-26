"""Fail-loud guards on `ReconciliationModule`'s injected mapping (Epic 11 S4).

The orchestrator holds the `(time, priogrid_gid) -> country_id` mapping as injected
numpy arrays (ADR-014/ADR-023 — never fetched here). Its `__init__` rejects a
mis-shaped mapping loudly. numpy + views-frames only.
"""

import numpy as np
import pytest

from views_frames_reconcile import ReconciliationModule


def test_map_keys_must_be_m_by_2():
    with pytest.raises(ValueError, match=r"\(M, 2\)"):
        ReconciliationModule(np.array([1, 2, 3]), np.array([10, 20, 30]))


def test_map_vals_must_be_length_m():
    keys = np.array([[1, 100], [1, 101]])  # (2, 2)
    with pytest.raises(ValueError, match="length-M"):
        ReconciliationModule(keys, np.array([[10], [20]]))  # wrong shape (2, 1)


def test_valid_mapping_constructs():
    mod = ReconciliationModule(np.array([[1, 100], [1, 101]]), np.array([10, 10]))
    assert isinstance(mod, ReconciliationModule)
