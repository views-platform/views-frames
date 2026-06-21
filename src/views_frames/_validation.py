"""Shared construction-time invariant checks (ADR-008, ADR-009).

Fail loud at construction. The guarantee is **structural, not temporal**: the
leaf validates integer dtype / length-N / no-NaN, but ``time`` is an opaque
integer — epoch, range, and monotonicity are a producer concern (register C-11).

STUB — implementation lands in Epic 2.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def validate_identifiers(
    identifiers: dict[str, NDArray[np.integer]], n_rows: int
) -> None:
    """Assert identifiers are integer dtype, length ``n_rows``, and complete (no NaN).

    Raises:
        ValueError: if any identifier array violates a structural invariant.
        TypeError: if any identifier array is not an integer dtype.
    """
    raise NotImplementedError(
        "views-frames is a stub skeleton (Epic 1); validation lands in Epic 2"
    )


def validate_values(values: NDArray[np.float32]) -> None:
    """Assert ``values`` are contiguous ``float32`` with an explicit trailing axis.

    Raises:
        TypeError: if ``values`` are not ``float32``.
        ValueError: if ``values`` are non-contiguous or have object dtype.
    """
    raise NotImplementedError(
        "views-frames is a stub skeleton (Epic 1); validation lands in Epic 2"
    )
