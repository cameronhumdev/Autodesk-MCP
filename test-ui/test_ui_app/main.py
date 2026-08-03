from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Repo root on PYTHONPATH for `rag` package
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from rag import get_rag_backend  # noqa: E402
from test_ui_app import samples as samples_mod  # noqa: E402
from test_ui_app.llm import chat as llm_chat, resolve_mode  # noqa: E402
from test_ui_app.tools import build_dispatch, tool_specs  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(title="Autodesk-MCP Test UI", version="0.1.0")
rag = get_rag_backend()
dispatch = build_dispatch(lambda q, k: rag.search(q, k))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "test-ui",
        "rag": rag.status(),
    }


@app.get("/api/status")
async def status():
    mode = await resolve_mode()
    return {
        "ok": True,
        "llm_mode": mode,
        "llm_base_url": os.getenv("LLM_BASE_URL", ""),
        "llm_model": os.getenv("LLM_MODEL", ""),
        "rag": rag.status(),
        "tools": [t["function"]["name"] for t in tool_specs()],
    }


@app.get("/api/samples")
def api_samples():
    return {"samples": samples_mod.load_samples()}


@app.get("/api/samples/raw", response_class=PlainTextResponse)
def api_samples_raw():
    return samples_mod.raw_markdown()


@app.get("/api/tools")
def api_tools():
    return {"tools": tool_specs()}


@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    messages = [m.model_dump() for m in body.messages]
    return await llm_chat(messages, dispatch)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
