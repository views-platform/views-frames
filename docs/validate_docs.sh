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
# Each check reads the CODE and asserts the DOCUMENT names what it found. Bash-and-grep
# on purpose: the `docs` CI job installs no Python (ci.yml), and tying a documentation
# gate to the Python matrix is an unrelated thing to change.
#
# THREE WAYS THESE CHECKS COULD LIE, ALL OF WHICH BIT DURING REVIEW:
#
#  1. Substring matching. `Frame` has 84 substring hits across the CICs and 9 real ones,
#     so `grep -F` would let any `*Frame` satisfy the bare `Frame` protocol and let
#     `hdi_tower` satisfy `hdi`. Names are matched on word boundaries.
#  2. A parser that silently reads nothing. The first version matched only the literal
#     `__all__ = [`; annotating one file as `__all__: list[str] = [` — a form already used
#     in `src/views_frames/io/__init__.py` — dropped check 7 from 38 names to 32 and
#     check 9 from 8 to 2, and the script still printed PASSED. Extraction now accepts the
#     annotated and one-line forms, and a block containing quoted names that yields none
#     is an ERROR, not a quiet zero.
#  3. Iterating over nothing. With `../src` absent, an empty line still satisfies
#     `read -r`, and `grep -qE "\b\b"` matches everything — check 8 reported
#     "OK (checked 1 public classes)". Every loop skips blank input, and `../src` is
#     guarded.
#
# NOT COVERED, deliberately: `src/views_frames/io/`. Its published surface is module-level
# (`npz.save`, `arrow.load`, …) by decision D-11 rather than `__all__` — its `__all__` is
# empty on purpose — and those functions are contracted through the frames' `save`/`load`
# in the frame CICs. Stated here rather than left for a reader to infer coverage this
# check does not give.
#
# Two of the three conformance modules declare no `__all__` (register C-87), so their
# surface is read from their public `assert_*` definitions. When C-87 is fixed and they
# gain an `__all__`, that takes precedence automatically — the fallback only applies when
# no `__all__` is present.

# Names declared in a file's `__all__`. Accepts `__all__ = [`, `__all__: list[str] = [`
# and the one-line form. Prints nothing when the file declares no `__all__`.
all_names_from() {
    sed -n '/^__all__[^=]*= *\[/,/\]/p' "$1" 2>/dev/null \
        | grep -oE '"[A-Za-z_][A-Za-z0-9_]*"' | tr -d '"'
}

# Every publicly exported name, one per line as `source<TAB>name`.
# Emits `MISSING<TAB>path` if a file is gone and `EMPTY<TAB>path` if its `__all__` holds
# quoted names but none could be read — either is a broken input, never a quiet pass.
published_names() {
    for init in ../src/views_frames/__init__.py \
                ../src/views_frames_summarize/__init__.py \
                ../src/views_frames_reconcile/__init__.py \
                ../src/views_frames/conformance/__init__.py; do
        if [ ! -f "$init" ]; then echo "MISSING	$init"; continue; fi
        names=$(all_names_from "$init")
        # Every scanned `__init__.py` MUST yield names. The repo requires explicit
        # re-exports and no `import *` (ADR-002 / the physical-architecture standard), so a
        # package `__init__` with no readable `__all__` is either a parse failure or a
        # convention breach — never a package that legitimately exports nothing.
        if [ -z "$names" ]; then echo "EMPTY	$init"; continue; fi
        echo "$names" | while read -r n; do [ -n "$n" ] && echo "$init	$n"; done
    done
    for mod in ../src/views_frames_summarize/conformance.py \
               ../src/views_frames_reconcile/conformance.py; do
        if [ ! -f "$mod" ]; then echo "MISSING	$mod"; continue; fi
        names=$(all_names_from "$mod")
        # C-87 fallback: only when the module declares no `__all__` at all. If it declares
        # one and we read nothing, that is a parse failure, not an empty surface.
        if [ -z "$names" ] && grep -q '^__all__' "$mod"; then
            echo "EMPTY	$mod"; continue
        fi
        [ -z "$names" ] && names=$(grep -oE '^def (assert_[A-Za-z0-9_]+)' "$mod" | sed 's/^def //')
        if [ -z "$names" ]; then echo "EMPTY	$mod"; continue; fi
        echo "$names" | while read -r n; do [ -n "$n" ] && echo "$mod	$n"; done
    done
}

if [ ! -d "../src" ]; then
    echo "--- Completeness assertions ---"
    echo "  ERROR: ../src not found; cannot check any documented surface against the code"
    errors=$((errors + 1))
else

# 7. Every publicly exported name is named in some CIC.
echo "--- Checking every exported name appears in a CIC ---"
before=$errors
if [ ! -d "CICs" ] || [ -z "$(ls CICs/*.md 2>/dev/null)" ]; then
    echo "  ERROR: no CIC files under CICs/; cannot check exported-name coverage"
    errors=$((errors + 1))
else
    while IFS="	" read -r where name; do
        [ -z "$where" ] && continue
        case "$where" in
            MISSING) echo "  ERROR: expected $name; cannot read the published surface"
                     errors=$((errors + 1)); continue ;;
            EMPTY)   echo "  ERROR: no exported names could be read from $name (missing or unparseable __all__)"
                     errors=$((errors + 1)); continue ;;
        esac
        grep -qE "\b${name}\b" CICs/*.md || {
            echo "  ERROR: '$name' is exported by $where but named in no CIC"
            errors=$((errors + 1))
        }
    done <<EOF
$(published_names)
EOF
    # Presence is the gate. Telling "contracted" from "mentioned in passing" is a judgement
    # this script cannot make, so a single occurrence is reported for a human — NOT an
    # error. One occurrence is often correct (`assert_index_alignment_laws` is contracted by
    # exactly one bolded entry in Conformance.md). The known real case is `TowerSummary`,
    # whose only occurrence describes what `summarize_tower` returns — register C-91.
    published_names | grep -vE '^(MISSING|EMPTY)' | cut -f2 | sort -u | while read -r name; do
        [ -z "$name" ] && continue
        hits=$(grep -ohE "\b${name}\b" CICs/*.md 2>/dev/null | wc -l)
        [ "$hits" = "1" ] && echo "  INFO: '$name' occurs once in CICs/ — fine if that occurrence IS its contract entry; look if unsure"
    done
    [ "$errors" -eq "$before" ] && echo "  OK (checked $(published_names | grep -vcE '^(MISSING|EMPTY)') exported names)"
fi

# 8. Every public class has a CIC, or an exemption stated in the CIC index.
echo "--- Checking every public class has a CIC or a stated exemption ---"
before=$errors
class_count=0
while read -r cls; do
    [ -z "$cls" ] && continue
    class_count=$((class_count + 1))
    grep -qE "\b${cls}\b" CICs/*.md 2>/dev/null || {
        echo "  ERROR: class '$cls' has no CIC and no exemption in CICs/README.md"
        errors=$((errors + 1))
    }
done <<EOF
$(grep -rhoE '^class [A-Za-z][A-Za-z0-9_]*' ../src --include='*.py' | sed 's/^class //' | sort -u)
EOF
if [ "$class_count" -eq 0 ]; then
    echo "  ERROR: found no public classes under ../src; the check cannot be vacuously true"
    errors=$((errors + 1))
fi
[ "$errors" -eq "$before" ] && echo "  OK (checked $class_count public classes)"

# 9. GOVERNANCE.md names every published conformance entry point (register C-85 item 1).
echo "--- Checking GOVERNANCE.md names every published conformance entry point ---"
before=$errors
if [ ! -f "../GOVERNANCE.md" ]; then
    echo "  ERROR: no ../GOVERNANCE.md; cannot check the conformance table"
    errors=$((errors + 1))
else
    conf_count=0
    while IFS="	" read -r where name; do
        [ -z "$where" ] && continue
        case "$where" in
            MISSING|EMPTY)
                case "$name" in *conformance*)
                    echo "  ERROR: $name is unreadable or exports nothing; cannot check it against GOVERNANCE.md"
                    errors=$((errors + 1)) ;;
                esac
                continue ;;
        esac
        case "$where" in *conformance*) ;; *) continue ;; esac
        conf_count=$((conf_count + 1))
        grep -qE "\b${name}\b" ../GOVERNANCE.md || {
            echo "  ERROR: '$name' is a published conformance name ($where) but GOVERNANCE.md does not name it"
            errors=$((errors + 1))
        }
    done <<EOF
$(published_names)
EOF
    if [ "$conf_count" -eq 0 ]; then
        echo "  ERROR: found no published conformance names; the check cannot be vacuously true"
        errors=$((errors + 1))
    fi
    [ "$errors" -eq "$before" ] && echo "  OK (checked $conf_count published conformance names)"
fi

fi  # ../src exists

echo ""
if [ "$errors" -gt 0 ]; then
    echo "=== FAILED: $errors issue(s) found ==="
    exit 1
else
    echo "=== PASSED: no issues found ==="
    exit 0
fi
