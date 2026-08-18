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

# Every document carrying an authoritative tree, and the line its fence opens on. There
# are two: the standard's §2 and README's layout section. The README one was stale for
# months after the standard's was fixed, because the check only knew about one of them
# (register C-86) — so the list is the thing to extend, not the logic.
TREES: tuple[tuple[str, str], ...] = (
    ("docs/standards/physical_architecture_standard.md", "```\nsrc/views_frames/"),
    ("README.md", "views-frames/\n"),
)
PACKAGES = (
    "src/views_frames/",
    "src/views_frames_summarize/",
    "src/views_frames_reconcile/",
)


def _tree_block(document: str, fence: str, name: str) -> str:
    """Return the fenced tree, or exit if the fence has moved."""
    try:
        start = document.index(fence)
    except ValueError as exc:  # pragma: no cover - guards a doc restructure
        raise SystemExit(
            f"could not find the tree fence in {name}; if the document was "
            "restructured, update TREES"
        ) from exc
    return document[start : document.index("```", start + 3)]


def _package_blocks(tree: str) -> dict[str, str]:
    """Split the tree into one text block per package.

    A bare basename test is not enough: `conformance.py` exists in two packages and
    `__init__.py` in five, so a single mention anywhere in the tree would satisfy all of
    them — deleting `views_frames_reconcile/conformance.py` from the tree left the check
    green. Each module is therefore looked up only within its own package's block.
    """
    blocks: dict[str, str] = {}
    for i, pkg in enumerate(PACKAGES):
        start = tree.index(pkg)
        ends = [tree.index(p) for p in PACKAGES[i + 1 :] if p in tree]
        blocks[pkg.removeprefix("src/").rstrip("/")] = tree[
            start : min(ends, default=len(tree))
        ]
    return blocks


def _check_one(relpath: str, fence: str, modules: list[str]) -> int:
    """Diff one document's tree against `modules`; return the error count."""
    document = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    tree = _tree_block(document, fence, relpath)
    print(f"--- {relpath}")

    absent_packages = [p for p in PACKAGES if p not in tree]
    if absent_packages:  # cannot attribute modules to blocks that are not there
        print(f"    packages absent from tree: {absent_packages}")
        return 1

    blocks = _package_blocks(tree)
    missing = [m for m in modules if m.split("/")[-1] not in blocks[m.split("/", 1)[0]]]
    named = {
        (pkg, n)
        for pkg, block in blocks.items()
        for n in re.findall(r"([a-z_]+\.py)", block)
    }
    ghosts = sorted(
        f"{pkg}/{n}"
        for pkg, n in named
        if not any(m.split("/", 1)[0] == pkg and m.split("/")[-1] == n for m in modules)
    )
    print(f"    missing from tree: {missing or 'none'}")
    print(f"    in tree but absent from src/: {ghosts or 'none'}")
    return 1 if (missing or ghosts) else 0


def main() -> int:
    """Diff every authoritative tree against `src/`, in both directions."""
    modules = sorted(
        str(p.relative_to(REPO_ROOT / "src")) for p in (REPO_ROOT / "src").rglob("*.py")
    )
    if not modules:
        print(
            "FAILED: no modules found under src/; the check cannot be vacuously true."
        )
        return 1
    print(f"source modules: {len(modules)}")

    stale = [rel for rel, fence in TREES if _check_one(rel, fence, modules)]
    if stale:
        print(f"\nFAILED: out of date — {', '.join(stale)}")
        return 1
    print(f"\nPASSED: {len(TREES)} trees match src/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
