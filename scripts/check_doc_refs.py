"""Cross-reference resolution for the governance corpus.

The documents in this repository cite each other about 3,600 times — roughly 1,160 `ADR-NNN`
references, 1,770 `C-NN` register concerns, 120 `D-NN` disagreements and 140 source paths in
prose. Every one is a claim that something exists. Until this script, none of them was checked,
and the only reason none had rotted is that nobody had renamed a file yet.

This resolves each reference against its source of truth:

    ADR-NNN     ->  docs/ADRs/NNN_*.md exists
    C-NN        ->  a `### C-NN` header in the register
    D-NN        ->  a `### D-NN` header in the register
    src/... .py ->  the file exists
    tests/....py -> the file exists

**The allowlist is the load-bearing part.** Some references are deliberately non-local: a
sibling repository's ADR, a concern in another repo's register, an id this register skipped on
purpose. A checker that flags those is a checker someone switches off within a week, so each
one is listed below with its reason.

**The allowlist is not free-floating.** `reports/technical_risk_register.md` already documents
every non-local id in its *Register Conventions* section — that prose is the authority, and
this script is the machine-readable half. To stop the two drifting apart (which is the exact
defect class this script exists to catch), every allowlisted id must also appear in that
section, and the script fails if one does not. Adding a foreign id here without documenting it
there is therefore an error, in both directions.

**What this does not catch.** That a reference points at the *right* thing. `ADR-018` resolving
to a file proves the file exists, not that ADR-018 says what the citing sentence claims. That
is a comparison problem, and comparison is what a human read is for.

GitHub issue references (`#NNN`) are **not** resolved by default. CI has no business calling
the GitHub API, and a doc check that needs the network is a doc check that goes red when
GitHub does. Use ``--check-issues`` for a manual sweep.

Usage::

    python3 scripts/check_doc_refs.py                # CI: offline, exits 1 on a dangling ref
    python3 scripts/check_doc_refs.py --check-issues # manual: also resolves #NNN via `gh`

Exits 0 when every reference resolves or is allowlisted, 1 with a report when it does not.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "reports" / "technical_risk_register.md"

# Directories whose contents are not governance prose.
SKIP_DIRS = {
    ".git",
    "graphify-out",
    "node_modules",
    ".venv",
    "__pycache__",
    ".mypy_cache",
}

# --- The allowlist -------------------------------------------------------------------------
#
# Every entry is a reference that is CORRECT despite not resolving locally. The reason is not
# decoration: it is what lets the next reader tell "foreign" from "broken" without going and
# finding out. Each id must also be documented in the register's Register Conventions section
# — `_check_allowlist_is_documented` enforces that, so this list cannot quietly diverge.

FOREIGN_ADRS = {
    "034": "views-pipeline-core's ADR",
    "044": "views-datafactory's ADR (area-majority GAUL work)",
    "055": "sibling repo's ADR, paired with the foreign D-29",
}

FOREIGN_CONCERNS = {
    "30": "views-pipeline-core's id for the cross-repo contract-test gap — skipped here on purpose",
    "48": "views-reporting's concern (run-identity ambiguity)",
    "108": "views-reporting's concern",
    "135": "views-reporting's concern",
    "164": "views-reporting's concern",
    "165": "views-reporting's concern",
    "167": "views-reporting's concern",
    "184": "views-reporting's concern",
    "186": "views-reporting's concern (the #181 report-stage OOM)",
    "198": "views-pipeline-core's concern",
}

# Ids this register deliberately never assigned. Distinct from foreign ids: these are *local*
# numbers that were skipped, and the register says why.
SKIPPED_CONCERNS = {
    "04": "merged into C-18 (the SpatialLevel slippery slope)",
}

FOREIGN_DISAGREEMENTS = {
    "28": "views-pipeline-core's disagreement (relocate reconciliation)",
    "29": "sibling repo's disagreement, paired with the foreign ADR-055",
    "33": "views-pipeline-core's disagreement",
}

# Paths that appear in prose as illustrations of something that does NOT exist — a file a
# future violation would create, or an elision. Flagging these would be flagging the prose for
# being explanatory.
HYPOTHETICAL_PATHS = {
    "src/views_frames/metric_frame.py": "a hypothetical future file, cited to describe what a violation would look like",
}

# Template files legitimately contain placeholder references.
TEMPLATE_FILES = {"docs/CICs/cic_template.md", "docs/ADRs/adr_template.md"}

# Documents written from ANOTHER repository's point of view. `perspectives/` holds cross-repo
# design reviews ("from views-datafactory's perspective") and `critiqus/` holds the critique
# rounds that fed them. In these, an unqualified `ADR-045` or `C-182` is the *author's* repo's
# numbering, not ours, and `src/datafactory_adapters/...` is their tree. Resolving those against
# this repository would flag correct prose, which is how a check gets switched off.
#
# They are not exempt, only differently scoped: a path under THIS repo's own packages is still
# checked in them, because that reference is unambiguously about us.
CROSS_REPO_DIRS = ("perspectives/", "critiqus/")

# Paths that are unambiguously this repository's, wherever they appear.
OWN_SOURCE_PREFIXES = ("src/views_frames",)

ADR_RE = re.compile(r"\bADR-(\d{3})\b")
CONCERN_RE = re.compile(r"\bC-(\d{2,3})\b")
DISAGREEMENT_RE = re.compile(r"\bD-(\d{2})\b")
PATH_RE = re.compile(r"\b((?:src|tests|scripts)/[A-Za-z0-9_./-]+\.py)\b")
ISSUE_RE = re.compile(r"(?<![A-Za-z0-9])#(\d{2,4})\b")


def markdown_files() -> list[Path]:
    """Every governance document in the repository, in a stable order."""
    out = []
    for p in sorted(REPO_ROOT.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return out


def local_adrs() -> set[str]:
    return {
        p.name.split("_")[0] for p in (REPO_ROOT / "docs" / "ADRs").glob("[0-9]*.md")
    }


def register_ids(prefix: str) -> set[str]:
    """Every `### C-NN` / `### D-NN` header in the register, normalised without leading zeros.

    Raises FileNotFoundError if the register has moved. `main` turns that into a loud, named
    failure rather than a traceback: a check that dies obscurely when its input moves is the
    same defect as one that silently passes (register C-89).
    """
    text = REGISTER.read_text()
    return {
        m.group(1).lstrip("0") or "0"
        for m in re.finditer(rf"^### {prefix}-(\d+):", text, re.M)
    }


def _norm(n: str) -> str:
    return n.lstrip("0") or "0"


def _check_allowlist_is_documented() -> list[str]:
    """Every allowlisted id must be named in the register's conventions prose.

    This is the half that stops the allowlist becoming a second, silently diverging source of
    truth — the failure mode the register calls "the instance fix instead of the class fix".
    """
    errors = []
    if not REGISTER.exists():
        return [
            f"ERROR: {REGISTER} is missing; cannot verify the allowlist is documented"
        ]
    conventions = REGISTER.read_text()
    marker = "Register Conventions"
    if marker in conventions:
        conventions = conventions[conventions.index(marker) :]
    for num in FOREIGN_ADRS:
        if f"ADR-{num}" not in conventions:
            errors.append(
                f"ERROR: allowlisted ADR-{num} is not documented in the register's {marker}"
            )
    for num in {**FOREIGN_CONCERNS, **SKIPPED_CONCERNS}:
        if f"C-{num}" not in conventions:
            errors.append(
                f"ERROR: allowlisted C-{num} is not documented in the register's {marker}"
            )
    for num in FOREIGN_DISAGREEMENTS:
        if f"D-{num}" not in conventions:
            errors.append(
                f"WARN: allowlisted D-{num} is not named in the register's {marker} — "
                "document it there so a reader can tell foreign from broken"
            )
    return errors


def _resolve_issues(numbers: set[str]) -> list[str]:
    """Manual-only: ask `gh` whether each issue number exists. Never called from CI."""
    errors = []
    for num in sorted(numbers, key=int):
        r = subprocess.run(
            ["gh", "issue", "view", num, "--json", "number"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            r = subprocess.run(
                ["gh", "pr", "view", num, "--json", "number"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        if r.returncode != 0:
            errors.append(
                f"ERROR: #{num} resolves to neither an issue nor a pull request"
            )
    return errors


def main() -> int:
    check_issues = "--check-issues" in sys.argv
    errors: list[str] = []
    errors.extend(_check_allowlist_is_documented())

    adrs = local_adrs()
    try:
        concerns = register_ids("C")
        disagreements = register_ids("D")
    except FileNotFoundError:
        print(
            f"  ERROR: {REGISTER.relative_to(REPO_ROOT)} not found; cannot resolve any C-/D- reference"
        )
        return 1
    if not adrs or not concerns:
        print(
            "  ERROR: found no local ADRs or no register concerns; the check cannot be vacuously true"
        )
        return 1

    counts = {"ADR": 0, "C": 0, "D": 0, "path": 0, "issue": 0}
    issue_numbers: set[str] = set()

    for doc in markdown_files():
        rel = doc.relative_to(REPO_ROOT).as_posix()
        is_template = rel in TEMPLATE_FILES
        cross_repo = rel.startswith(CROSS_REPO_DIRS)
        text = doc.read_text(errors="replace")

        for m in ADR_RE.finditer(text):
            num = m.group(1)
            counts["ADR"] += 1
            if num in adrs or num in FOREIGN_ADRS or is_template or cross_repo:
                continue
            errors.append(
                f"ERROR: {rel} cites ADR-{num}, which has no file in docs/ADRs/"
            )

        for m in CONCERN_RE.finditer(text):
            num = _norm(m.group(1))
            counts["C"] += 1
            if cross_repo or num in concerns:
                continue
            if num in {_norm(k) for k in {**FOREIGN_CONCERNS, **SKIPPED_CONCERNS}}:
                continue
            errors.append(
                f"ERROR: {rel} cites C-{m.group(1)}, which has no entry in the register"
            )

        for m in DISAGREEMENT_RE.finditer(text):
            num = _norm(m.group(1))
            counts["D"] += 1
            if cross_repo or num in disagreements:
                continue
            if num in {_norm(k) for k in FOREIGN_DISAGREEMENTS}:
                continue
            errors.append(
                f"ERROR: {rel} cites D-{m.group(1)}, which has no entry in the register"
            )

        for m in PATH_RE.finditer(text):
            path = m.group(1)
            # Only OUR paths are resolvable. `src/datafactory_adapters/...` in a cross-repo
            # review is that repo's tree; `tests/...` there is ambiguous, so it is checked only
            # in local documents where `tests/` can only mean ours.
            ours = path.startswith(OWN_SOURCE_PREFIXES) or (
                not cross_repo and path.startswith(("tests/", "scripts/"))
            )
            if not ours:
                continue
            counts["path"] += 1
            if path in HYPOTHETICAL_PATHS or (REPO_ROOT / path).exists():
                continue
            errors.append(f"ERROR: {rel} cites `{path}`, which does not exist")

        if check_issues:
            for m in ISSUE_RE.finditer(text):
                counts["issue"] += 1
                issue_numbers.add(m.group(1))

    if check_issues:
        errors.extend(_resolve_issues(issue_numbers))

    total = sum(counts.values())
    print(f"references checked: {total}")
    for kind, n in counts.items():
        if n:
            print(f"  {kind:6s} {n}")
    allow = (
        len(FOREIGN_ADRS)
        + len(FOREIGN_CONCERNS)
        + len(SKIPPED_CONCERNS)
        + len(FOREIGN_DISAGREEMENTS)
    )
    print(f"  allowlisted non-local ids: {allow} (each documented in the register)")
    if not check_issues:
        print("  (#NNN issue references not resolved — run with --check-issues)")

    if errors:
        print()
        for e in errors:
            print(f"  {e}")
        print(f"\nFAILED: {len(errors)} unresolved reference(s)")
        return 1
    print("\nPASSED: every reference resolves or is a documented non-local id")
    return 0


if __name__ == "__main__":
    sys.exit(main())
