"""🟩 Green: release-metadata guards (packaging).

A public PyPI release must advertise its supported Pythons / development status / topic
via Trove classifiers — their absence was the soft falsification found by `/falsify`
(P3, register C-40). These guard against a silent regression of the published metadata.

`tomllib` is stdlib only on Python 3.11+, so this module is skipped on the 3.10 floor
(the metadata is still asserted by the 3.11/3.12/3.13 CI jobs).
"""

from __future__ import annotations

from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # py3.11+; skipped on the 3.10 floor

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _project() -> dict:
    with _PYPROJECT.open("rb") as f:
        return dict(tomllib.load(f)["project"])


def test_pyproject_declares_pypi_classifiers():
    assert _project().get("classifiers"), (
        "a public PyPI release should declare Trove classifiers (status/Python/topic)"
    )


def test_classifiers_cover_the_supported_python_range():
    # requires-python >= 3.10 and CI tests 3.10-3.13; the classifiers must match.
    classifiers = _project().get("classifiers", [])
    missing = [
        f"Programming Language :: Python :: 3.{m}"
        for m in (10, 11, 12, 13)
        if f"Programming Language :: Python :: 3.{m}" not in classifiers
    ]
    assert not missing, f"classifiers omit tested Python versions: {missing}"
