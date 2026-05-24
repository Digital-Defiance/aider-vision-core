#!/usr/bin/env bash
# Pin aider-vision to a released aider-vision-core version on PyPI and install into
# the parent app's .venv (not aider-vision-core/.venv).
#
# Usage:
#   ./scripts/sync_aider_vision.sh 0.90.10.dev0
#   ./scripts/sync_aider_vision.sh v0.90.10.dev0 --commit
#   AIDER_VISION_ROOT=/path/to/aider-vision ./scripts/sync_aider_vision.sh 0.90.10.dev0

set -euo pipefail

CORE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSUME_YES=0
DO_COMMIT=0
SKIP_PIP=0
VERSION_ARG=""

usage() {
  echo "Usage: $0 <version> [--commit] [--yes] [--skip-pip]" >&2
  echo "  version     PEP 440 or tag, e.g. 0.90.10.dev0 or v0.90.10.dev0" >&2
  echo "  --commit    commit requirements-core.txt + submodule pointer in aider-vision" >&2
  echo "  AIDER_VISION_ROOT  override parent app path (default: ../aider-vision)" >&2
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

resolve_vision_root() {
  if [[ -n "${AIDER_VISION_ROOT:-}" ]]; then
    echo "$(cd "$AIDER_VISION_ROOT" && pwd)"
    return
  fi
  local parent
  parent="$(cd "${CORE_ROOT}/.." && pwd)"
  if [[ -f "${parent}/.gitmodules" ]] && [[ -d "${parent}/aider-vision-core" ]]; then
    echo "$parent"
    return
  fi
  die "could not find aider-vision parent (set AIDER_VISION_ROOT)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit) DO_COMMIT=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --skip-pip) SKIP_PIP=1; shift ;;
    -h|--help) usage ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      [[ -z "$VERSION_ARG" ]] || die "unexpected argument: $1"
      VERSION_ARG="$1"
      shift
      ;;
  esac
done

[[ -n "$VERSION_ARG" ]] || usage

VERSION_TAG="$VERSION_ARG"
PEP440_VERSION="${VERSION_TAG#v}"
if [[ ! "$PEP440_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]]; then
  die "invalid version: ${VERSION_ARG}"
fi
if [[ "$VERSION_TAG" != v* ]]; then
  VERSION_TAG="v${PEP440_VERSION}"
fi

VISION_ROOT="$(resolve_vision_root)"
REQ_FILE="${VISION_ROOT}/requirements-core.txt"
SUBMODULE="${VISION_ROOT}/aider-vision-core"
VENV="${VISION_ROOT}/.venv"

echo "Parent app: ${VISION_ROOT}"
echo "Pin: aider-vision-core==${PEP440_VERSION}"

cat >"$REQ_FILE" <<EOF
# Pinned PyPI release of the engine (updated by aider-vision-core/scripts/sync_aider_vision.sh).
# Dev default: editable submodule via \`source activate.sh\` in aider-vision.
# After a core release: ./build.sh ${VERSION_TAG} --sync-vision
aider-vision-core==${PEP440_VERSION}
EOF
echo "Wrote ${REQ_FILE}"

if [[ -d "$SUBMODULE/.git" ]]; then
  echo "Checking out submodule at tag ${VERSION_TAG}..."
  git -C "$SUBMODULE" fetch origin tag "$VERSION_TAG" 2>/dev/null || true
  if git -C "$SUBMODULE" rev-parse "$VERSION_TAG" >/dev/null 2>&1; then
    git -C "$SUBMODULE" checkout "$VERSION_TAG"
  else
    echo "warning: tag ${VERSION_TAG} not found in submodule; requirements pin still updated" >&2
  fi
fi

if (( SKIP_PIP )); then
  echo "Skipping pip install (--skip-pip)."
else
  PYTHON="${VISION_PYTHON:-python3}"
  if [[ ! -d "$VENV" ]]; then
    echo "Creating ${VENV}..."
    "$PYTHON" -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
  echo "Installing into aider-vision .venv (not core/.venv)..."
  python -m pip install -q -U pip
  python -m pip install -q -U -r "$REQ_FILE"
  python -c "import aider_vision_core as c; print('aider_vision_core', c.__version__, 'at', c.__file__)"
  deactivate 2>/dev/null || true
fi

if (( DO_COMMIT )); then
  if ! git -C "$VISION_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "aider-vision is not a git repo; cannot --commit"
  fi
  MSG="chore: pin aider-vision-core==${PEP440_VERSION}"
  git -C "$VISION_ROOT" add requirements-core.txt
  if [[ -d "$SUBMODULE/.git" ]]; then
    git -C "$VISION_ROOT" add aider-vision-core
  fi
  if git -C "$VISION_ROOT" diff --cached --quiet; then
    echo "Nothing to commit in aider-vision."
  elif (( ASSUME_YES )) || confirm "Commit in aider-vision: \"${MSG}\"?"; then
    git -C "$VISION_ROOT" commit -m "$MSG"
    echo "Committed in aider-vision."
  else
    echo "Skipped commit; changes left staged/unstaged in aider-vision."
  fi
fi

echo "Done. Use: cd ${VISION_ROOT} && source activate.sh  (editable) or source .venv/bin/activate after PyPI install."
