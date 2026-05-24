"""
Headless aider sessions for API / web frontends.
"""

from __future__ import annotations

import base64
import os
import shlex
from pathlib import Path
from typing import Any, Iterator

from aider_vision_core import models
from aider_vision_core.coders import Coder
from aider_vision_core.commands import Commands
from aider_vision_core.event_io import EventIO
from aider_vision_core.git_undo import undo_last_aider_commit_for_coder
from aider_vision_core.git_workspace import create_git_workspace
from aider_vision_core.workspace_todos import WorkspaceTodos, format_todo_context


class Session:
    """A headless coder session with event-streaming support."""

    def __init__(self, coder: Coder, io: EventIO):
        self.coder = coder
        self.io = io
        self.coder.yield_stream = True
        self.coder.stream = bool(coder.stream)
        self.coder.pretty = False
        self.coder.commands.io = io

    @classmethod
    def create(
        cls,
        workspace_dir: str,
        files: list[str] | None = None,
        model: str | None = None,
        *,
        yes: bool = False,
        stream: bool = True,
        auto_commits: bool = True,
        dirty_commits: bool = True,
        dry_run: bool = False,
        map_tokens: int | None = None,
        on_event=None,
        echo_to_console: bool = False,
    ) -> Session:
        """
        Create a session rooted at ``workspace_dir``.

        ``files`` are optional paths (absolute or relative) to add to the chat.
        """
        workspace = Path(workspace_dir).resolve()
        if not workspace.is_dir():
            raise FileNotFoundError(f"Workspace not found: {workspace}")

        from aider_vision_core.vision_runtime import configure_vision_runtime, purge_legacy_tag_caches

        configure_vision_runtime()
        purge_legacy_tag_caches(workspace)

        prev_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            io = EventIO(yes=yes, pretty=False, on_event=on_event, echo_to_console=echo_to_console)
            model_name = model or models.DEFAULT_MODEL_NAME
            main_model = models.Model(model_name)

            fnames = [str(Path(f).resolve()) for f in (files or [])]

            repo = None
            try:
                repo = create_git_workspace(
                    io,
                    fnames if fnames else [str(workspace)],
                    str(workspace),
                    models=main_model.commit_message_models(),
                )
            except FileNotFoundError:
                pass

            if map_tokens is None:
                map_tokens = main_model.get_repo_map_tokens()

            commands = Commands(io, None)
            coder = Coder.create(
                main_model=main_model,
                io=io,
                repo=repo,
                fnames=fnames,
                stream=stream and main_model.streaming,
                auto_commits=auto_commits,
                dirty_commits=dirty_commits,
                dry_run=dry_run,
                map_tokens=map_tokens,
                commands=commands,
                use_git=repo is not None,
            )
            return cls(coder, io)
        finally:
            os.chdir(prev_cwd)

    def run_message(
        self,
        message: str,
        *,
        preproc: bool = True,
        active_todo_id: str | None = None,
        inject_todo_spec: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Process one user message; yield event dicts (tokens, tool output, done).

        The final event is always ``{"type": "done", ...}``.
        When ``active_todo_id`` is set, ``done`` includes that id and turn links are
        appended to the task in ``.aider-vision/todos.json``.
        """
        turn_todo_id: str | None = None
        user_text = message
        if active_todo_id:
            todos = WorkspaceTodos(self.coder.root)
            store = todos.load()
            item = todos.find(store, active_todo_id)
            if item:
                turn_todo_id = item.id
                if inject_todo_spec:
                    user_text = format_todo_context(item, store=store) + message

        self.io.emit("user_message", text=user_text)
        assistant_text = []

        try:
            self.coder.init_before_message()
            self.io.user_input(user_text)

            user_msg = user_text
            if preproc:
                user_msg = self.coder.preproc_user_input(user_text)

            if user_msg is None:
                for event in self.io.drain_events():
                    yield event
                yield self.io.emit("done", assistant_text="")
                return

            for chunk in self.coder.send_message(user_msg):
                for event in self.io.drain_events():
                    yield event
                if chunk:
                    assistant_text.append(chunk)
                    event = self.io.emit("token", text=chunk)
                    yield event

            for event in self.io.drain_events():
                yield event

            edited = sorted(self.coder.aider_edited_files or [])
            payload: dict[str, Any] = {
                "assistant_text": "".join(assistant_text),
                "edited_files": edited,
            }
            if self.coder.last_aider_commit_hash:
                payload["commit_hash"] = self.coder.last_aider_commit_hash
                payload["commit_message"] = self.coder.last_aider_commit_message
            if self.coder.aider_commit_stack:
                payload["commits"] = self.coder.aider_commit_stack[-1]

            if turn_todo_id:
                payload["active_todo_id"] = turn_todo_id
                links: list[str] = list(edited)
                if self.coder.last_aider_commit_hash:
                    links.append(f"commit:{self.coder.last_aider_commit_hash}")
                WorkspaceTodos(self.coder.root).append_links(links, todo_id=turn_todo_id)

            yield self.io.emit("done", **payload)
        except BrokenPipeError as err:
            yield self.io.emit("error", text=str(err))
            yield self.io.emit("done", assistant_text="".join(assistant_text), error=True)
        except Exception as err:
            yield self.io.emit("error", text=str(err))
            yield self.io.emit("done", assistant_text="".join(assistant_text), error=True)

    def add_files(self, paths: list[str]) -> list[dict[str, Any]]:
        """
        Add workspace files (e.g. images) to the chat without running the LLM.

        Paths may be absolute or relative to the session workspace.
        Returns drained IO events (tool_output, tool_error, etc.).
        """
        if not paths:
            return []

        workspace = Path(self.coder.root).resolve()
        quoted: list[str] = []
        for raw in paths:
            p = Path(raw)
            if not p.is_absolute():
                p = workspace / p
            p = p.resolve()
            if not p.is_file():
                self.io.tool_error(f"Not a file: {p}")
                continue
            try:
                rel = p.relative_to(workspace)
                quoted.append(shlex.quote(str(rel).replace("\\", "/")))
            except ValueError:
                quoted.append(shlex.quote(str(p)))

        if quoted:
            self.coder.commands.cmd_add(" ".join(quoted))

        return self.io.drain_events()

    def stage_uploaded_file(self, filename: str, content: bytes) -> Path:
        """Write bytes under ``.aider-vision/attachments/`` in the workspace."""
        workspace = Path(self.coder.root).resolve()
        attach_dir = workspace / ".aider-vision" / "attachments"
        attach_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(filename).name or "upload"
        dest = attach_dir / safe_name
        stem = dest.stem
        suffix = dest.suffix
        n = 1
        while dest.exists():
            dest = attach_dir / f"{stem}-{n}{suffix}"
            n += 1
        dest.write_bytes(content)
        return dest

    def upload_files(self, items: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
        """Save uploaded blobs to the workspace and add them to the chat."""
        paths: list[str] = []
        for name, data in items:
            if len(data) > 20 * 1024 * 1024:
                self.io.tool_error(f"File too large (max 20MB): {name}")
                continue
            dest = self.stage_uploaded_file(name, data)
            paths.append(str(dest))
        return self.add_files(paths) if paths else self.io.drain_events()

    @staticmethod
    def decode_upload(content_base64: str) -> bytes:
        raw = content_base64.strip()
        if "," in raw and raw.startswith("data:"):
            raw = raw.split(",", 1)[1]
        return base64.b64decode(raw, validate=False)

    def undo(self) -> list[dict[str, Any]]:
        """Undo the last aider commit batch. Returns drained IO events."""
        undo_last_aider_commit_for_coder(self.coder, self.io)
        return self.io.drain_events()
