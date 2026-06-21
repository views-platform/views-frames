"""Internal type aliases for the leaf's array surface (register C-19).

`NDArray[np.integer]` is a generic with an unbound parameter: under
``mypy --strict`` (``disallow_any_generics``) it is a ``[type-arg]`` error at the
declared numpy floor (``numpy==1.26.4``), even though newer stubs let it slide.
Parameterising once here — ``np.integer[Any]`` — keeps every call site green at
the floor and gives the integer identifier arrays a single, named contract.

These are private (underscore module): the public surface is the frames, not the
array aliases.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

# Integer identifier arrays (``time``, ``unit``): any width, fixed to integers.
IntArray = NDArray[np.integer[Any]]

# Float32 value arrays: the leaf's canonical value dtype (ADR-009).
Float32Array = NDArray[np.float32]
