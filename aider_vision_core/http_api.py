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
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from aider_vision_core.headless_stdio import install_headless_stdio

install_headless_stdio()

from aider_vision_core.git_undo import undo_last_aider_commit_for_coder
from aider_vision_core.http_auth import auth_enabled, configure_auth, get_token_from_env, verify_bearer
from aider_vision_core.session import Session


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
    auto_commits: bool = True
    dirty_commits: bool = True
    dry_run: bool = False


class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    preproc: bool = True


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
    return SessionInfo(
        session_id=session_id,
        workspace=session.coder.root,
        model=session.coder.main_model.name,
        files_in_chat=session.coder.get_inchat_relative_files(),
    )


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


@app.post("/sessions/{session_id}/messages")
def post_message(session_id: str, body: MessageRequest):
    session = _get_session(session_id)

    def generate():
        try:
            for event in session.run_message(body.content, preproc=body.preproc):
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
