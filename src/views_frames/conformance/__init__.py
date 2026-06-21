"""The published conformance suite (ADR-016).

A consumer re-runs these contract checks in CI against **its own** frame factories,
at a single governed **conformance-floor** version, so every consumer tests the same
contract (closes the cross-repo gap; register C-10). The checks are plain assertion
functions (no pytest dependency) so they run anywhere.

Usage in a consumer's test::

    from views_frames.conformance import assert_frame_contract
    assert_frame_contract(my_adapter_output())

The floor is governed in ``GOVERNANCE.md``; ``CONFORMANCE_FLOOR`` records the version
this suite belongs to.
"""

from __future__ import annotations

import tempfile
from typing import Any

import numpy as np

CONFORMANCE_FLOOR = "0.1.0"

__all__ = [
    "CONFORMANCE_FLOOR",
    "assert_cross_level_alignment_law",
    "assert_frame_contract",
    "assert_index_alignment_laws",
]


def assert_frame_contract(frame: Any) -> None:
    """Assert ``frame`` satisfies the views-frames data contract.

    Checks the structural invariants (float32 values, no object dtype, an explicit
    trailing axis, complete integer identifiers of length ``n_rows``) and the
    save/load round-trip. (Sample-axis reduction is the ``views_frames_summarize``
    package's concern, not the contract's — ADR-017.)

    Raises:
        AssertionError: any part of the contract is violated.
    """
    values = frame.values
    assert isinstance(values, np.ndarray), "values must be a numpy array"
    assert values.dtype == np.float32, f"values must be float32, got {values.dtype}"
    assert values.dtype != np.dtype(object), "object dtype is banned (list-in-cell)"
    assert values.ndim >= 2, "values must have an explicit trailing sample axis"
    assert values.shape[0] == frame.n_rows, "values rows must equal n_rows"

    ids = frame.identifiers
    for key in ("time", "unit"):
        assert key in ids, f"missing required identifier '{key}'"
        arr = ids[key]
        assert np.issubdtype(arr.dtype, np.integer), f"'{key}' must be integer"
        assert arr.shape == (frame.n_rows,), f"'{key}' must be length n_rows"

    _assert_roundtrip(frame)


def _assert_roundtrip(frame: Any) -> None:
    with tempfile.TemporaryDirectory() as directory:
        frame.save(directory)
        loaded = type(frame).load(directory)
        assert np.array_equal(loaded.values, frame.values), "save/load changed values"
        for key, arr in frame.identifiers.items():
            assert np.array_equal(loaded.identifiers[key], arr), (
                f"save/load changed identifier '{key}'"
            )


def assert_index_alignment_laws(index_a: Any, index_b: Any) -> None:
    """Assert the same-level alignment laws hold for two indices at the same level.

    - intersection is commutative;
    - an index is a superset of itself (reflexive);
    - ``searchsorted`` against itself is an identity round-trip.

    Raises:
        AssertionError: a law is violated.
    """
    assert index_a.intersect(index_b) == index_b.intersect(index_a), (
        "intersect must be commutative"
    )
    assert index_a.is_superset_of(index_a) is True, "is_superset_of must be reflexive"
    pos = index_a.searchsorted(index_a)
    assert np.array_equal(index_a.time[pos], index_a.time), "searchsorted self-identity"
    assert np.array_equal(index_a.unit[pos], index_a.unit), "searchsorted self-identity"


def assert_cross_level_alignment_law(
    index: Any, mapping: Any, target_level: Any
) -> None:
    """Assert ``cross_level_align`` honours the **time-varying** injected mapping.

    The mapping is keyed by ``(time, unit)`` (register C-20), so the same unit may
    map to different target units in different time steps. The law:

    - every row's target unit equals ``mapping[(time, unit)]`` (time-varying remap);
    - ``time`` is preserved row-for-row;
    - the produced index carries ``target_level``.

    Args:
        index: a ``SpatioTemporalIndex`` to remap.
        mapping: a ``{(time, unit): target_unit}`` mapping covering every row.
        target_level: the ``SpatialLevel`` to remap to.

    Raises:
        AssertionError: the remap disagrees with the mapping, drops time, or
            produces the wrong level.
    """
    aligned = index.cross_level_align(mapping, target_level)
    assert aligned.level is target_level, "cross_level_align must carry target_level"
    assert np.array_equal(aligned.time, index.time), "cross_level_align must keep time"
    pairs = zip(index.time, index.unit, strict=True)
    expected = np.array(
        [mapping[(int(t), int(u))] for t, u in pairs],
        dtype=aligned.unit.dtype,
    )
    assert np.array_equal(aligned.unit, expected), (
        "cross_level_align must honour the (time, unit)-keyed mapping per row"
    )
