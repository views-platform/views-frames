"""The constrained-nested HDI tower (ADR-019) — interval estimates over the sample axis.

`hdi_tower` returns, for each requested mass, the highest-density interval read out of
a **fixed canonical tower** built **outside-in**: the widest floor is the shortest
interval holding its mass, then each *narrower* floor is the shortest interval
**contained in** its wider parent. Nesting is guaranteed **by construction** (register
C-33), and — crucially — the build is **robust to minority duplicated draws** (register
C-44): a lonely outlier (a couple of exact zeros, a stray pair) is shed by the
well-determined wide floors, and the containment constraint forbids any narrower floor
from re-selecting a window that pokes outside its parent. Because the tower is always
built on the same fixed `_CANONICAL_FLOORS` grid — requested masses are *pinned* to the
nearest floor, never inserted — "the 50% HDI" is identical regardless of which other
masses a caller asks for (reproducibility).

The construction is vectorized over the sample axis and runs in row-blocks (register
C-22/C-25): one sort per block, never a whole-grid sorted copy. A raw-count zero
short-circuit (`max(row) <= zero_cutoff` → the whole summary collapses to 0) kills the
quiet cells cheaply.

All tunables (the grid, zero cutoff, row-block size) come from `config` with **no silent
defaults** (ADR-009). The private engine (`_dense_tower`, `_median_in`, `_pin`,
`_zero_mask`, `_CANONICAL_FLOORS`) is shared by `tower_point`, `bimodality`, and the
single-pass `summarize_tower` bundle.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from views_frames_summarize import config
from views_frames_summarize._common import AnyFrame, block_apply

# The fixed canonical mass grid + the zero cutoff, sourced from the single config (no
# silent defaults — ADR-009). Kept as module names so the engine and its siblings share
# one source of truth.
_CANONICAL_FLOORS: Final[NDArray[np.float64]] = config.canonical_floors()
_ZERO_CUTOFF: Final[float] = float(config.get("zero_cutoff"))


def _ks(sample_count: int) -> NDArray[np.intp]:
    """The per-floor window size ``k = floor(mass * S)`` for every canonical floor."""
    return np.asarray(np.floor(_CANONICAL_FLOORS * sample_count), dtype=np.intp)


def _pin(masses: Sequence[float]) -> NDArray[np.intp]:
    """Index of the nearest canonical floor for each requested mass.

    Deterministic: ``argmin`` of the distance, breaking ties on the lowest index. A
    mass at the midpoint between two floors (e.g. ``0.075`` between ``0.05`` and
    ``0.10``) therefore pins **down** to the lower floor — unambiguous and
    reproducible. Fails loud (ADR-008) on a mass outside ``(0, 1)`` rather than silently
    pinning a nonsense value to the nearest floor and returning a plausible interval.
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


def _in_range_span(
    srt: NDArray[np.float32], lo: NDArray[np.float32], hi: NDArray[np.float32]
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """``(first, count)`` of the contiguous run of samples within ``[lo, hi]`` per row.

    ``lo``/``hi`` are sample values (a floor's bounds), so the in-range samples form a
    contiguous run; at least one is always in range (the floor was built from samples).
    """
    inside = (srt >= lo[:, None]) & (srt <= hi[:, None])
    first = np.argmax(inside, axis=1)  # index of the first in-range sample
    count = inside.sum(axis=1)
    return np.asarray(first, dtype=np.intp), np.asarray(count, dtype=np.intp)


def _median_in(
    srt: NDArray[np.float32], lo: NDArray[np.float32], hi: NDArray[np.float32]
) -> NDArray[np.float32]:
    """Per-row **median value** of the samples within ``[lo, hi]`` (averaged for an even
    count). Used for the *tip point estimate*, which may fall between two samples.
    """
    first, count = _in_range_span(srt, lo, hi)
    a = first + (count - 1) // 2
    b = first + count // 2
    va = np.take_along_axis(srt, a[:, None], axis=1)[:, 0]
    vb = np.take_along_axis(srt, b[:, None], axis=1)[:, 0]
    return np.asarray((va + vb) * 0.5, dtype=np.float32)


def _mid_sample_in(
    srt: NDArray[np.float32], lo: NDArray[np.float32], hi: NDArray[np.float32]
) -> NDArray[np.float32]:
    """Per-row **middle sample** (a real draw) of the run within ``[lo, hi]``.

    Used for a ``k <= 0`` *floor*, whose bounds must be actual samples so that the next
    narrower floor's containment (and `_median_in`) stays well-defined — an averaged
    median could be a value no draw equals, breaking the contiguous-run assumption.
    """
    first, count = _in_range_span(srt, lo, hi)
    mid = first + (count - 1) // 2
    return np.asarray(
        np.take_along_axis(srt, mid[:, None], axis=1)[:, 0], dtype=np.float32
    )


def _shortest_seed(
    srt: NDArray[np.float32], k: int
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """The widest floor (no parent): the shortest interval holding ``k + 1`` samples.

    Leftmost tie-break (``np.argmin`` returns the first). ``k <= 0`` degenerates to the
    per-row median point; ``k >= n-1`` is the whole row (the widest floor of a small S).
    """
    n = srt.shape[-1]
    if k <= 0:
        v = srt[:, n // 2]
        return v.copy(), v.copy()
    if k >= n - 1:
        return srt[:, 0].copy(), srt[:, -1].copy()
    widths = srt[:, k:] - srt[:, : n - k]
    i = np.argmin(widths, axis=-1)
    lo = np.take_along_axis(srt, i[:, None], axis=-1)[:, 0]
    hi = np.take_along_axis(srt, (i + k)[:, None], axis=-1)[:, 0]
    return lo, hi


def _shortest_contained_in(
    srt: NDArray[np.float32],
    k: int,
    parent_lo: NDArray[np.float32],
    parent_hi: NDArray[np.float32],
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Shortest ``k+1``-sample window ``[lo, hi]`` with ``parent_lo <= lo`` and
    ``hi <= parent_hi`` — the outside-in nesting step.

    This is what makes the tower nested *and* robust to minority duplicates: a window
    straddling an outlier cannot fit in a parent that already shed it. Always feasible
    — the parent's own first ``k+1`` samples are a candidate (the parent holds at least
    ``k+1`` samples, since floors are non-decreasing in mass and built widest-first).
    ``k <= 0`` collapses to the in-parent median point.
    """
    n = srt.shape[-1]
    if k <= 0:
        v = _mid_sample_in(srt, parent_lo, parent_hi)
        return v, v
    starts = srt[:, : n - k]
    ends = srt[:, k:]
    inside = (starts >= parent_lo[:, None]) & (ends <= parent_hi[:, None])
    widths = np.where(inside, ends - starts, np.inf)
    i = np.argmin(widths, axis=-1)
    lo = np.take_along_axis(starts, i[:, None], axis=-1)[:, 0]
    hi = np.take_along_axis(ends, i[:, None], axis=-1)[:, 0]
    return lo, hi


def _dense_tower(srt: NDArray[np.float32], ks: NDArray[np.intp]) -> NDArray[np.float32]:
    """Build the full constrained-nested tower over a sorted block → ``(rows, F, 2)``.

    Built **outside-in**: the widest floor (last index) first, then each narrower floor
    contained in its wider parent. Each floor is written at its natural ascending index,
    so the output layout, the ``[:, pin, :]`` readout, and reproducibility are unchanged
    from the published contract — only the *fill order* runs widest→narrowest.
    """
    rows = srt.shape[0]
    f = ks.shape[0]
    out = np.empty((rows, f, 2), dtype=np.float32)
    plo: NDArray[np.float32] | None = None
    phi: NDArray[np.float32] | None = None
    for j in range(f - 1, -1, -1):  # widest → narrowest
        k = int(ks[j])
        if plo is None or phi is None:
            lo, hi = _shortest_seed(srt, k)
        else:
            lo, hi = _shortest_contained_in(srt, k, plo, phi)
        out[:, j, 0] = lo
        out[:, j, 1] = hi
        plo, phi = lo, hi
    return out


def _tip_floor_index(sample_count: int) -> int:
    """The canonical-grid index whose mass is nearest ``config['tip_mass']``."""
    tip_mass = float(config.get("tip_mass"))
    return int(np.argmin(np.abs(_CANONICAL_FLOORS - tip_mass)))


def hdi_tower(
    frame: AnyFrame,
    masses: Sequence[float] = (0.5, 0.9, 0.99),
) -> NDArray[np.float32]:
    """Per-row constrained-nested HDIs at the requested ``masses`` → ``(N, …, M, 2)``.

    Each requested mass is pinned to the nearest fixed canonical floor; the interval is
    read out of the full canonical tower (built once per block, outside-in). Nested by
    construction, robust to minority duplicates, and reproducible (a mass's interval is
    independent of the other requested masses). Quiet rows (``max <= zero_cutoff``)
    collapse to ``(0, 0)``. Aligned to ``frame.index``. Tunables come from ``config``.
    """
    values = frame.values
    lead = values.shape[:-1]
    s = values.shape[-1]
    ks = _ks(s)
    pin = _pin(masses)
    block_rows = int(config.get("row_block"))
    flat = np.ascontiguousarray(values).reshape(-1, s)

    def _block(block: NDArray[np.float32]) -> NDArray[np.float32]:
        srt = np.sort(block, axis=-1)
        sel = _dense_tower(srt, ks)[:, pin, :]
        sel[_zero_mask(block)] = 0.0
        return sel

    out = block_apply(flat, block_rows, _block)
    return np.asarray(out, dtype=np.float32).reshape(*lead, pin.shape[0], 2)
