#!/usr/bin/env bash
# Validates internal consistency of base_docs documentation set.
# Exit 0 if clean, exit 1 if issues found.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

errors=0

echo "=== base_docs validation ==="
echo ""

# 1. Check for unfilled template placeholders in accepted/active files
#    (skip files whose names contain "template" — those are expected to have placeholders)
#    These are warnings only (non-blocking) since in the template repo some
#    files are legitimately Accepted with placeholder dates.
echo "--- Checking for template placeholders in accepted/active files ---"
warnings=0
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ "$file" == *template* ]] && continue
    if grep -q 'YYYY-MM-DD' "$file"; then
        echo "  WARN: Unfilled date placeholder in $file"
        warnings=$((warnings + 1))
    fi
    if grep -q '<roles / team>' "$file"; then
        echo "  WARN: Unfilled deciders placeholder in $file"
        warnings=$((warnings + 1))
    fi
    if grep -q '<ClassName>' "$file"; then
        echo "  WARN: Unfilled ClassName placeholder in $file"
        warnings=$((warnings + 1))
    fi
done < <(grep -rl 'Status:.*\(Accepted\|Active\)' --include='*.md' . 2>/dev/null || true)
if [ "$warnings" -eq 0 ]; then
    echo "  OK"
fi

# 2. Verify CIC active contracts exist (skip blockquote/example lines)
echo "--- Checking CIC active contract references ---"
if [ -f "CICs/README.md" ]; then
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        contract=$(echo "$line" | sed -n 's/^- `\(.*\.md\)`.*$/\1/p')
        if [ -n "$contract" ] && [ ! -f "CICs/$contract" ]; then
            echo "  ERROR: CIC contract listed but missing: CICs/$contract"
            errors=$((errors + 1))
        fi
    done < <(grep -E '^- `[A-Z].*\.md`' CICs/README.md 2>/dev/null | grep -v '>' || true)
fi

# 3. Cross-ADR reference integrity (constitutional ADRs 000-009 only;
#    higher numbers are project-specific and not expected in the template repo)
echo "--- Checking cross-ADR references (constitutional: 000-009) ---"
while IFS= read -r ref; do
    [[ -z "$ref" ]] && continue
    file=$(echo "$ref" | cut -d: -f1)
    adr_num=$(echo "$ref" | grep -oP 'ADR-00\K[0-9]' | head -1)
    if [ -n "$adr_num" ]; then
        match_count=$(find ADRs -name "00${adr_num}_*.md" 2>/dev/null | wc -l)
        if [ "$match_count" -eq 0 ]; then
            echo "  ERROR: $file references ADR-00${adr_num} but no matching file found"
            errors=$((errors + 1))
        fi
    fi
done < <(grep -rn 'ADR-00[0-9]' --include='*.md' . 2>/dev/null || true)

# 4. Check that referenced protocol files exist
echo "--- Checking protocol file references ---"
while IFS= read -r ref; do
    [[ -z "$ref" ]] && continue
    file=$(echo "$ref" | cut -d: -f1)
    proto=$(echo "$ref" | grep -oP 'contributor_protocols/[a-z_]+\.md' | head -1)
    if [ -n "$proto" ] && [ ! -f "$proto" ]; then
        echo "  ERROR: $file references $proto but file does not exist"
        errors=$((errors + 1))
    fi
done < <(grep -rn 'contributor_protocols/' --include='*.md' . 2>/dev/null || true)

# 5. Report template status markers
echo "--- Checking template status markers ---"
template_count=$(grep -rl '\-\-template\-\-' --include='*.md' . 2>/dev/null | wc -l)
echo "  INFO: $template_count files still have --template-- status (expected in template repo)"

# 6. README status banner tracks the released MAJOR.MINOR (guards the narrative
#    epoch-lag found by the 2026-07 audit, register C-70: the banner sat at v1.7.0
#    while 1.8.0 was on PyPI). Patch releases are exempt — the banner tracks the
#    surface, which only MINORs change.
echo "--- Checking README status banner vs pyproject version ---"
if [ -f "../pyproject.toml" ] && [ -f "../README.md" ]; then
    pyver=$(grep -m1 '^version = ' ../pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    pymm=$(echo "$pyver" | cut -d. -f1,2)
    banner=$(grep -m1 -oE '\*\*Status:\*\* \*\*v[0-9]+\.[0-9]+' ../README.md | grep -oE '[0-9]+\.[0-9]+')
    if [ -z "$banner" ]; then
        echo "  ERROR: could not find a '**Status:** **vX.Y' banner in README.md"
        errors=$((errors + 1))
    elif [ "$banner" != "$pymm" ]; then
        echo "  ERROR: README banner says v$banner but pyproject version is $pyver (MAJOR.MINOR $pymm)"
        errors=$((errors + 1))
    else
        echo "  OK (banner v$banner ~ pyproject $pyver)"
    fi
fi

echo ""
if [ "$errors" -gt 0 ]; then
    echo "=== FAILED: $errors issue(s) found ==="
    exit 1
else
    echo "=== PASSED: no issues found ==="
    exit 0
fi
