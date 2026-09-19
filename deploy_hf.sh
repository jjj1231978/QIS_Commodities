#!/usr/bin/env bash
# Deploy the current commit to the Hugging Face Space.
#
#   ./deploy_hf.sh            # deploy HEAD
#   ./deploy_hf.sh --commit   # stage+commit changed viewer artifacts first
#
# GitHub is NOT in this path. The Space is an independent git remote; pushing to
# GitHub is optional and does not trigger a rebuild.
#
# Why an orphan branch rather than `git push hf HEAD:main`: the Hub gets a clean
# single-commit snapshot with no upstream history, and the deploy happens in a
# throwaway worktree so your checkout is never touched — which matters when a
# backtest is mid-run writing into data/processed.
#
# The parquets go through Git LFS. This is not about size: the Hub's
# pre-receive hook rejects raw binary blobs outright, and it rejected these
# 96 KB files on the first deploy attempt. The pointer gate below catches a
# regression before a long upload rather than after.
set -euo pipefail
cd "$(dirname "$0")"

SPACE_URL="https://huggingface.co/spaces/JJ-JIN12345/qis-commodities"
HF_USER="JJ-JIN12345"
WT="$(mktemp -d)/hfdeploy"

# A bare `python` does not exist outside an activated venv, so prefer the repo
# venv, then python3, then python.
if [ -x .venv/bin/python ];                   then PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1;      then PY=python3
elif command -v python  >/dev/null 2>&1;      then PY=python
else echo "ERROR: no python interpreter found" >&2; exit 1
fi

DO_COMMIT=0
SKIP_SYNTAX=0
for arg in "$@"; do
    case "$arg" in
        --commit)            DO_COMMIT=1 ;;
        --skip-syntax-check) SKIP_SYNTAX=1 ;;
        *) echo "unknown flag: $arg (want --commit / --skip-syntax-check)" >&2; exit 2 ;;
    esac
done

if [ "$DO_COMMIT" = "1" ]; then
    # Only the whitelisted viewer artifacts in .gitignore can land here.
    git add data/processed 2>/dev/null || true
    if ! git diff --cached --quiet; then
        git commit -m "chore(data): refresh viewer artifacts for Space deploy"
    else
        echo "nothing new to commit"
    fi
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: working tree is dirty. Commit first, or run with --commit." >&2
    exit 1
fi

# Parse every file the Space executes under the Python the Space actually runs.
# The dev venv may be newer, in which case compiling locally proves nothing:
# PEP 701 f-strings parse on 3.12 and raise on 3.11. The tree is clean by the
# check above, so the working copy == what gets pushed.
if [ "$SKIP_SYNTAX" = "0" ]; then
    PYVER=$(grep -oP '^FROM python:\K[0-9]+\.[0-9]+' Dockerfile)
    LOCALVER=$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    CHECK='
import ast, pathlib, sys
bad = []
for p in sorted(list(pathlib.Path("app").rglob("*.py")) + list(pathlib.Path("src").rglob("*.py"))):
    try:
        ast.parse(p.read_text(), str(p))
    except SyntaxError as e:
        bad.append("  %s:%s  %s" % (p, e.lineno, e.msg))
if bad:
    sys.stderr.write("ERROR: these files do not parse under Python %d.%d:\n%s\n"
                     % (sys.version_info[0], sys.version_info[1], "\n".join(bad)))
    raise SystemExit(1)
'
    if [ "$LOCALVER" = "$PYVER" ]; then
        "$PY" -c "$CHECK"
    elif command -v docker >/dev/null 2>&1; then
        docker run --rm -v "$PWD":/w -w /w "python:$PYVER-slim" python -c "$CHECK"
    else
        echo "ERROR: cannot check syntax for Python $PYVER (venv is $LOCALVER, no docker)." >&2
        echo "       Match the venv to $PYVER, install docker, or --skip-syntax-check." >&2
        exit 1
    fi
    echo "syntax OK for Python $PYVER"
fi

: "${HF_API_KEY:=$(grep -oP '^HF_API_KEY=\K.*' .env 2>/dev/null | tr -d '"'"'"'' || true)}"
if [ -z "${HF_API_KEY:-}" ]; then
    echo "ERROR: HF_API_KEY not found in environment or .env" >&2
    echo "       Add HF_API_KEY=hf_... to .env, or export it before running." >&2
    exit 1
fi
export HF_API_KEY

ASKPASS="$(mktemp)"
cat > "$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  Username*) echo "$HF_USER_ENV" ;;
  Password*) echo "$HF_API_KEY" ;;
esac
EOF
chmod +x "$ASKPASS"
export HF_USER_ENV="$HF_USER"

HEADSHA=$(git rev-parse HEAD)
echo "deploying $HEADSHA -> $SPACE_URL"

# Clear any leftover deploy worktree from an interrupted run FIRST. A branch
# checked out in a worktree cannot be deleted, so `git branch -D` alone fails
# and the whole deploy aborts.
git worktree list --porcelain \
    | awk '/^worktree /{p=$2} /^branch refs\/heads\/hf-main$/{print p}' \
    | while read -r old; do git worktree remove --force "$old" 2>/dev/null || true; done
git worktree prune
git branch -D hf-main 2>/dev/null || true
git worktree add --detach "$WT" "$HEADSHA" >/dev/null
trap 'git worktree remove --force "$WT" 2>/dev/null || true; rm -f "$ASKPASS"' EXIT

(
    cd "$WT"
    git checkout -q --orphan hf-main

    # Publish only what the Space executes. Throwaway worktree, so these
    # deletions never touch your checkout.
    #
    # tests/ and notebooks/ are never run here. src/data/ and src/reporting/
    # stay: src.config lives under src/ and the package imports must resolve,
    # but nothing under them executes on the Space (no API keys are set).
    rm -rf tests notebooks specs .specify .claude
    rm -f  Sys_Commodity.pdf reference_paper.pdf

    # Belt-and-braces: the reference figures are gitignored, so they should
    # never be in the commit at all. Fail loudly if one ever slips through.
    if [ -e data/reference/benchmark.json ]; then
        echo "ERROR: data/reference/benchmark.json is present — third-party figures must not ship." >&2
        exit 1
    fi

    git add -A
    # Unchanged files skip the LFS clean filter, so force it across the tree —
    # without this, parquets already committed as raw blobs stay raw and the
    # Hub rejects the push.
    git add --renormalize .
    git commit -q -m "Deploy: Sys Commodities Research Demo ($(echo "$HEADSHA" | cut -c1-8))"

    # Fail loudly rather than let the Hub reject the push after a long upload.
    raw=$(git ls-files | grep -iE '\.(parquet|png|jpg|jpeg|db|h5|joblib|npy|pkl)$' \
          | while read -r f; do
                git show ":$f" | head -c 40 | grep -q git-lfs || echo "  $f"
            done)
    if [ -n "$raw" ]; then
        echo "ERROR: these binaries are not LFS pointers:" >&2
        echo "$raw" >&2
        exit 1
    fi

    GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 \
        git push "$SPACE_URL" hf-main:main --force
)

echo
echo "pushed. the Space rebuilds automatically (~2-4 min):"
echo "  $SPACE_URL"
