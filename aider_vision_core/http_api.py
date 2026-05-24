"""
HTTP API for aider-vision (FastAPI + Server-Sent Events).

Run with::

    python scripts/vision_serve.py --workspace /path/to/repo

Or::

    uvicorn aider_vision_core.http_api:app --host 127.0.0.1 --port 8741
"""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from aider_vision_core.vision_runtime import configure_vision_runtime

configure_vision_runtime()

from aider_vision_core.git_undo import undo_last_aider_commit_for_coder
from aider_vision_core.http_auth import auth_enabled, configure_auth, get_token_from_env, verify_bearer
from aider_vision_core.session import Session
from aider_vision_core.workspace_todos import (
    TODO_TEMPLATES,
    ChecklistItem,
    TodoItem,
    TodoStore,
    WorkspaceTodos,
)


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    # When started via raw uvicorn, still honor AIDER_VISION_TOKEN if set.
    if get_token_from_env():
        configure_auth("127.0.0.1")
    yield


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        if not verify_bearer(request.headers.get("authorization")):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

app = FastAPI(
    title="aider-vision-core API",
    description="Headless aider-vision-core sessions for web and Rust clients",
    version="0.1.0",
    lifespan=_app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BearerAuthMiddleware)

_lock = threading.Lock()
_sessions: dict[str, Session] = {}


class CreateSessionRequest(BaseModel):
    workspace: str = Field(..., description="Absolute path to git workspace root")
    files: list[str] = Field(default_factory=list, description="Files to add to the chat")
    model: str | None = Field(default=None, description="LLM model name")
    stream: bool = True
    auto_yes: bool = Field(
        False,
        description="Auto-approve confirmations (non-interactive; use UI confirm API when false)",
    )
    auto_commits: bool = True
    dirty_commits: bool = True
    dry_run: bool = False


class ConfirmRequest(BaseModel):
    confirm_id: str = Field(..., min_length=1)
    answer: bool = Field(..., description="True to accept, False to decline")


class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    preproc: bool = True
    active_todo_id: str | None = Field(
        None,
        description="Workspace task id for this turn (links + optional spec inject)",
    )
    inject_todo_spec: bool = Field(
        False,
        description="When true with active_todo_id, prepend task spec to the message",
    )


class ChecklistItemModel(BaseModel):
    id: str
    text: str
    done: bool = False


class TodoItemModel(BaseModel):
    id: str
    title: str
    spec: str = ""
    requirements: str = ""
    design: str = ""
    tasks_md: str = ""
    depends_on: list[str] = Field(default_factory=list)
    status: str = "open"
    links: list[str] = Field(default_factory=list)
    checklist: list[ChecklistItemModel] = Field(default_factory=list)
    created_at: str
    updated_at: str


class TodoListResponse(BaseModel):
    version: int = 1
    active_id: str | None = Field(None, serialization_alias="activeId")
    todos: list[TodoItemModel]
    templates: list[str] = Field(
        default_factory=lambda: sorted(set(TODO_TEMPLATES) | set(SPEC_LAYER_TEMPLATES))
    )

    model_config = {"populate_by_name": True}


class CreateTodoRequest(BaseModel):
    title: str = Field(..., min_length=1)
    spec: str = ""
    template: str | None = None


class PatchTodoRequest(BaseModel):
    title: str | None = None
    spec: str | None = None
    status: str | None = None
    links: list[str] | None = None
    checklist: list[ChecklistItemModel] | None = None


class SetActiveTodoRequest(BaseModel):
    active_id: str | None = Field(None, serialization_alias="activeId")

    model_config = {"populate_by_name": True}


class PatchTodoResponse(BaseModel):
    item: TodoItemModel
    auto_completed: bool = False


class ImportTodosRequest(BaseModel):
    workspace: str = Field(..., min_length=1)
    markdown: str = Field(..., min_length=1)
    merge: bool = False


class AddFilesRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1, description="Absolute or workspace-relative file paths")


class UploadedFilePart(BaseModel):
    filename: str = Field(..., min_length=1)
    content_base64: str = Field(..., min_length=1)


class UploadFilesRequest(BaseModel):
    files: list[UploadedFilePart] = Field(..., min_length=1)


class AddFilesResponse(BaseModel):
    files_in_chat: list[str]
    events: list[dict[str, Any]] = Field(default_factory=list)


class SessionInfo(BaseModel):
    session_id: str
    workspace: str
    model: str
    files_in_chat: list[str]


class CommandInfo(BaseModel):
    name: str
    summary: str


class CommandListResponse(BaseModel):
    commands: list[CommandInfo]


def _sse_pack(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok", "auth_required": auth_enabled()}


@app.post("/sessions", response_model=SessionInfo)
def create_session(body: CreateSessionRequest):
    try:
        session = Session.create(
            body.workspace,
            files=body.files or None,
            model=body.model,
            stream=body.stream,
            yes=body.auto_yes,
            auto_commits=body.auto_commits,
            dirty_commits=body.dirty_commits,
            dry_run=body.dry_run,
        )
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    session_id = uuid.uuid4().hex
    with _lock:
        _sessions[session_id] = session

    return SessionInfo(
        session_id=session_id,
        workspace=body.workspace,
        model=session.coder.main_model.name,
        files_in_chat=session.coder.get_inchat_relative_files(),
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo)
def get_session(session_id: str):
    session = _get_session(session_id)
    return _session_info(session_id, session)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    with _lock:
        if session_id not in _sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        del _sessions[session_id]
    return {"deleted": session_id}


@app.get("/sessions/{session_id}/commands", response_model=CommandListResponse)
def list_commands(session_id: str):
    session = _get_session(session_id)
    commands = session.coder.commands.get_commands()
    items: list[CommandInfo] = []
    for cmd in sorted(commands):
        key = cmd[1:].replace("-", "_")
        method = getattr(session.coder.commands, f"cmd_{key}", None)
        summary = ""
        if method and method.__doc__:
            summary = method.__doc__.strip().split("\n")[0]
        items.append(CommandInfo(name=cmd, summary=summary))
    return CommandListResponse(commands=items)


def _workspace_todos(session: Session) -> WorkspaceTodos:
    return WorkspaceTodos(session.coder.root)


def _todos_for_workspace(workspace: str) -> WorkspaceTodos:
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"Not a directory: {workspace}")
    return WorkspaceTodos(root)


def _patch_todo_api(api: WorkspaceTodos, todo_id: str, body: PatchTodoRequest) -> PatchTodoResponse:
    checklist = None
    if body.checklist is not None:
        checklist = [
            ChecklistItem(id=c.id or uuid.uuid4().hex[:8], text=c.text, done=c.done)
            for c in body.checklist
        ]
    status = body.status
    if status is not None and status not in ("open", "in_progress", "done", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    try:
        item, auto_completed = api.update(
            todo_id,
            title=body.title,
            spec=body.spec,
            status=status,
            links=body.links,
            checklist=checklist,
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return PatchTodoResponse(item=_todo_item_model(item), auto_completed=auto_completed)


def _todo_item_model(item: TodoItem) -> TodoItemModel:
    return TodoItemModel(
        id=item.id,
        title=item.title,
        spec=item.spec,
        status=item.status,
        links=item.links,
        checklist=[ChecklistItemModel(id=c.id, text=c.text, done=c.done) for c in item.checklist],
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _todo_list_response(store: TodoStore) -> TodoListResponse:
    return TodoListResponse(
        version=store.version,
        active_id=store.active_id,
        todos=[_todo_item_model(t) for t in store.todos],
    )


@app.get("/workspaces/todos", response_model=TodoListResponse)
def list_workspace_todos(workspace: str):
    return _todo_list_response(_todos_for_workspace(workspace).load())


@app.post("/workspaces/todos", response_model=TodoItemModel)
def create_workspace_todo(workspace: str, body: CreateTodoRequest):
    api = _todos_for_workspace(workspace)
    item = api.add(body.title, body.spec, template=body.template)
    return _todo_item_model(item)


@app.patch("/workspaces/todos/{todo_id}", response_model=PatchTodoResponse)
def patch_workspace_todo(workspace: str, todo_id: str, body: PatchTodoRequest):
    return _patch_todo_api(_todos_for_workspace(workspace), todo_id, body)


@app.delete("/workspaces/todos/{todo_id}")
def delete_workspace_todo(workspace: str, todo_id: str):
    try:
        _todos_for_workspace(workspace).delete(todo_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return {"deleted": todo_id}


@app.put("/workspaces/todos/active", response_model=TodoListResponse)
def set_workspace_active_todo(workspace: str, body: SetActiveTodoRequest):
    try:
        store = _todos_for_workspace(workspace).set_active(body.active_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return _todo_list_response(store)


@app.get("/workspaces/todos/export")
def export_workspace_todos(workspace: str):
    md = _todos_for_workspace(workspace).export_markdown()
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@app.post("/workspaces/todos/import", response_model=TodoListResponse)
def import_workspace_todos(body: ImportTodosRequest):
    api = _todos_for_workspace(body.workspace)
    store = api.import_markdown(body.markdown, merge=body.merge)
    return _todo_list_response(store)


@app.get("/sessions/{session_id}/todos", response_model=TodoListResponse)
def list_session_todos(session_id: str):
    session = _get_session(session_id)
    return _todo_list_response(_workspace_todos(session).load())


@app.post("/sessions/{session_id}/todos", response_model=TodoItemModel)
def create_session_todo(session_id: str, body: CreateTodoRequest):
    session = _get_session(session_id)
    api = _workspace_todos(session)
    item = api.add(body.title, body.spec, template=body.template)
    return _todo_item_model(item)


@app.patch("/sessions/{session_id}/todos/{todo_id}", response_model=PatchTodoResponse)
def patch_session_todo(session_id: str, todo_id: str, body: PatchTodoRequest):
    session = _get_session(session_id)
    return _patch_todo_api(_workspace_todos(session), todo_id, body)


@app.delete("/sessions/{session_id}/todos/{todo_id}")
def delete_session_todo(session_id: str, todo_id: str):
    session = _get_session(session_id)
    try:
        _workspace_todos(session).delete(todo_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return {"deleted": todo_id}


@app.put("/sessions/{session_id}/todos/active", response_model=TodoListResponse)
def set_session_active_todo(session_id: str, body: SetActiveTodoRequest):
    session = _get_session(session_id)
    api = _workspace_todos(session)
    try:
        store = api.set_active(body.active_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return _todo_list_response(store)


def _session_info(session_id: str, session: Session) -> SessionInfo:
    return SessionInfo(
        session_id=session_id,
        workspace=session.coder.root,
        model=session.coder.main_model.name,
        files_in_chat=session.coder.get_inchat_relative_files(),
    )


@app.post("/sessions/{session_id}/files", response_model=AddFilesResponse)
def add_session_files(session_id: str, body: AddFilesRequest):
    session = _get_session(session_id)
    events = session.add_files(body.paths)
    return AddFilesResponse(
        files_in_chat=session.coder.get_inchat_relative_files(),
        events=events,
    )


@app.post("/sessions/{session_id}/files/upload", response_model=AddFilesResponse)
def upload_session_files(session_id: str, body: UploadFilesRequest):
    session = _get_session(session_id)
    items: list[tuple[str, bytes]] = []
    for part in body.files:
        try:
            data = Session.decode_upload(part.content_base64)
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Invalid base64 for {part.filename}: {err}") from err
        items.append((part.filename, data))
    events = session.upload_files(items)
    return AddFilesResponse(
        files_in_chat=session.coder.get_inchat_relative_files(),
        events=events,
    )


@app.post("/sessions/{session_id}/messages")
def post_message(session_id: str, body: MessageRequest):
    session = _get_session(session_id)

    def generate():
        try:
            for event in session.run_message(
                body.content,
                preproc=body.preproc,
                active_todo_id=body.active_todo_id,
                inject_todo_spec=body.inject_todo_spec,
            ):
                yield _sse_pack(event)
        except (BrokenPipeError, ConnectionResetError) as err:
            yield _sse_pack({"type": "error", "text": str(err)})
            yield _sse_pack({"type": "done", "error": True})
        except OSError as err:
            if err.errno != 32:
                raise
            yield _sse_pack({"type": "error", "text": str(err)})
            yield _sse_pack({"type": "done", "error": True})
        except GeneratorExit:
            return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/sessions/{session_id}/confirm")
def post_confirm(session_id: str, body: ConfirmRequest):
    session = _get_session(session_id)
    if not session.io.resolve_confirm(body.confirm_id, body.answer):
        raise HTTPException(status_code=404, detail="Unknown or expired confirmation")
    return {"ok": True, "confirm_id": body.confirm_id, "answer": body.answer}


@app.post("/sessions/{session_id}/undo")
def post_undo(session_id: str):
    session = _get_session(session_id)
    undo_last_aider_commit_for_coder(session.coder, session.io)
    events = session.io.drain_events()
    return {
        "events": events,
        "commits": session.coder.aider_commit_stack,
        "last_commit_hash": session.coder.last_aider_commit_hash,
    }


def _get_session(session_id: str) -> Session:
    with _lock:
        session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
