# Publishing `views-frames` to PyPI

A practical runbook for releasing this package, modelled on the views-reporting
routine. Written to be followed **solo, cold, months later** — every command is
copy-paste-able. If you only need to ship a routine update, the cheat sheet is enough.

> Build tooling: **hatchling + uv** (see `pyproject.toml`, CLAUDE.md). Release
> automation: `.github/workflows/publish_package.yml` (Trusted Publishing / OIDC).
> Versioning policy: `GOVERNANCE.md` (the v1.0 freeze; ADR-018).

---

## What is special about this package (read once)

| Thing | What | Why it matters |
|---|---|---|
| **One project, three packages** | The single `views-frames` wheel bundles `views_frames` (the leaf), `views_frames_summarize` and `views_frames_reconcile` (the siblings) — see `[tool.hatch.build.targets.wheel]` | `pip install views-frames` makes **all three** importable. There are no separate `views-frames-summarize` or `views-frames-reconcile` projects. |
| **numpy-only, broad Python** | `requires-python = ">=3.10"`; the only runtime dep is `numpy>=1.26,<3`. `pyarrow` is an optional `[arrow]` extra | No build cap, no heavy deps — installs are fast and the wheel is pure-Python (`py3-none-any`). |
| **Versions are write-once** | Once `X.Y.Z` is on PyPI it can never be re-uploaded or truly deleted (only "yanked") | Always **bump the version first**. For repeated TestPyPI rehearsals use a throwaway like `1.0.1.dev1`. |
| **uv + hatchling, NOT poetry** | Build backend is `hatchling.build`; tooling is `uv` | Use `uv build` / `uv publish`. |
| **Frozen API since v1.0.0** | ADR-018 froze the public surface | Breaking changes are MAJOR + the cross-repo process in `GOVERNANCE.md`. |

---

## TL;DR — release an update (the automated way)

Normal releases are published **by CI** when you publish a **GitHub Release** — you do
**not** run `uv publish` by hand. Auth is PyPI Trusted Publishing (no token); see
`.github/workflows/publish_package.yml`.

```bash
# 1. bump the version on a branch (you can NEVER reuse a published version)
$EDITOR pyproject.toml                          # under [project]: version = "X.Y.Z"
git commit -am "release: vX.Y.Z" && git push    # open a PR -> merge to main

# 2. (optional, wise for big changes) rehearse on TestPyPI first — see §A

# 3. cut the GitHub Release FROM main — this triggers the publish workflow:
gh release create vX.Y.Z --target main --title "views-frames X.Y.Z" --notes "what changed"
#    (or GitHub UI: Releases -> Draft a new release -> tag vX.Y.Z on main -> Publish)

# 4. confirm: Actions tab shows "Publish Package" green, then
#    https://pypi.org/project/views-frames/
```

The workflow guards the version (must beat PyPI), `uv build`s, and `uv publish`es via
Trusted Publishing — **no token needed**. First-ever setup requires the one-time PyPI
trusted-publisher config — see Prerequisites.

---

### Pre-tag checklist — run this before `gh release create`

`gh release create` is the point of no return: it publishes, and a PyPI version can never
be reused. Everything below is checkable in about two minutes. Tick it.

**Every release**

- [ ] CI is green on **the exact commit you are about to tag**, not merely on the branch:
      `gh api repos/views-platform/views-frames/commits/$(git rev-parse main)/check-runs -q '.check_runs[]|"\(.conclusion) \(.name)"'`
- [ ] `bash docs/validate_docs.sh` passes (this includes the README banner and the
      wheel-package checks)
- [ ] `python3 scripts/check_arch_tree.py` passes
- [ ] `rm -rf dist && uv build && uvx --from twine twine check dist/*` — both artifacts PASSED
- [ ] the built wheel carries **every** package in `[tool.hatch.build.targets.wheel] packages`
      with its `py.typed`
- [ ] `CHANGELOG.md` has an entry for this version and no `[Unreleased]` section remains

**MAJOR only — the expensive ones**

- [ ] **An adoption issue is filed in every pinned consumer repository.** Register **C-13**'s
      trigger requires this *before tagging*, and `GOVERNANCE.md` §Cross-repo MAJOR-bump
      process step 3 says the same. Find the consumers by their pins, not from memory:
      ```bash
      for r in $(gh repo list views-platform --limit 50 --json name -q '.[].name'); do
        gh api "repos/views-platform/$r/contents/pyproject.toml" -q .content 2>/dev/null \
          | base64 -d 2>/dev/null | grep -q "views-frames" && echo "$r"
      done
      ```
- [ ] The **conformance floor** decision is made and recorded — `CONFORMANCE_FLOOR` is bumped
      on any breaking change to any published entry point (`GOVERNANCE.md`), and moving it
      means every consumer's CI begins asserting a new contract version.
- [ ] An ADR records the decision and the migration (`GOVERNANCE.md` MAJOR process step 1).

> **Why this exists.** Until 2026-08-18 C-13's requirement lived only in the risk register,
> which is not the document anyone stands in front of at release time. 2.0.0 reached
> "ready to tag" with **zero** adoption issues filed — the rule existed and was invisible at
> the moment it applied. A pre-release falsification audit caught it; this checklist is so
> the next one does not need to.

---

## Prerequisites (one-time setup) — Trusted Publishing

The release workflow authenticates with **Trusted Publishing (OIDC)** — there is **no
stored token**. A project owner enables it **once** on PyPI.

**This is already configured** — `views-frames` has been on PyPI since `v1.0.0` and the
trusted publisher lives under the project's **Settings → Publishing**. What follows is kept
for reference: how it was set up, and what to repeat if the entry is ever lost or a second
project is added. It was originally a *pending* publisher, which is how PyPI lets you trust
a publisher for a project that does not exist yet:

> PyPI → your account → **Publishing** → **Add a pending publisher (GitHub)**:
> - **PyPI Project Name:** `views-frames`
> - **Owner:** `views-platform`  ·  **Repository:** `views-frames`
> - **Workflow name:** `publish_package.yml`  ·  **Environment:** *(leave blank)*

After the first release created the project, that entry became a normal trusted publisher
under **Settings → Publishing**, which is where it is today. If it is ever removed, the
workflow's publish step fails with an auth error and nothing else breaks.

> If you'd rather not use a pending publisher, do the **first** upload manually with a
> token (§B), then all future releases go through the automated path.

### Creating an API token (web UI — the click-by-click, for the manual path §A/§B)

You need a token on **each site you upload to**: **TestPyPI** (https://test.pypi.org) for
rehearsals (§A) and **real PyPI** (https://pypi.org) for releases (§B). They are **separate
accounts with separate tokens** — a TestPyPI token gets a `403` on real PyPI and vice-versa.
The steps are identical on both sites:

1. Log in. Click your **username** (top-right corner).
2. Click **Account settings** (left sidebar).
3. Scroll down to the **API tokens** section → **Add API token**.
4. **Token name:** any label, e.g. `views-frames-release`.
5. **Scope:** for a **first-ever** upload of a project, choose **"Entire account (all
   projects)"** — PyPI will not let you scope to a project that does not exist yet (the
   "Proceed with caution" banner is expected). For *later* uploads, scope to the
   **`views-frames`** project (see the next note).
6. Click **Create token**.
7. The token (`pypi-AgEN…`) is shown **once**, with a **copy button** — copy it now; you
   cannot see it again. Ignore the `.pypirc` / `pip` config snippets it also shows.

🔒 Paste the token **only** into your own terminal's `uv publish --token …` command — never
into a chat, PR, or commit. Put a **space before** the command (or `export
UV_PUBLISH_TOKEN=…` and drop `--token`) to keep it out of shell history.

### After the first publish — tighten the token scope (register C-28)

An **"Entire account"** token can upload to *all* your PyPI projects, so it is
over-privileged once `views-frames` exists. Housekeeping after the first release: **Account
settings → API tokens → delete `views-frames-release`**, then either rely on the tokenless
Trusted-Publishing workflow (recommended) **or** create a new token **scoped to the
`views-frames` project** for future manual uploads.

---

## A. TestPyPI dress rehearsal (optional, recommended for big releases)

```bash
rm -rf dist && uv build
uvx --from twine twine check dist/*            # both files must say PASSED
# sanity: all three packages + their py.typed are in the wheel
python3 -c "import zipfile,glob; ns=zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist(); \
print([n for n in ns if n.endswith('py.typed')])"   # expect all three packages' py.typed

# upload to TestPyPI (your terminal; replace the token — never paste it in chat)
uv publish --publish-url https://test.pypi.org/legacy/ --token pypi-<YOUR-TESTPYPI-TOKEN> dist/*

# clean-room install back (TestPyPI for this pkg, real PyPI for numpy)
uv venv --clear --python 3.11 /tmp/tp-check && source /tmp/tp-check/bin/activate
uv pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ views-frames
python -c "import views_frames, views_frames_summarize, views_frames_reconcile; print('all three import OK')"
deactivate && rm -rf /tmp/tp-check
```

> The two index URLs are both required — TestPyPI only hosts *your* package; `numpy`
> lives on real PyPI.

---

## B. Break-glass — manual upload

Not the normal path, and not needed since `v1.0.0`. Use it only if Trusted Publishing is
broken and a release genuinely cannot wait for it to be fixed.

```bash
git checkout main && git pull --ff-only
rm -rf dist && uv build && uvx --from twine twine check dist/*
# publish to REAL PyPI
uv publish --token pypi-<YOUR-REAL-PYPI-TOKEN> dist/*
# confirm it's live:
curl -s https://pypi.org/pypi/views-frames/json | \
  python3 -c "import sys,json;d=json.load(sys.stdin)['info'];print(d['name'],d['version'])"
```

Then go straight back to the automated path (§C) — a manual upload leaves no Actions
record of what was published.

> 🔒 **Token safety:** type a token only in your own terminal; never paste it into a
> chat/transcript/PR. Prefix the command with a space (or `export UV_PUBLISH_TOKEN=…`) to
> keep it out of shell history.

---

## C. Future updates (the repeatable loop — automated)

1. **Bump `version`** in `pyproject.toml` under `[project]` (you cannot reuse a published
   version; SemVer per `GOVERNANCE.md` — post-1.0 breaking = MAJOR).
2. Commit on a branch → PR → **merge to `main`**.
3. (Optional) rehearse on TestPyPI (§A) with a throwaway `X.Y.Z.dev1`; revert before merge.
4. **Cut the GitHub Release from `main`** — triggers `publish_package.yml`:
   ```bash
   gh release create vX.Y.Z --target main --title "views-frames X.Y.Z" --notes "what changed"
   ```
   It runs the **version guard**, `uv build`, `uv publish` via **Trusted Publishing**.
4½. **Before step 4 fires, walk the [pre-tag checklist](#pre-tag-checklist--run-this-before-gh-release-create).**
   It is short, and it is the step that catches the expensive omissions — a MAJOR whose
   consumers have not been told, a conformance floor nobody decided.
5. **Verify:** Actions → *Publish Package* green, then https://pypi.org/project/views-frames/.

> Under the hood: `release: published` → `permissions: id-token: write` mints an OIDC
> token → PyPI checks the GitHub claim against the trusted publisher → upload. The version
> guard fails the run if `[project].version` isn't higher than what's on PyPI, so "forgot
> to bump" is a loud error, not a wasted version.

---

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `403 Forbidden` on the automated publish | Trusted publisher not configured (or name mismatch). Re-check the Prerequisites entry (owner `views-platform`, repo `views-frames`, workflow `publish_package.yml`). |
| `400 … File already exists` | That version is already uploaded — **versions are write-once**. Bump `version` and rebuild. |
| Version guard fails the run | `[project].version` ≤ current PyPI version. Bump it. |
| `twine check` fails on metadata | Stale build — `rm -rf dist && uv build` and re-check. |
| TestPyPI install can't find numpy | Missing `--extra-index-url https://pypi.org/simple/`. |

---

## Provenance

- This guide and `.github/workflows/publish_package.yml` mirror the views-reporting
  routine (its `documentation/guides/publishing-to-pypi.md`), adapted: no Python cap, no
  bundled assets, and a single wheel that ships `views_frames`,
  `views_frames_summarize` and `views_frames_reconcile`.
- **Exercised by every release published since `v1.0.0`**, including the `v1.7.0` publish that added
  the third package to the wheel. This line said "not yet exercised by a real release" until
  2026-08-18, having been written before the first one and never revised — the same drift
  the version banner check and the architecture-tree check exist to prevent, in the guide
  that describes how releases work.
