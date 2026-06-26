"""Reconciliation production-parity verifier — a standalone drift report (Epic 11).

Two modes, both human-readable:

  * ``--oracle`` (no extra deps): re-run ``views_frames_reconcile`` against the frozen
    views-reporting **torch oracle** fixtures (``tests/fixtures/reconciliation_*.npz``)
    and print a drift report — max absolute / relative error, the per-row sum-to-country
    conservation residual, and zero-preservation — with a PASS/FAIL verdict at the same
    ``rtol=1e-5, atol=1e-6`` the test suite uses. This re-confirms that the canonical
    numpy reconciler still reproduces the torch numbers the cutover was validated against.

  * ``--compare OLD.parquet NEW.parquet`` (needs pandas): align two reconciled forecast
    outputs on their identity columns and report the same drift statistics across the
    shared numeric columns — the *retrospective production-slice check* (compare what the
    old served path produced against what the new ``views_frames_reconcile`` path produces
    on a real slice).

This is a **dev / ops tool**, not run in CI and not part of the package (like
``scripts/gen_reconciliation_*.py``). The Epic 11 cutover already shipped and was verified
by the in-repo gates (the 136-case new-vs-old bit-identity head-to-head + these oracle
parity fixtures); this script makes that evidence re-runnable and gives any *future*
reconciler change — or a belt-and-suspenders production check — a one-command verifier.

Usage:
    uv run python scripts/verify_reconcile_parity.py --oracle
    uv run --with pandas python scripts/verify_reconcile_parity.py \
        --compare old_served.parquet new_served.parquet --keys month_id priogrid_id
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from views_frames import PredictionFrame, SpatialLevel, SpatioTemporalIndex
from views_frames_reconcile import ReconciliationModule, reconcile_proportional

_RTOL = 1e-5
_ATOL = 1e-6
_FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _stats(got: np.ndarray, expected: np.ndarray) -> tuple[float, float, bool]:
    """Return (max abs error, max rel error, allclose) at the suite's rtol/atol."""
    got = np.asarray(got, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    abs_err = np.abs(got - expected)
    rel_err = abs_err / np.maximum(np.abs(expected), _ATOL)
    ok = bool(np.allclose(got, expected, rtol=_RTOL, atol=_ATOL))
    return float(abs_err.max(initial=0.0)), float(rel_err.max(initial=0.0)), ok


def _oracle_leaf() -> bool:
    """Re-run reconcile_proportional against the frozen leaf-parity oracle."""
    data = np.load(_FIX / "reconciliation_parity.npz")
    n = int(data["n_cases"])
    worst_abs = worst_rel = cons = 0.0
    all_ok = zero_ok = True
    for i in range(n):
        grid = data[f"grid_{i}"]
        country = data[f"country_{i}"]
        got = reconcile_proportional(grid, country)
        a, r, ok = _stats(got, data[f"expected_{i}"])
        worst_abs, worst_rel, all_ok = max(worst_abs, a), max(worst_rel, r), all_ok and ok
        # conservation: each active (non-all-zero) draw sums to its country total
        g2, adj = np.atleast_2d(grid), np.atleast_2d(got)
        active = g2.sum(axis=1) > 0
        if active.any():
            tot = np.atleast_1d(country).astype(np.float64).reshape(-1)[active]
            cons = max(cons, float(np.abs(adj.sum(axis=1)[active] - tot).max(initial=0.0)))
        zero_ok = zero_ok and bool(np.all(adj[g2 == 0] == 0))
    print(f"  leaf reconcile_proportional ({n} oracle cases):")
    print(f"    max abs err   = {worst_abs:.3e}    max rel err = {worst_rel:.3e}")
    print(f"    conservation  = {cons:.3e} (worst |sum(adjusted) - country| on active draws)")
    print(f"    zeros preserved = {zero_ok}")
    return all_ok and zero_ok


def _oracle_e2e() -> bool:
    """Re-run ReconciliationModule.reconcile against the frozen end-to-end oracle."""
    data = np.load(_FIX / "reconciliation_e2e_parity.npz")
    targets = [str(t) for t in data["targets"]]
    module = ReconciliationModule(
        np.stack([data["pg_time"], data["pg_unit"]], axis=1), data["pg_country"]
    )
    worst_abs = worst_rel = 0.0
    all_ok = True
    for tgt in targets:
        cm = PredictionFrame(
            np.asarray(data[f"cm__{tgt}"], dtype=np.float32),
            SpatioTemporalIndex(data["cm_time"], data["cm_unit"], SpatialLevel.CM),
        )
        pgm = PredictionFrame(
            np.asarray(data[f"pg__{tgt}"], dtype=np.float32),
            SpatioTemporalIndex(data["pg_time"], data["pg_unit"], SpatialLevel.PGM),
        )
        got = module.reconcile(cm, pgm).values
        a, r, ok = _stats(got, data[f"recon__{tgt}"])
        worst_abs, worst_rel, all_ok = max(worst_abs, a), max(worst_rel, r), all_ok and ok
    print(f"  end-to-end ReconciliationModule ({len(targets)} targets {targets}):")
    print(f"    max abs err = {worst_abs:.3e}    max rel err = {worst_rel:.3e}")
    return all_ok


def run_oracle() -> int:
    """Re-confirm the canonical reconciler still matches the frozen torch oracle."""
    print("Reconciliation oracle parity — views_frames_reconcile vs the frozen")
    print(f"views-reporting torch oracle (rtol={_RTOL:g}, atol={_ATOL:g}):\n")
    ok = _oracle_leaf() and _oracle_e2e()
    print(
        f"\n  VERDICT: {'PASS' if ok else 'FAIL'} — the canonical copy "
        f"{'reproduces' if ok else 'DIVERGES from'} the torch oracle."
    )
    return 0 if ok else 1


def run_compare(old_path: str, new_path: str, keys: list[str]) -> int:
    """Align two reconciled outputs on `keys` and report drift across shared columns."""
    try:
        import pandas as pd
    except ImportError:
        print(
            "--compare needs pandas: `uv run --with pandas python "
            "scripts/verify_reconcile_parity.py --compare ...`",
            file=sys.stderr,
        )
        return 2
    old = pd.read_parquet(old_path)
    new = pd.read_parquet(new_path)
    missing = [k for k in keys if k not in old.columns or k not in new.columns]
    if missing:
        print(f"key column(s) absent from one side: {missing}", file=sys.stderr)
        return 2
    merged = old.merge(new, on=keys, suffixes=("_old", "_new"), how="inner")
    print(
        f"compare: {len(old)} old rows, {len(new)} new rows, "
        f"{len(merged)} matched on {keys}\n"
    )
    cols = sorted(
        c[:-4]
        for c in merged.columns
        if c.endswith("_old")
        and f"{c[:-4]}_new" in merged.columns
        and np.issubdtype(merged[c].dtype, np.number)
    )
    all_ok = True
    for col in cols:
        a, r, ok = _stats(merged[f"{col}_new"].to_numpy(), merged[f"{col}_old"].to_numpy())
        all_ok = all_ok and ok
        flag = "" if ok else "   <-- beyond tolerance"
        print(f"    {col:<28} max abs = {a:.3e}   max rel = {r:.3e}{flag}")
    print(
        f"\n  VERDICT: {'PASS' if all_ok else 'FAIL'} — old vs new reconciled outputs "
        f"{'agree' if all_ok else 'DIVERGE'} within rtol={_RTOL:g}/atol={_ATOL:g}."
    )
    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconciliation parity verifier (Epic 11).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--oracle",
        action="store_true",
        help="re-run the reconciler against the frozen torch-oracle fixtures",
    )
    group.add_argument(
        "--compare",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="compare two reconciled-output parquet files (needs pandas)",
    )
    parser.add_argument(
        "--keys",
        nargs="+",
        default=["month_id", "priogrid_id"],
        help="identity columns to align --compare on (default: month_id priogrid_id)",
    )
    args = parser.parse_args(argv)
    if args.oracle:
        return run_oracle()
    return run_compare(args.compare[0], args.compare[1], args.keys)


if __name__ == "__main__":
    raise SystemExit(main())
