"""
Import/export workspace tasks as markdown.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from aider_vision_core.workspace_todos import ChecklistItem, TodoItem, TodoStore, _now_iso

_TASK_HEADER = re.compile(r"^#\s+(.+)$")
_META_ID = re.compile(r"^id:\s*(\S+)\s*$", re.I)
_META_STATUS = re.compile(r"^status:\s*(\S+)\s*$", re.I)
_CHECKLIST_ITEM = re.compile(r"^-\s*\[([ xX])\]\s*(.*)$")


def export_markdown(store: TodoStore) -> str:
    blocks: list[str] = []
    for item in store.todos:
        lines = [
            f"# {item.title}",
            f"id: {item.id}",
            f"status: {item.status}",
            "",
            "## Specification",
            item.spec.strip() or "",
        ]
        if item.checklist:
            lines += ["", "## Checklist"]
            for c in item.checklist:
                mark = "x" if c.done else " "
                lines.append(f"- [{mark}] {c.text}")
        if item.links:
            lines += ["", "## Links"]
            for link in item.links:
                lines.append(f"- {link}")
        blocks.append("\n".join(lines))
    active = f"activeId: {store.active_id}\n\n" if store.active_id else ""
    body = "\n---\n\n".join(blocks)
    return f"# Aider Vision Tasks\n\n{active}{body}\n" if body else "# Aider Vision Tasks\n\n"


def _parse_checklist_line(line: str) -> ChecklistItem | None:
    m = _CHECKLIST_ITEM.match(line.strip())
    if not m:
        return None
    return ChecklistItem(
        id=uuid.uuid4().hex[:8],
        text=m.group(2).strip(),
        done=m.group(1).lower() == "x",
    )


def import_markdown(text: str, existing: TodoStore | None = None, *, merge: bool = False) -> TodoStore:
    store = existing if merge and existing else TodoStore()
    if not merge:
        store = TodoStore()

    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    active_from_header: str | None = None
    if lines and lines[0].strip().lower().startswith("# aider vision tasks"):
        i = 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines) and lines[i].strip().lower().startswith("activeid:"):
            active_from_header = lines[i].split(":", 1)[1].strip() or None
            i += 1

    current: dict[str, Any] | None = None
    section: str | None = None
    spec_lines: list[str] = []

    def flush_task() -> None:
        nonlocal current, spec_lines, section
        if not current or not current.get("title"):
            current = None
            spec_lines = []
            section = None
            return
        item = TodoItem(
            id=str(current.get("id") or uuid.uuid4().hex),
            title=str(current["title"]),
            spec="\n".join(spec_lines).strip(),
            status=current.get("status") or "open",
            links=list(current.get("links") or []),
            checklist=list(current.get("checklist") or []),
        )
        store.todos.append(item)
        current = None
        spec_lines = []
        section = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "---":
            flush_task()
            i += 1
            continue

        hm = _TASK_HEADER.match(stripped)
        if hm and not stripped.lower().startswith("# aider vision"):
            flush_task()
            current = {"title": hm.group(1).strip(), "checklist": [], "links": []}
            section = None
            spec_lines = []
            i += 1
            continue

        if current is None:
            i += 1
            continue

        mid = _META_ID.match(stripped)
        if mid:
            current["id"] = mid.group(1)
            i += 1
            continue
        ms = _META_STATUS.match(stripped)
        if ms:
            st = ms.group(1).lower()
            if st in ("open", "in_progress", "done", "cancelled"):
                current["status"] = st
            i += 1
            continue

        if stripped.lower() == "## specification":
            section = "spec"
            spec_lines = []
            i += 1
            continue
        if stripped.lower() == "## checklist":
            section = "checklist"
            i += 1
            continue
        if stripped.lower() == "## links":
            section = "links"
            i += 1
            continue

        if section == "spec":
            if stripped.lower().startswith("## "):
                section = None
                continue
            spec_lines.append(line)
        elif section == "checklist":
            if stripped.lower().startswith("## "):
                section = None
                continue
            entry = _parse_checklist_line(stripped)
            if entry:
                current["checklist"].append(entry)
        elif section == "links":
            if stripped.lower().startswith("## "):
                section = None
                continue
            if stripped.startswith("- "):
                current["links"].append(stripped[2:].strip())

        i += 1

    flush_task()

    if active_from_header and any(t.id == active_from_header for t in store.todos):
        store.active_id = active_from_header

    return store
