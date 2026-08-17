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
if [ ! -f "../pyproject.toml" ] || [ ! -f "../README.md" ]; then
    # A guard that disables itself when its inputs move is not a guard (register C-89).
    # This script is a CI gate; a rename must fail it, not silently skip it.
    echo "  ERROR: expected ../pyproject.toml and ../README.md; cannot check the banner"
    errors=$((errors + 1))
else
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

# --- Completeness assertions (register C-85) ---------------------------------
#
# Checks 1-6 verify that documents are internally consistent. Nothing verified that a
# document which *enumerates* a surface enumerates all of it. That gap produced C-64,
# C-81 and C-85: `docs/CICs/README.md` claimed "fully contracted" three times while a
# public class had no contract, `GOVERNANCE.md` named three of seven published
# conformance entry points, and ADR-018 omitted an entire package.
#
# Each check below reads the CODE and asserts the DOCUMENT names what it found. They are
# bash-and-grep on purpose: the `docs` CI job installs no Python (see ci.yml), and tying a
# documentation gate to the Python matrix is an unrelated thing to change.
#
# Names are matched on WORD BOUNDARIES, not as substrings. A plain `grep -F` would let
# `hdi_tower` satisfy `hdi`, and let any `*Frame` satisfy the bare `Frame` protocol —
# measured: `Frame` has 84 substring hits across the CICs and 9 real ones. That is the
# third time a substring match has been the defect here (`scripts/check_arch_tree.py`,
# then the S5 verification), so it is called out rather than left to be rediscovered.
#
# `__all__` blocks in this repository are literal lists of quoted names, so sed can read
# them. Two of the three conformance modules declare no `__all__` at all (register C-87),
# so their published surface is read as their public `assert_*` definitions instead — the
# asymmetry is documented in GOVERNANCE.md rather than hidden here.

# Print every publicly exported name, one per line: `module<TAB>name`.
published_names() {
    for init in ../src/views_frames/__init__.py \
                ../src/views_frames_summarize/__init__.py \
                ../src/views_frames_reconcile/__init__.py \
                ../src/views_frames/conformance/__init__.py; do
        [ -f "$init" ] || { echo "MISSING	$init"; continue; }
        sed -n '/^__all__ = \[/,/^\]/p' "$init" \
            | grep -oE '"[A-Za-z_][A-Za-z0-9_]*"' | tr -d '"' \
            | while read -r n; do echo "$init	$n"; done
    done
    # C-87: these two declare no `__all__`; their published surface is their assert_* defs.
    for mod in ../src/views_frames_summarize/conformance.py \
               ../src/views_frames_reconcile/conformance.py; do
        [ -f "$mod" ] || { echo "MISSING	$mod"; continue; }
        grep -oE '^def (assert_[A-Za-z0-9_]+)' "$mod" | sed 's/^def //' \
            | while read -r n; do echo "$mod	$n"; done
    done
}

# 7. Every publicly exported name is named in some CIC.
echo "--- Checking every exported name appears in a CIC ---"
if [ ! -d "CICs" ]; then
    echo "  ERROR: no CICs/ directory; cannot check exported-name coverage"
    errors=$((errors + 1))
else
    while IFS="	" read -r where name; do
        if [ "$where" = "MISSING" ]; then
            echo "  ERROR: expected $name; cannot read the published surface"
            errors=$((errors + 1))
        elif ! grep -qE "\b${name}\b" CICs/*.md; then
            echo "  ERROR: '$name' is exported by $where but named in no CIC"
            errors=$((errors + 1))
        fi
    done <<EOF
$(published_names)
EOF
    # Presence is the gate. Telling "contracted" from "mentioned in passing" is a judgement
    # this script cannot make, so a single occurrence is reported for a human to look at —
    # NOT an error. A single occurrence is often correct (`assert_index_alignment_laws` is
    # contracted by exactly one bolded entry in Conformance.md). The known real case is
    # `TowerSummary`, whose only occurrence describes what `summarize_tower` returns rather
    # than contracting the type — see issue #246 and register C-91.
    published_names | grep -v '^MISSING' | cut -f2 | sort -u | while read -r name; do
        hits=$(grep -ohE "\b${name}\b" CICs/*.md 2>/dev/null | wc -l)
        [ "$hits" = "1" ] && echo "  INFO: '$name' occurs once in CICs/ — fine if that occurrence IS its contract entry; look if unsure"
    done
    echo "  OK (checked $(published_names | grep -cv '^MISSING') exported names)"
fi

# 8. Every public class has a CIC, or an exemption stated in the CIC index.
echo "--- Checking every public class has a CIC or a stated exemption ---"
if [ ! -f "CICs/README.md" ]; then
    echo "  ERROR: no CICs/README.md; cannot check class coverage"
    errors=$((errors + 1))
else
    class_count=0
    while read -r cls; do
        class_count=$((class_count + 1))
        grep -qE "\b${cls}\b" CICs/*.md || {
            echo "  ERROR: class '$cls' has no CIC and no exemption in CICs/README.md"
            errors=$((errors + 1))
        }
    done <<EOF
$(grep -rhoE '^class [A-Za-z_][A-Za-z0-9_]*' ../src --include='*.py' | sed 's/^class //' | sort -u)
EOF
    echo "  OK (checked $class_count public classes)"
fi

# 9. GOVERNANCE.md names every published conformance entry point (register C-85 item 1).
echo "--- Checking GOVERNANCE.md names every published conformance entry point ---"
if [ ! -f "../GOVERNANCE.md" ]; then
    echo "  ERROR: no ../GOVERNANCE.md; cannot check the conformance table"
    errors=$((errors + 1))
else
    conf_count=0
    while IFS="	" read -r where name; do
        case "$where" in *conformance*) ;; *) continue ;; esac
        conf_count=$((conf_count + 1))
        grep -qE "\b${name}\b" ../GOVERNANCE.md || {
            echo "  ERROR: '$name' is a published conformance name ($where) but GOVERNANCE.md does not name it"
            errors=$((errors + 1))
        }
    done <<EOF
$(published_names)
EOF
    echo "  OK (checked $conf_count published conformance names)"
fi

echo ""
if [ "$errors" -gt 0 ]; then
    echo "=== FAILED: $errors issue(s) found ==="
    exit 1
else
    echo "=== PASSED: no issues found ==="
    exit 0
fi
