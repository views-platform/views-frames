"""Import-boundary + physical-architecture enforcement (ADR-002, README §3.1/§6).

The executable form of the leaf's defining constraints:

- The core imports **no** ``pandas``/``polars``/``geopandas``/``wandb``/``viewser``/
  ``torch`` and **no** other ``views_*`` package. ``pyarrow`` is allowed **only**
  under ``io/`` (an optional serialization extra).
- One concept per file: at most one public class per module.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "views_frames"

FORBIDDEN = {"pandas", "polars", "geopandas", "wandb", "viewser", "torch"}


def _top_level_imports(path: Path) -> set[str]:
    """Return the set of top-level module names imported by ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_core_has_no_forbidden_imports() -> None:
    """No core module imports a forbidden external or a foreign ``views_*`` package."""
    violations: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        under_io = "io" in py.relative_to(SRC).parts[:-1]
        for mod in _top_level_imports(py):
            forbidden = mod in FORBIDDEN
            foreign_views = mod.startswith("views_") and mod != "views_frames"
            arrow_outside_io = mod == "pyarrow" and not under_io
            if forbidden or foreign_views or arrow_outside_io:
                violations.append(f"{py.relative_to(SRC)} imports '{mod}'")
    assert not violations, "forbidden imports in the core:\n" + "\n".join(violations)


def test_one_concept_per_file() -> None:
    """Every module (except __init__ and protocols) defines at most one public class."""
    exempt = {"__init__.py", "protocols.py"}
    offenders: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        if py.name in exempt:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        public = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
        ]
        if len(public) > 1:
            offenders.append(f"{py.relative_to(SRC)}: {public}")
    detail = "\n".join(offenders)
    assert not offenders, f"more than one public class per file:\n{detail}"
