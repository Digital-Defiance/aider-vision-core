#!/usr/bin/env python3
"""
CI / dev audit: catch regressions from the aider → aider_vision_core rename.

Usage:
    python scripts/audit_rename_compat.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "aider_vision_core"
SKIP_DIRS = {
    "website",
    "__pycache__",
    ".git",
}
SKIP_FILES = {
    "audit_rename_compat.py",
}

# `from aider.` / `import aider` but not aider_vision_core / aiderignore / …
BAD_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+aider(?!_vision_core|ignore|_edited|_commit|@)",
)
# tqdm( in production code — allow gui_progress + search_replace __main__
BAD_TQDM = re.compile(r"\btqdm\s*\(")
ALLOW_TQDM = {
    PKG / "gui_progress.py",
    PKG / "coders" / "search_replace.py",
}
# resources.files(__package__) under repomap breaks query paths
BAD_RESOURCES = re.compile(r"resources\.files\(\s*__package__\s*\)")


def iter_py_files() -> list[Path]:
    out: list[Path] = []
    for path in PKG.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        out.append(path)
    return sorted(out)


def audit() -> list[str]:
    errors: list[str] = []
    for path in iter_py_files():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if BAD_IMPORT.search(line):
                errors.append(f"{rel}:{i}: legacy import of package 'aider': {line.strip()}")
            if BAD_RESOURCES.search(line):
                errors.append(f"{rel}:{i}: use resources.files('aider_vision_core'), not __package__")
        if path in ALLOW_TQDM:
            continue
        if path.name == "repomap.py":
            continue  # uses progress_iter
        for i, line in enumerate(text.splitlines(), start=1):
            if BAD_TQDM.search(line) and "progress_iter" not in line:
                errors.append(f"{rel}:{i}: use progress_iter() or gui_progress in headless paths: {line.strip()}")

    repomap = PKG / "repomap.py"
    body = repomap.read_text(encoding="utf-8")
    if "vision_runtime" not in body or "REPO_MAP_CACHE_VERSION" not in body:
        errors.append("repomap.py: must use vision_runtime.REPO_MAP_CACHE_VERSION and purge_legacy_tag_caches")

    return errors


def main() -> int:
    errors = audit()
    if errors:
        print("audit_rename_compat FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("audit_rename_compat OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
