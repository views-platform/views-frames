"""Eval entrypoint (IMMUTABLE) — the autoresearch `eval_command`.

Runs the sandbox estimator (`estimator.summarize`) on the fixed cached battery,
computes the tower-quality metric, and prints:

    score: <scalar>
    components: mass_err=.. excess_w=.. instab=.. nesting_viol=..

then the same line for each incumbent baseline (for comparison). The loop greps
the first `score:` line. Deterministic: fixed battery + seeded stability bootstrap.

Run:  uv run --with scipy python research/map_hdi/run_eval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from benchmark import baselines, battery, metric  # noqa: E402

MASSES = (0.10, 0.50, 0.90)
N_BOOT = 3
BOOT_SEED = 7


def _instability(fn, observed, ref_sorted, original_tower) -> float:
    """Mean normalised movement of tower endpoints under a bootstrap resample."""
    scale = float(np.subtract(*np.quantile(ref_sorted, [0.75, 0.25]))) + 1e-9
    rng = np.random.default_rng(BOOT_SEED)
    moves = []
    for _ in range(N_BOOT):
        boot = rng.choice(observed, size=observed.size, replace=True)
        t = fn(boot, MASSES)["tower"]
        d = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(t, original_tower))
        moves.append(d / (2 * len(MASSES) * scale))
    return float(np.mean(moves))


def evaluate(fn) -> tuple[float, dict]:
    observed, reference, _meta = battery.load()
    per_cell = []
    for obs, ref in zip(observed, reference):
        obs = np.asarray(obs, dtype=float)
        ref = np.asarray(ref, dtype=float)
        try:
            res = fn(obs, MASSES)
            nested, mass_err, excess_w = metric.cell_components(res["tower"], ref, MASSES)
            instab = _instability(fn, obs, ref, res["tower"])
        except Exception:  # a broken estimator is infeasible, not a hard crash
            nested, mass_err, excess_w, instab = False, 9.9, 9.9, 9.9
        per_cell.append(
            {"nested": nested, "mass_err": mass_err, "excess_w": excess_w, "instab": instab}
        )
    return metric.aggregate(per_cell)


def _fmt(name: str, score: float, comp: dict) -> str:
    c = comp
    return (
        f"{name}\nscore: {score:.6f}\n"
        f"components: mass_err={c['mass_err']:.4f} excess_w={c['excess_w']:.4f} "
        f"instab={c['instab']:.4f} nesting_viol={c['nesting_viol']}"
    )


def main() -> None:
    import estimator  # the sandbox

    score, comp = evaluate(estimator.summarize)
    # the loop greps the FIRST `score:` line — keep the candidate first.
    print(_fmt("[candidate] estimator.summarize", score, comp))
    print("\n--- baselines (the bar to beat) ---")
    for name, fn in baselines.BASELINES.items():
        bscore, bcomp = evaluate(fn)
        print(_fmt(f"[baseline] {name}", bscore, bcomp))


if __name__ == "__main__":
    main()
