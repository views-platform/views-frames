"""Physical-architecture tree check — does §2 of the standard still match `src/`?

`docs/standards/physical_architecture_standard.md` §2 holds the repository's authoritative
directory tree. It is the document a contributor consults to answer "where does this file
go", and ADR-007 expects agents to read it. Being authoritative makes it perishable: it sat
unrevised from before the package was built until 2026-08-17, by which point it showed one
of the three shipped packages, omitted `metadata.py` / `_typing.py` / `conformance/`, and
listed two files that were never written (register C-84).

This script parses the fenced tree out of §2 and diffs it against `src/**/*.py` in **both**
directions — a module missing from the tree, and a module named in the tree that does not
exist. Both directions matter: the first is how the tree goes stale as the package grows,
the second is how it acquired two phantom frames.

Run it after adding, moving or removing a module::

    uv run python scripts/check_arch_tree.py

Exits 0 when the tree matches, 1 with a report when it does not.

**Not wired into CI.** `docs/validate_docs.sh` is the documentation gate and is bash-and-grep
by design — its CI job installs no Python on purpose. Whether this check belongs there, and
how to express it without Python, is issue #246 (register C-85). Until then this is a
standalone tool, like `verify_reconcile_parity.py` beside it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STANDARD = REPO_ROOT / "docs" / "standards" / "physical_architecture_standard.md"
FENCE_START = "```\nsrc/views_frames/"
PACKAGES = (
    "src/views_frames/",
    "src/views_frames_summarize/",
    "src/views_frames_reconcile/",
)


def _tree_block(document: str) -> str:
    """Return the fenced §2 tree, or raise if the fence has moved."""
    try:
        start = document.index(FENCE_START)
    except ValueError as exc:  # pragma: no cover - guards a doc restructure
        raise SystemExit(
            f"could not find the §2 tree fence in {STANDARD.name}; "
            "if the document was restructured, update FENCE_START"
        ) from exc
    return document[start : document.index("```", start + 3)]


def main() -> int:
    """Diff the standard's §2 tree against `src/` and report both directions."""
    tree = _tree_block(STANDARD.read_text(encoding="utf-8"))
    modules = sorted(
        str(p.relative_to(REPO_ROOT / "src")) for p in (REPO_ROOT / "src").rglob("*.py")
    )

    missing = [m for m in modules if m.split("/")[-1] not in tree]
    named = set(re.findall(r"([a-z_]+\.py)", tree))
    ghosts = sorted(
        n for n in named if not any(m.endswith("/" + n) or m == n for m in modules)
    )
    absent_packages = [p for p in PACKAGES if p not in tree]

    print(f"source modules: {len(modules)}")
    print(f"missing from tree: {missing or 'none'}")
    print(f"in tree but absent from src/: {ghosts or 'none'}")
    print(f"packages absent from tree: {absent_packages or 'none'}")

    if missing or ghosts or absent_packages:
        print(
            "\nFAILED: docs/standards/physical_architecture_standard.md §2 is out of date."
        )
        return 1
    print("\nPASSED: the tree matches src/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
