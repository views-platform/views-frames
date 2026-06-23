"""The constrained-nested HDI tower (ADR-019) — interval estimates over the sample axis.

`hdi_tower` returns, for each requested mass, the highest-density interval read out
of a **fixed canonical tower**: a dense set of shortest intervals built inside-out so
each floor is the shortest interval that *contains* the next-narrower one. Nesting is
therefore guaranteed **by construction** (no post-hoc "move to nest" patch; register
C-33), and because the tower is always built on the same fixed `_CANONICAL_FLOORS`
grid — with requested masses *pinned* to the nearest floor, never inserted — "the 50%
HDI" is identical regardless of which other masses a caller asks for (reproducibility).

The construction is vectorized over the sample axis and runs in row-blocks (register
C-22/C-25): one sort per block, never a whole-grid sorted copy. A raw-count zero
short-circuit (`max(row) <= 1.0` → the whole summary collapses to 0) kills the quiet
cells — the overwhelming majority — cheaply.

Returns numpy arrays aligned to the frame's index (the interval convention, ADR-017);
the caller holds the index. The private engine here (`_dense_tower`, `_tip`, `_pin`,
`_zero_mask`, `_CANONICAL_FLOORS`) is shared by `tower_point`, `bimodality`, and the
single-pass `summarize_tower` bundle.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize._common import ROW_BLOCK, AnyFrame, block_apply

# The fixed canonical mass grid: a 5% body plus a fixed fine high-mass tail so a
# requested 0.99 pins to 0.99 (not 0.95). Built from rounded literals — NOT
# ``np.arange`` (whose float accumulation drifts ~1 ulp across numpy versions and
# would make the grid, and therefore every pinned interval, non-reproducible).
_CANONICAL_FLOORS: Final[NDArray[np.float64]] = np.array(
    [round(0.05 * i, 2) for i in range(1, 19)]  # 0.05 … 0.90
    + [0.92, 0.94, 0.96, 0.97, 0.98, 0.99],  # fixed fine high-mass tail
    dtype=np.float64,
)

# Raw-count zero rule: a row whose every draw is <= this collapses to 0 (the quiet
# cell — no meaningful positive mass). Deliberately a *count* rule, distinct from
# ``map_estimate``'s zero-*mass*-fraction rule, so the two estimators stay independent.
_ZERO_CUTOFF: Final = 1.0


def _ks(sample_count: int) -> NDArray[np.intp]:
    """The per-floor window size ``k = floor(mass * S)`` for every canonical floor."""
    return np.asarray(np.floor(_CANONICAL_FLOORS * sample_count), dtype=np.intp)


def _pin(masses: Sequence[float]) -> NDArray[np.intp]:
    """Index of the nearest canonical floor for each requested mass (ties → lowest).

    Fails loud (ADR-008) on a mass outside ``(0, 1)`` rather than silently pinning a
    nonsense value to the nearest floor and returning a plausible-looking interval.
    """
    m = np.asarray(masses, dtype=np.float64)
    if m.size == 0 or not np.all((m > 0.0) & (m < 1.0)):
        raise ValueError(
            f"masses must each be in the open interval (0, 1); got {masses!r}"
        )
    dist = np.abs(_CANONICAL_FLOORS[None, :] - m[:, None])
    return np.asarray(np.argmin(dist, axis=1), dtype=np.intp)


def _zero_mask(block: NDArray[np.float32]) -> NDArray[np.bool_]:
    """Rows whose maximum draw is at/below the zero cutoff — the quiet cells."""
    return np.asarray(block.max(axis=-1) <= _ZERO_CUTOFF, dtype=np.bool_)


def _shortest(
    srt: NDArray[np.float32], k: int
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Shortest interval holding ``k + 1`` samples, per row of a sorted block.

    For ``k <= 0`` the floor cannot hold two samples (``S`` below the grid's 1/S
    resolution); it degenerates to the per-row median point — the tower-tip seed.
    """
    n = srt.shape[-1]
    if k <= 0:
        v = srt[:, n // 2]
        return v.copy(), v.copy()
    widths = srt[:, k:] - srt[:, : n - k]
    i = np.argmin(widths, axis=-1)
    lo = np.take_along_axis(srt, i[:, None], axis=-1)[:, 0]
    hi = np.take_along_axis(srt, (i + k)[:, None], axis=-1)[:, 0]
    return lo, hi


def _shortest_containing(
    srt: NDArray[np.float32],
    k: int,
    plo: NDArray[np.float32],
    phi: NDArray[np.float32],
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Shortest ``k+1``-sample interval that contains the inner floor ``[plo, phi]``.

    This is what makes the tower nested by construction. ``k <= 0`` inherits the inner
    floor; ``k >= n-1`` is the whole row.
    """
    n = srt.shape[-1]
    if k <= 0:
        return plo.copy(), phi.copy()
    if k >= n - 1:
        return srt[:, 0].copy(), srt[:, -1].copy()
    starts = srt[:, : n - k]
    ends = srt[:, k:]
    ok = (starts <= plo[:, None]) & (ends >= phi[:, None])
    widths = np.where(ok, ends - starts, np.inf)
    i = np.argmin(widths, axis=-1)
    lo = np.take_along_axis(starts, i[:, None], axis=-1)[:, 0]
    hi = np.take_along_axis(ends, i[:, None], axis=-1)[:, 0]
    # Defensive: the construction guarantees an inner floor is itself a sample window,
    # so a wider containing window always exists — but if that invariant is ever
    # broken, expand minimally rather than emit a non-nested floor.
    bad = ~np.isfinite(widths.min(axis=-1))
    if bad.any():  # pragma: no cover - unreachable while inner ⊂ outer holds
        lo = np.where(bad, np.minimum(srt[:, 0], plo), lo)
        hi = np.where(bad, np.maximum(srt[:, -1], phi), hi)
    return lo, hi


def _dense_tower(srt: NDArray[np.float32], ks: NDArray[np.intp]) -> NDArray[np.float32]:
    """Build the full constrained-nested tower over a sorted block → ``(rows, F, 2)``.

    F is the number of canonical floors; each is nested in the next-wider one.
    """
    rows = srt.shape[0]
    out = np.empty((rows, ks.shape[0], 2), dtype=np.float32)
    plo: NDArray[np.float32] | None = None
    phi: NDArray[np.float32] | None = None
    for j, k in enumerate(ks):
        if plo is None or phi is None:
            lo, hi = _shortest(srt, int(k))
        else:
            lo, hi = _shortest_containing(srt, int(k), plo, phi)
        out[:, j, 0] = lo
        out[:, j, 1] = hi
        plo, phi = lo, hi
    return out


def _tip(srt: NDArray[np.float32], k0: int) -> NDArray[np.float32]:
    """The tower tip: the median of the narrowest floor's ``k0 + 1`` samples, per row.

    For ``k0 <= 0`` the floor is the median point itself.
    """
    n = srt.shape[-1]
    if k0 <= 0:
        return srt[:, n // 2].copy()
    widths = srt[:, k0:] - srt[:, : n - k0]
    i = np.argmin(widths, axis=-1)
    lo_mid = i + (k0 // 2)
    hi_mid = i + ((k0 + 1) // 2)
    a = np.take_along_axis(srt, lo_mid[:, None], axis=-1)[:, 0]
    b = np.take_along_axis(srt, hi_mid[:, None], axis=-1)[:, 0]
    return np.asarray((a + b) * 0.5, dtype=np.float32)


def hdi_tower(
    frame: AnyFrame,
    masses: Sequence[float] = (0.5, 0.9, 0.99),
    *,
    block_rows: int = ROW_BLOCK,
) -> NDArray[np.float32]:
    """Per-row constrained-nested HDIs at the requested ``masses`` → ``(N, …, M, 2)``.

    Each requested mass is pinned to the nearest fixed canonical floor; the interval is
    read out of the full canonical tower (built once per block). Nested by construction
    and reproducible (a mass's interval is independent of the other requested masses).
    Quiet rows (``max <= 1``) collapse to ``(0, 0)``. Aligned to ``frame.index``.
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    ks = _ks(s)
    pin = _pin(masses)
    flat = np.ascontiguousarray(values).reshape(-1, s)

    def _block(block: NDArray[np.float32]) -> NDArray[np.float32]:
        srt = np.sort(block, axis=-1)
        sel = _dense_tower(srt, ks)[:, pin, :]
        sel[_zero_mask(block)] = 0.0
        return sel

    out = block_apply(flat, block_rows, _block)
    return np.asarray(out, dtype=np.float32).reshape(*lead, pin.shape[0], 2)
