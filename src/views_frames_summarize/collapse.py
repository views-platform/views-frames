"""`collapse` — the generic sample-axis fold (a point estimate over the samples).

The statistic is **injected** by the caller (e.g. ``np.mean``, ``np.median``); this
package owns the *mechanism* (reduce the trailing axis, rebuild a valid frame), not
a menu of statistics. This is the operation that was removed from the leaf (ADR-017).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from views_frames_summarize._common import AnyFrame, rebuild

# A reducer is applied as ``reducer(values, axis=-1)`` and reduces the sample axis.
Reducer = Callable[..., Any]


def collapse(frame: AnyFrame, reducer: Reducer) -> AnyFrame:
    """Reduce the trailing sample axis with ``reducer``, returning a new frame.

    ``reducer`` is called as ``reducer(frame.values, axis=-1)`` — any numpy-style
    reduction works (``np.mean``, ``np.median``, ``np.max`` …). The result is a
    point estimate with an explicit trailing axis of size 1 (e.g. `(N, S) → (N, 1)`,
    `(N, F, S) → (N, F, 1)`).

    Args:
        frame: A frame with a trailing sample axis.
        reducer: A callable taking ``(values, axis=-1)`` and reducing that axis.

    Returns:
        A new frame of the same type with the sample axis collapsed to size 1.
    """
    reduced = np.asarray(reducer(frame.values, axis=-1), dtype=np.float32)
    return rebuild(frame, reduced[..., np.newaxis])
