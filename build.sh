#!/usr/bin/env bash
# Release helper: commit release metadata, tag, push, build sdist/wheel, upload to PyPI.
#
# Usage:
#   ./build.sh v0.90.10
#   ./build.sh v0.90.10 --no-upload    # tag + push + build only
#   ./build.sh v0.90.10 --yes          # non-interactive (CI); fails if tree is dirty
#
# Requires: git, python3.14 (or PYTHON=python3.12), build, twine; PyPI credentials for upload.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VERSION=""
UPLOAD=1
ASSUME_YES=0

# setuptools-scm release metadata (allowed dirty paths without prompting)
VERSION_FILES=(
  "aider_vision_core.egg-info/PKG-INFO"
  "aider_vision_core.egg-info/SOURCES.txt"
  "aider_vision_core/_version.py"
)

usage() {
  echo "Usage: $0 <version-tag> [--no-upload] [--yes]" >&2
  echo "  version-tag   e.g. v0.90.10 or v0.90.9.dev0" >&2
  exit 1
}

die() {
  echo "error: $*" >&2
  exit 1
}

confirm() {
  local prompt="$1"
  if (( ASSUME_YES )); then
    return 0
  fi
  local ans
  read -r -p "${prompt} [y/N] " ans
  ans="$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')"
  [[ "$ans" == "y" || "$ans" == "yes" ]]
}

# First path from a porcelain line (handles rename "old -> new").
porcelain_path() {
  local rest="${1:3}"
  rest="${rest#\"}"
  rest="${rest%\"}"
  if [[ "$rest" == *" -> "* ]]; then
    echo "${rest%% -> *}"
  else
    echo "${rest%% *}"
  fi
}

is_version_file() {
  local path="$1"
  local f
  for f in "${VERSION_FILES[@]}"; do
    [[ "$path" == "$f" ]] && return 0
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-upload) UPLOAD=0; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      [[ -z "$VERSION" ]] || die "unexpected extra argument: $1 (version already set to ${VERSION})"
      VERSION="$1"
      shift
      ;;
  esac
done

[[ -n "$VERSION" ]] || usage

if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]]; then
  die "version must look like v0.90.10 or v0.90.9.dev0 (got: ${VERSION})"
fi

PEP440_VERSION="${VERSION#v}"

command -v git >/dev/null 2>&1 || die "git not found"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git repository"

PYTHON="${PYTHON:-python3.14}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi
command -v "$PYTHON" >/dev/null 2>&1 || die "python not found (set PYTHON=...)"

if git rev-parse "$VERSION" >/dev/null 2>&1; then
  die "tag ${VERSION} already exists locally"
fi

if git ls-remote --exit-code --tags origin "$VERSION" >/dev/null 2>&1; then
  die "tag ${VERSION} already exists on origin"
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" && "$BRANCH" != "master" ]]; then
  echo "warning: on branch '${BRANCH}', not main/master" >&2
  confirm "Continue anyway?" || die "aborted"
fi

echo "Checking for uncommitted changes..."
OTHER_LINES=()
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  path="$(porcelain_path "$line")"
  if is_version_file "$path"; then
    continue
  fi
  OTHER_LINES+=("$line")
done < <(git status --porcelain 2>/dev/null || true)

if ((${#OTHER_LINES[@]} > 0)); then
  echo "Uncommitted changes outside release metadata:" >&2
  printf '  %s\n' "${OTHER_LINES[@]}" >&2
  echo >&2
  if (( ASSUME_YES )); then
    die "working tree is dirty; commit or stash other changes, or run without --yes"
  fi
  if confirm "Commit these changes now before release?"; then
    git add -A
    DEFAULT_MSG="chore: prepare ${VERSION}"
    if ! confirm "Use default commit message: \"${DEFAULT_MSG}\"?"; then
      read -r -p "Commit message: " COMMIT_MSG
      [[ -n "${COMMIT_MSG:-}" ]] || die "empty commit message"
    else
      COMMIT_MSG="$DEFAULT_MSG"
    fi
    git commit -m "$COMMIT_MSG"
    echo "Committed other changes."
  else
    die "aborted — commit or stash changes before releasing"
  fi
fi

echo "Regenerating version metadata for ${VERSION}..."
export SETUPTOOLS_SCM_PRETEND_VERSION="$PEP440_VERSION"
"$PYTHON" - <<'PY' || die "failed to write aider_vision_core/_version.py"
import os
from pathlib import Path

try:
    from setuptools_scm import get_version
except ImportError:
    raise SystemExit("install setuptools_scm in your venv: pip install setuptools_scm")

root = Path(".").resolve()
version = get_version(
    root=str(root),
    version=os.environ["SETUPTOOLS_SCM_PRETEND_VERSION"],
)
out = root / "aider_vision_core" / "_version.py"
out.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
print(f"wrote {out} -> {version}")
PY

# Refresh egg-info so PKG-INFO / SOURCES.txt match the intended release.
"$PYTHON" -m pip install -q -e . --no-deps
unset SETUPTOOLS_SCM_PRETEND_VERSION

echo "Committing release metadata..."
for f in "${VERSION_FILES[@]}"; do
  if [[ -e "$f" ]]; then
    git add "$f"
  else
    echo "warning: ${f} not found, skipping" >&2
  fi
done

if git diff --cached --quiet; then
  echo "Release metadata already committed; nothing to commit."
else
  RELEASE_MSG="chore: release ${VERSION}"
  if (( ASSUME_YES )); then
    git commit -m "$RELEASE_MSG"
  elif confirm "Commit release metadata with message: \"${RELEASE_MSG}\"?"; then
    git commit -m "$RELEASE_MSG"
  else
    die "aborted before release metadata commit"
  fi
fi

# Final sanity check — only ignored version files may remain dirty.
REMAINING=()
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  path="$(porcelain_path "$line")"
  is_version_file "$path" && continue
  REMAINING+=("$line")
done < <(git status --porcelain 2>/dev/null || true)

if ((${#REMAINING[@]} > 0)); then
  echo "Still dirty after release commit:" >&2
  printf '  %s\n' "${REMAINING[@]}" >&2
  die "resolve remaining changes before tagging"
fi

echo "Tagging ${VERSION}..."
if (( ASSUME_YES )); then
  git tag "$VERSION"
else
  confirm "Create git tag ${VERSION}?" || die "aborted before tag"
  git tag "$VERSION"
fi

echo "Pushing to origin..."
if (( ASSUME_YES )); then
  git push origin HEAD
  git push origin "$VERSION"
else
  confirm "Push branch ${BRANCH} and tag ${VERSION} to origin?" || die "aborted before push"
  git push origin HEAD
  git push origin "$VERSION"
fi

echo "Cleaning build artifacts..."
rm -rf dist build *.egg-info aider_vision_core.egg-info

echo "Building sdist and wheel..."
"$PYTHON" -m pip install -q build
"$PYTHON" -m build

if (( UPLOAD )); then
  command -v twine >/dev/null 2>&1 || "$PYTHON" -m pip install -q twine
  echo "Uploading to PyPI..."
  if (( ASSUME_YES )); then
    "$PYTHON" -m twine upload dist/*
  else
    confirm "Upload dist/* to PyPI?" || die "aborted before upload (artifacts in dist/)"
    "$PYTHON" -m twine upload dist/*
  fi
  echo "Done. Released ${VERSION} to PyPI."
else
  echo "Done. Built dist/ for ${VERSION} (--no-upload)."
fi
