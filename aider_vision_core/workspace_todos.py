"""
Workspace task list persisted in ``.aider-vision/todos.json``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

TodoStatus = Literal["open", "in_progress", "done", "cancelled"]

TODO_TEMPLATES: dict[str, str] = {
    "feature": (
        "## Goal\n\n"
        "## Requirements\n\n"
        "## Acceptance criteria\n"
        "- [ ] \n"
    ),
    "bugfix": (
        "## Problem\n\n"
        "## Root cause\n\n"
        "## Fix verification\n"
        "- [ ] Repro fixed\n"
        "- [ ] Tests pass\n"
    ),
    "refactor": (
        "## Scope\n\n"
        "## Non-goals\n\n"
        "## Acceptance criteria\n"
        "- [ ] Behavior unchanged\n"
        "- [ ] \n"
    ),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def apply_template(name: str) -> str:
    return TODO_TEMPLATES.get((name or "").strip().lower(), "")


@dataclass
class ChecklistItem:
    id: str
    text: str
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ChecklistItem:
        return cls(
            id=str(raw.get("id") or uuid.uuid4().hex[:8]),
            text=str(raw.get("text") or ""),
            done=bool(raw.get("done")),
        )


@dataclass
class TodoItem:
    id: str
    title: str
    spec: str = ""
    status: TodoStatus = "open"
    links: list[str] = field(default_factory=list)
    checklist: list[ChecklistItem] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checklist"] = [c.to_dict() for c in self.checklist]
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TodoItem:
        checklist = [ChecklistItem.from_dict(c) for c in raw.get("checklist") or []]
        status = raw.get("status")
        valid = status if status in ("open", "in_progress", "done", "cancelled") else "open"
        return cls(
            id=str(raw.get("id") or uuid.uuid4().hex),
            title=str(raw.get("title") or "Untitled"),
            spec=str(raw.get("spec") or ""),
            status=valid,
            links=list(raw.get("links") or []),
            checklist=checklist,
            created_at=str(raw.get("created_at") or _now_iso()),
            updated_at=str(raw.get("updated_at") or _now_iso()),
        )


@dataclass
class TodoStore:
    version: int = 1
    active_id: str | None = None
    todos: list[TodoItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "activeId": self.active_id,
            "todos": [t.to_dict() for t in self.todos],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TodoStore:
        items = [TodoItem.from_dict(t) for t in raw.get("todos") or []]
        active = raw.get("activeId") or raw.get("active_id")
        if active and not any(t.id == active for t in items):
            active = None
        return cls(version=int(raw.get("version") or 1), active_id=active, todos=items)


def checklist_all_done(item: TodoItem) -> bool:
    if not item.checklist:
        return False
    return all(c.text.strip() and c.done for c in item.checklist)


def format_todo_context(item: TodoItem) -> str:
    spec = item.spec.strip() or "(No spec yet — add requirements and acceptance criteria.)"
    lines = [
        f"[Active task: {item.title} · id {item.id[:8]}]",
        "",
        "## Specification",
        spec,
    ]
    if item.checklist:
        lines += ["", "## Checklist"]
        for entry in item.checklist:
            mark = "x" if entry.done else " "
            lines.append(f"- [{mark}] {entry.text}")
    lines += ["", "---", ""]
    return "\n".join(lines)


class WorkspaceTodos:
    def __init__(self, workspace_dir: str | Path):
        self.root = Path(workspace_dir).resolve()
        self.path = self.root / ".aider-vision" / "todos.json"

    def load(self) -> TodoStore:
        if not self.path.is_file():
            return TodoStore()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return TodoStore()
        if not isinstance(data, dict):
            return TodoStore()
        return TodoStore.from_dict(data)

    def save(self, store: TodoStore) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(store.to_dict(), indent=2, ensure_ascii=False)
        self.path.write_text(payload + "\n", encoding="utf-8")

    def find(self, store: TodoStore, token: str) -> TodoItem | None:
        token = token.strip()
        if not token:
            return None
        for item in store.todos:
            if item.id == token or item.id.startswith(token):
                return item
        lower = token.lower()
        for item in store.todos:
            if item.title.lower() == lower:
                return item
        return None

    def get(self, todo_id: str) -> TodoItem:
        store = self.load()
        item = self.find(store, todo_id)
        if not item:
            raise ValueError(f"Unknown task: {todo_id}")
        return item

    def add(self, title: str, spec: str = "", *, template: str | None = None) -> TodoItem:
        store = self.load()
        body = spec.strip() or apply_template(template or "")
        item = TodoItem(id=uuid.uuid4().hex, title=title.strip() or "Untitled", spec=body)
        store.todos.insert(0, item)
        self.save(store)
        return item

    def update(
        self,
        todo_id: str,
        *,
        title: str | None = None,
        spec: str | None = None,
        status: TodoStatus | None = None,
        links: list[str] | None = None,
        checklist: list[ChecklistItem] | None = None,
        auto_complete_checklist: bool = True,
    ) -> tuple[TodoItem, bool]:
        """Returns ``(item, auto_completed)``."""
        store = self.load()
        item = self.find(store, todo_id)
        if not item:
            raise ValueError(f"Unknown task: {todo_id}")
        auto_completed = False
        if title is not None:
            item.title = title.strip() or "Untitled"
        if spec is not None:
            item.spec = spec
        if status is not None:
            item.status = status
        if links is not None:
            item.links = list(links)
        if checklist is not None:
            item.checklist = checklist
        if (
            auto_complete_checklist
            and checklist is not None
            and checklist_all_done(item)
            and item.status not in ("done", "cancelled")
        ):
            item.status = "done"
            auto_completed = True
            if store.active_id == item.id:
                store.active_id = None
        item.updated_at = _now_iso()
        if status == "done" and store.active_id == item.id:
            store.active_id = None
        self.save(store)
        return item, auto_completed

    def import_markdown(self, text: str, *, merge: bool = False) -> TodoStore:
        from aider_vision_core.todo_markdown import import_markdown

        store = import_markdown(text, self.load() if merge else None, merge=merge)
        self.save(store)
        return store

    def export_markdown(self) -> str:
        from aider_vision_core.todo_markdown import export_markdown

        return export_markdown(self.load())

    def delete(self, todo_id: str) -> None:
        store = self.load()
        before = len(store.todos)
        store.todos = [t for t in store.todos if t.id != todo_id]
        if len(store.todos) == before:
            raise ValueError(f"Unknown task: {todo_id}")
        if store.active_id == todo_id:
            store.active_id = None
        self.save(store)

    def set_active(self, todo_id: str | None) -> TodoStore:
        store = self.load()
        if todo_id:
            item = self.find(store, todo_id)
            if not item:
                raise ValueError(f"Unknown task id: {todo_id}")
            store.active_id = item.id
            if item.status == "open":
                item.status = "in_progress"
                item.updated_at = _now_iso()
        else:
            store.active_id = None
        self.save(store)
        return store

    def mark_done(self, token: str) -> TodoItem:
        store = self.load()
        item = self.find(store, token)
        if not item:
            raise ValueError(f"Unknown task: {token}")
        item.status = "done"
        item.updated_at = _now_iso()
        if store.active_id == item.id:
            store.active_id = None
        self.save(store)
        return item

    def append_links(self, links: list[str], *, todo_id: str | None = None) -> None:
        if not links:
            return
        store = self.load()
        target = todo_id or store.active_id
        if not target:
            return
        item = self.find(store, target)
        if not item:
            return
        seen = set(item.links)
        for link in links:
            s = str(link).strip()
            if s and s not in seen:
                item.links.append(s)
                seen.add(s)
        item.updated_at = _now_iso()
        self.save(store)
