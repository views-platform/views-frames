"""Generate the cross-version parquet fixtures (register C-79).

Every arrow IO test writes a file and reads it back **in the same process, at the same
version**. That proves the codec is self-consistent. It cannot prove the property that
matters for a data-contract package: **that a file written by an earlier release still
loads.** The consumers on that path (views-postprocessing, views-faoapi #100) hold archived
shards written by earlier releases.

This script writes the fixtures **using the `save` function extracted from the `v1.8.0`
tag**, loaded out of git as its own module — not using today's `save`. The distinction is
the point: a fixture produced by current code only proves the codec round-trips itself,
which `tests/test_io.py` already covers. Producing it from released code is what makes
`test_v1_8_0_prediction_parquet_still_loads` and `test_v1_8_0_feature_parquet_still_loads`
cross-version tests rather than a second round-trip.

`v1.8.0` is chosen because it **predates v1.10.1**, which added three `ValueError` paths to
`load` rejecting row orders that violate the written wire contract (register C-72). Those
rules were derived from what `save` writes *today*; the fixture is the evidence that a file
written before them satisfies them.

`save` is byte-identical from `v1.8.0` to `HEAD` (verified by extracting the function from
both and diffing), so the fixtures are also what any release since v1.8.0 would produce.
**That equivalence is exactly what stops holding the moment someone edits `save`** — which
is when this script must be re-run against the last release that still has the old writer,
before the change lands.

Usage::

    uv run --extra arrow python scripts/gen_arrow_crossversion_fixture.py

Writes `tests/fixtures/arrow_v1_8_0_prediction.parquet` and
`tests/fixtures/arrow_v1_8_0_feature.parquet`. Regenerating is not routine: if the files
change, the cross-version test stops testing what it says it tests.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"
WRITER_TAG = "v1.8.0"


def _load_released(tag: str, relpath: str) -> types.ModuleType:
    """Import a module as it existed at `tag`, without touching the working tree."""
    source = subprocess.run(
        ["git", "show", f"{tag}:{relpath}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    name = relpath.rsplit("/", 1)[-1].removesuffix(".py")
    module = types.ModuleType(f"_{name}_{tag.replace('.', '_')}")
    module.__file__ = f"<{tag}:{relpath}>"
    exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102
    return module


def main() -> int:
    if importlib.util.find_spec("pyarrow") is None:
        raise SystemExit("pyarrow is required: uv run --extra arrow python scripts/...")
    arrow = _load_released(WRITER_TAG, "src/views_frames/io/arrow.py")
    npz = _load_released(WRITER_TAG, "src/views_frames/io/npz.py")
    FIXTURES.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(20260818)
    time = np.array([1, 1, 2, 2], dtype=np.int64)
    unit = np.array([10, 11, 10, 11], dtype=np.int64)

    # 2-D (N, S): a PredictionFrame's state.
    arrow.save(
        FIXTURES / "arrow_v1_8_0_prediction.parquet",
        values=rng.random((4, 3), dtype=np.float32),
        time=time,
        unit=unit,
        level="pgm",
        metadata={"model": "fixture", "run_id": "c79", "timestamp": 202608, "seed": 7},
    )

    # 3-D (N, F, S): a FeatureFrame's state, with feature_names.
    arrow.save(
        FIXTURES / "arrow_v1_8_0_feature.parquet",
        values=rng.random((4, 2, 3), dtype=np.float32),
        time=time,
        unit=unit,
        level="pgm",
        metadata={"model": "fixture", "data_version": "c79", "seed": 11},
        feature_names=["ged_sb", "pop"],
    )

    # npz — the format `PredictionFrame.save`/`load` actually use. A consumer reviving an
    # archived frame goes through `npz.load` -> `SpatioTemporalIndex(...)` ->
    # `FrameMetadata.from_dict`, so a construction-time tightening would reject old files
    # with nothing to catch it. `npz.save` is byte-identical since v1.8.0 too.
    npz.save(
        FIXTURES / "npz_v1_8_0_prediction",
        values=rng.random((4, 3), dtype=np.float32),
        time=time,
        unit=unit,
        level="pgm",
        metadata={
            "model": "fixture",
            "run_id": "c79-npz",
            "timestamp": 202608,
            "seed": 3,
        },
    )

    for name in (
        "arrow_v1_8_0_prediction.parquet",
        "arrow_v1_8_0_feature.parquet",
    ):
        size = (FIXTURES / name).stat().st_size
        print(f"wrote tests/fixtures/{name} ({size} bytes, writer {WRITER_TAG})")
    for f in sorted((FIXTURES / "npz_v1_8_0_prediction").iterdir()):
        print(
            f"wrote tests/fixtures/npz_v1_8_0_prediction/{f.name} ({f.stat().st_size} bytes, writer {WRITER_TAG})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
