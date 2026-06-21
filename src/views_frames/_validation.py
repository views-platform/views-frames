"""Shared construction-time invariant checks (ADR-008, ADR-009).

Fail loud at construction. The guarantee is **structural, not temporal**: the
leaf validates integer dtype / length-N / completeness, but ``time`` is an opaque
integer — epoch, range, and monotonicity are a producer concern (register C-11).

This is the numpy-only replacement for the ``pd.isna`` check used today in
``views-pipeline-core/.../data/prediction_frame.py`` (register C-17): identifiers
are required to be **integer** dtype, which makes them complete by construction
(integers cannot be NaN).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

REQUIRED_IDENTIFIERS = ("time", "unit")


def validate_identifiers(
    identifiers: dict[str, NDArray[np.integer]], n_rows: int
) -> None:
    """Assert identifiers are integer 1-D arrays of length ``n_rows``, complete.

    Args:
        identifiers: Mapping of identifier name to a 1-D integer array.
        n_rows: The expected length of every identifier array.

    Raises:
        ValueError: A required identifier is missing, an array is not 1-D, or an
            array length does not match ``n_rows``.
        TypeError: An identifier is not a numpy array or not an integer dtype.
    """
    for key in REQUIRED_IDENTIFIERS:
        if key not in identifiers:
            raise ValueError(f"Missing required identifier: '{key}'")
    for key, arr in identifiers.items():
        if not isinstance(arr, np.ndarray):
            raise TypeError(
                f"Identifier '{key}' must be a numpy array, "
                f"got {type(arr).__name__}"
            )
        if not np.issubdtype(arr.dtype, np.integer):
            raise TypeError(
                f"Identifier '{key}' must be an integer dtype "
                f"(integers cannot be NaN); got {arr.dtype}"
            )
        if arr.ndim != 1:
            raise ValueError(
                f"Identifier '{key}' must be 1-D, got ndim={arr.ndim}"
            )
        if arr.shape[0] != n_rows:
            raise ValueError(
                f"Identifier '{key}' has length {arr.shape[0]} "
                f"but expected {n_rows}"
            )


def validate_values(values: NDArray[np.float32]) -> None:
    """Assert ``values`` are a ``float32`` array with an explicit trailing axis.

    The frame is responsible for coercing input to ``float32`` (accepting e.g.
    ``float64``) and for rejecting object-dtype input before calling this; this
    check confirms the final stored invariants.

    Args:
        values: The frame's value array (first axis = rows; last axis = samples).

    Raises:
        TypeError: ``values`` is not a numpy array or not ``float32``.
        ValueError: ``values`` is object dtype (list-in-cell is banned) or lacks
            an explicit trailing sample axis (``ndim < 2``).
    """
    if not isinstance(values, np.ndarray):
        raise TypeError(
            f"values must be a numpy array, got {type(values).__name__}"
        )
    if values.dtype == np.dtype(object):
        raise ValueError(
            "values must not be object dtype — list-in-cell is banned (README §7)"
        )
    if values.dtype != np.float32:
        raise TypeError(f"values must be float32, got {values.dtype}")
    if values.ndim < 2:
        raise ValueError(
            "values must have an explicit trailing sample axis (ndim >= 2), "
            f"got ndim={values.ndim}"
        )
