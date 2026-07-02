"""Regression pins from the falsification audit 2026-07-02 (four-axis audit, Phase 4).

Each test pins a falsification of the safety claim found (and since fixed) by the
audit — written first as failing stubs, turned green by the fixes:

  F1 (HARD) — reconcile silently violated sum-to-country for tiny nonzero draw sums
      (the `+ 1e-8` denominator epsilon; replaced by an explicit all-zero guard).
  F3 (soft) — the published conformance suites were a silent no-op under `python -O`
      (bare asserts; now guarded by `_require_assertions`, which refuses to run).
  F4 (soft) — empty-index `searchsorted` died with an obscure IndexError
      (the `np.clip(pos, 0, -1)` corner; now returns all -1, the not-found value).
  F8 (soft) — a negative country total silently clamped to zero, breaking
      conservation (now raises ValueError).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import numpy as np

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex


def _pair(grid_draws):
    """A 2-cell pgm frame + 1-country cm frame (total 100) + mapping."""
    t = np.array([1, 1], dtype=np.int64)
    u = np.array([100, 101], dtype=np.int64)
    mk = np.array([[1, 100], [1, 101]], dtype=np.int64)
    mv = np.array([7, 7], dtype=np.int64)
    pg_idx = SpatioTemporalIndex(t, u, SpatialLevel.PGM)
    cm_idx = SpatioTemporalIndex(
        np.array([1], dtype=np.int64), np.array([7], dtype=np.int64), SpatialLevel.CM
    )
    pgm = PredictionFrame(np.asarray(grid_draws, dtype=np.float32), pg_idx)
    cm = PredictionFrame(np.array([[100.0]], dtype=np.float32), cm_idx)
    return cm, pgm, mk, mv


class TestF1HardEpsilonRegion:
    """F1 (HARD): tiny-but-nonzero draws are 'active' per the conformance law's own
    definition (in_sum != 0), yet reconcile's `sum_nonzero + _EPS` denominator
    (formerly proportional.py:74) silently deflated the scale factor — at grid-sum
    1e-8 the reconciled sum was 50 instead of 100. Fixed: exact division behind an
    explicit all-zero guard; conservation now holds for any nonzero sum."""

    def test_own_conformance_law_holds_on_tiny_nonzero_draws(self):
        from views_frames_reconcile.conformance import assert_reconcile_contract

        cm, pgm, mk, mv = _pair([[6e-9], [4e-9]])
        # Green post-fix: the sum-to-country law holds on tiny nonzero draws.
        assert_reconcile_contract(cm, pgm, mk, mv)

    def test_conservation_relative_error_within_documented_tolerance(self):
        from views_frames_reconcile import ReconciliationModule

        cm, pgm, mk, mv = _pair([[6e-6], [4e-6]])  # grid sum 1e-5 — still violating
        out = ReconciliationModule(mk, mv).reconcile(cm, pgm)
        rel = abs(float(out.values.sum()) - 100.0) / 100.0
        # Green post-fix: exact division conserves within the §3 rtol.
        assert rel <= 1e-4, f"silent conservation violation: rel_err={rel:.4%}"


class TestF3SoftConformanceUnderO:
    """F3 (soft): the published conformance suites are bare `assert`s — under
    `python -O` a float64 non-conformer with working save/load PASSED the envelope.
    Fixed: `_require_assertions()` makes the suite refuse to run under -O (exit 1
    here comes from that RuntimeError — the point is it can no longer silently pass)."""

    def test_envelope_rejects_nonconformer_even_under_optimized_bytecode(self):
        code = textwrap.dedent("""
            import numpy as np, pathlib, sys
            class Subtle:
                def __init__(self, values):
                    self.values = values; self.n_rows = values.shape[0]
                    self.identifiers = {"time": np.array([1,2]), "unit": np.array([10,20])}
                def save(self, d): np.save(pathlib.Path(d)/"v.npy", self.values)
                @classmethod
                def load(cls, d, mmap=False): return cls(np.load(pathlib.Path(d)/"v.npy"))
            from views_frames.conformance import assert_frame_envelope
            try:
                assert_frame_envelope(Subtle(np.ones((2,1), dtype=np.float64)))
                sys.exit(0)   # passed: the envelope had no teeth
            except AssertionError:
                sys.exit(1)   # rejected: teeth present
        """)
        r = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True)
        # exit 1 = rejected OR refused-to-run; exit 0 would mean a silent pass.
        assert r.returncode == 1, "conformance envelope is a no-op under python -O"


class TestF4SoftEmptyIndexSearchsorted:
    """F4 (soft): searchsorted from an EMPTY index against a non-empty one raises an
    obscure IndexError (the np.clip(pos, 0, -1) corner, index.py:140) instead of a
    clean result/-1s or a named ValueError. Fixed: returns all -1 (not-found)."""

    def test_empty_index_searchsorted_is_clean(self):
        empty = SpatioTemporalIndex(
            np.array([], dtype=np.int64), np.array([], dtype=np.int64), SpatialLevel.PGM
        )
        full = SpatioTemporalIndex(
            np.array([1, 2], dtype=np.int64), np.array([10, 20], dtype=np.int64),
            SpatialLevel.PGM,
        )
        # Green post-fix: all -1 (the not-found value), matching searchsorted's
        # documented missing-row semantics.
        try:
            pos = empty.searchsorted(full)
        except ValueError:
            return  # a clean, documented raise is acceptable
        assert (np.asarray(pos) == -1).all()


class TestF8SoftNegativeCountryTotal:
    """F8 (soft): a negative country total is neither rejected nor conserved — the
    non-negativity clamp silently mapped everything to 0. Fixed: raises ValueError."""

    def test_negative_country_total_rejected_or_conserved(self):
        from views_frames_reconcile.proportional import reconcile_proportional

        grid = np.array([3.0, 7.0], dtype=np.float32)
        # Green post-fix: raises ValueError (upstream nonsense rejected loudly).
        try:
            out = reconcile_proportional(grid, -50.0)
        except ValueError:
            return
        assert np.isclose(float(np.asarray(out).sum()), -50.0)
