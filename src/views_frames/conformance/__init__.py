"""The published conformance suite (ADR-016).

A consumer re-runs these contract checks in CI against **its own** frame factories,
at a single governed **conformance-floor** version, so every consumer tests the same
contract (closes the cross-repo gap; register C-10). The checks are plain assertion
functions (no pytest dependency) so they run anywhere.

Usage in a consumer's test::

    from views_frames.conformance import assert_frame_contract
    assert_frame_contract(my_adapter_output())

A consumer whose type is **not** spatiotemporal (a string-keyed evaluation output, e.g.
views-evaluation's ``MetricFrame``) validates against the shared envelope instead, so
the envelope has one written authority rather than re-asserted copies that drift
(ADR-020, register C-46)::

    from views_frames.conformance import assert_frame_envelope
    assert_frame_envelope(my_metric_frame())

The floor is governed in ``GOVERNANCE.md``; ``CONFORMANCE_FLOOR`` records the version
this suite belongs to.
"""

from __future__ import annotations

import tempfile
from typing import Any

import numpy as np

CONFORMANCE_FLOOR = "1.0.0"

__all__ = [
    "CONFORMANCE_FLOOR",
    "assert_cross_level_alignment_law",
    "assert_frame_contract",
    "assert_frame_envelope",
    "assert_index_alignment_laws",
    "assert_reindex_fill_law",
]


def _require_assertions() -> None:
    """Fail loud if assertions are stripped (``python -O``/``-OO``).

    The suite is built from ``assert`` statements; under optimized bytecode every
    check would silently pass regardless of conformance — a verification tool that
    reports green while dead (falsify audit 2026-07, F3). Refuse to run instead.
    """
    if not __debug__:  # pragma: no cover — pytest always runs with assertions on
        raise RuntimeError(
            "the views-frames conformance suite requires assertions; run without "
            "python -O/-OO (PYTHONOPTIMIZE), otherwise every check silently passes"
        )


def assert_frame_envelope(frame: Any) -> None:
    """Assert ``frame`` satisfies the shared **frame envelope**.

    The envelope is the subset of the contract that applies to *any* frame-like value
    object, spatiotemporal or not: float32 values with no object dtype, an explicit
    trailing axis, rows equal to ``n_rows``, and a save/load round-trip that preserves
    the values and every identifier array. It deliberately says nothing about *which*
    identifiers exist or their dtype — that is the spatiotemporal layer's concern.

    This is the single written authority for the envelope so a sibling that re-asserts
    it (views-evaluation's ``MetricFrame``, keyed by string axes — not ``(time, unit)``)
    validates against this checker rather than drifting from it (ADR-020, C-46).

    Raises:
        AssertionError: any part of the envelope is violated.
    """
    _require_assertions()
    values = frame.values
    assert isinstance(values, np.ndarray), "values must be a numpy array"
    assert values.dtype == np.float32, f"values must be float32, got {values.dtype}"
    assert values.dtype != np.dtype(object), "object dtype is banned (list-in-cell)"
    assert values.ndim >= 2, "values must have an explicit trailing sample axis"
    assert values.shape[0] == frame.n_rows, "values rows must equal n_rows"

    _assert_roundtrip(frame)


def assert_frame_contract(frame: Any) -> None:
    """Assert ``frame`` satisfies the full views-frames **spatiotemporal** contract.

    The shared envelope (:func:`assert_frame_envelope`) plus the spatiotemporal
    requirement: complete integer ``time``/``unit`` identifiers of length ``n_rows``.
    (Sample-axis reduction is the ``views_frames_summarize`` package's concern, not the
    contract's — ADR-017.)

    Raises:
        AssertionError: the envelope or the spatiotemporal identifier rule is violated.
    """
    _require_assertions()
    assert_frame_envelope(frame)

    ids = frame.identifiers
    for key in ("time", "unit"):
        assert key in ids, f"missing required identifier '{key}'"
        arr = ids[key]
        assert np.issubdtype(arr.dtype, np.integer), f"'{key}' must be integer"
        assert arr.shape == (frame.n_rows,), f"'{key}' must be length n_rows"


def _assert_roundtrip(frame: Any) -> None:
    with tempfile.TemporaryDirectory() as directory:
        frame.save(directory)
        loaded = type(frame).load(directory)
        assert np.array_equal(loaded.values, frame.values, equal_nan=True), (
            "save/load changed values"
        )
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
    _require_assertions()
    assert index_a.intersect(index_b) == index_b.intersect(index_a), (
        "intersect must be commutative"
    )
    assert index_a.is_superset_of(index_a) is True, "is_superset_of must be reflexive"
    pos = index_a.searchsorted(index_a)
    assert np.array_equal(index_a.time[pos], index_a.time), "searchsorted self-identity"
    assert np.array_equal(index_a.unit[pos], index_a.unit), "searchsorted self-identity"


def assert_reindex_fill_law(frame: Any, target: Any, fill_value: float) -> None:
    """Assert the dense-grid fill law (ADR-026) for ``frame`` against ``target``.

    ``reindex_fill`` aligns a frame to a target index with **no** superset
    requirement, filling absent rows. The law:

    - the result's index equals ``target`` row-for-row (time, unit, level);
    - every target row present in ``frame`` comes through **bit-exact**;
    - every absent row equals ``fill_value`` exactly (NaN-safe comparison);
    - when every target row is present, ``reindex_fill`` degenerates to
      ``reindex`` (filling a superset frame adds nothing).

    Args:
        frame: a frame exposing ``reindex_fill``/``reindex``/``index``/``values``.
        target: a ``SpatioTemporalIndex`` (same level) to densify against.
        fill_value: the fill for absent rows (``NaN`` is legal).

    Raises:
        AssertionError: a law is violated.
    """
    _require_assertions()
    filled = frame.reindex_fill(target, fill_value=fill_value)
    assert filled.index.level == target.level, "reindex_fill must keep the level"
    assert np.array_equal(filled.index.time, target.time), (
        "reindex_fill result index must equal the target (time)"
    )
    assert np.array_equal(filled.index.unit, target.unit), (
        "reindex_fill result index must equal the target (unit)"
    )
    pos = frame.index.searchsorted(target)
    found = pos >= 0
    assert np.array_equal(
        filled.values[found], frame.values[pos[found]], equal_nan=True
    ), "reindex_fill must pass present rows through bit-exact"
    expected = np.full_like(filled.values[~found], np.float32(fill_value))
    assert np.array_equal(filled.values[~found], expected, equal_nan=True), (
        "reindex_fill must set every absent row to fill_value"
    )
    if bool(found.all()):
        assert np.array_equal(
            filled.values, frame.reindex(target).values, equal_nan=True
        ), "reindex_fill on a superset frame must equal reindex"


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
    _require_assertions()
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
