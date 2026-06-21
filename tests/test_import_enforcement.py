"""Import-boundary + physical-architecture enforcement (ADR-002/017, README §3.1/§6).

The executable form of the package dependency DAG:

- ``views_frames`` (the leaf) imports **no** ``pandas``/``polars``/``geopandas``/
  ``wandb``/``viewser``/``torch`` and **no** other ``views_*`` package (so it never
  imports ``views_frames_summarize``). ``pyarrow`` is allowed **only** under ``io/``.
- ``views_frames_summarize`` may import only ``views_frames`` (+ numpy / stdlib);
  never the reverse, never a foreign ``views_*``, never pandas et al.
- One concept per file: at most one public class per module.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

FORBIDDEN = {"pandas", "polars", "geopandas", "wandb", "viewser", "torch"}

# Per-package allowed *internal* (views_*) imports. A package may always import itself.
ALLOWED_INTERNAL: dict[str, set[str]] = {
    "views_frames": set(),
    "views_frames_summarize": {"views_frames"},
}


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


def test_package_dependency_dag() -> None:
    """Each package respects the import DAG; the leaf imports nothing forbidden."""
    violations: list[str] = []
    for package, allowed in ALLOWED_INTERNAL.items():
        pkg_dir = SRC / package
        for py in sorted(pkg_dir.rglob("*.py")):
            under_io = "io" in py.relative_to(pkg_dir).parts[:-1]
            for mod in _top_level_imports(py):
                forbidden = mod in FORBIDDEN
                arrow_outside_io = mod == "pyarrow" and not under_io
                foreign_views = (
                    mod.startswith("views_")
                    and mod != package
                    and mod not in allowed
                )
                if forbidden or arrow_outside_io or foreign_views:
                    rel = py.relative_to(SRC)
                    violations.append(f"{rel} imports '{mod}' (package: {package})")
    assert not violations, "import-DAG violations:\n" + "\n".join(violations)


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
