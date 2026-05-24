"""
Headless aider sessions for API / web frontends.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

from aider_vision_core import models
from aider_vision_core.coders import Coder
from aider_vision_core.commands import Commands
from aider_vision_core.event_io import EventIO
from aider_vision_core.git_undo import undo_last_aider_commit_for_coder
from aider_vision_core.git_workspace import create_git_workspace


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
        yes: bool = True,
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

        prev_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            io = EventIO(yes=yes, pretty=False, on_event=on_event, echo_to_console=echo_to_console)
            model_name = model or models.DEFAULT_MODEL_NAME
            main_model = models.Model(model_name)

            fnames = [str(Path(f).resolve()) for f in (files or [])]
            if not fnames:
                fnames = [str(workspace)]

            repo = None
            try:
                repo = create_git_workspace(
                    io,
                    fnames,
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

    def run_message(self, message: str, *, preproc: bool = True) -> Iterator[dict[str, Any]]:
        """
        Process one user message; yield event dicts (tokens, tool output, done).

        The final event is always ``{"type": "done", ...}``.
        """
        self.io.emit("user_message", text=message)
        assistant_text = []

        try:
            self.coder.init_before_message()
            self.io.user_input(message)

            user_msg = message
            if preproc:
                user_msg = self.coder.preproc_user_input(message)

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

            yield self.io.emit("done", **payload)
        except BrokenPipeError as err:
            yield self.io.emit("error", text=str(err))
            yield self.io.emit("done", assistant_text="".join(assistant_text), error=True)
        except Exception as err:
            yield self.io.emit("error", text=str(err))
            yield self.io.emit("done", assistant_text="".join(assistant_text), error=True)

    def undo(self) -> list[dict[str, Any]]:
        """Undo the last aider commit batch. Returns drained IO events."""
        undo_last_aider_commit_for_coder(self.coder, self.io)
        return self.io.drain_events()
