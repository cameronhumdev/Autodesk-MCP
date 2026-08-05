from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

# Repo root on PYTHONPATH for `rag` package
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path, override=True)

from rag import get_rag_backend  # noqa: E402
from test_ui_app import chats as chats_mod  # noqa: E402
from test_ui_app import llm_settings  # noqa: E402
from test_ui_app import samples as samples_mod  # noqa: E402
from test_ui_app.llm import chat as llm_chat, resolve_mode  # noqa: E402

# UI-saved LLM settings override .env for this process (no restart needed on Save).
llm_settings.bootstrap()
from test_ui_app.cad_remote import agent_status, is_remote  # noqa: E402
from test_ui_app.tools import (  # noqa: E402
    build_dispatch,
    ensure_autocad_ready,
    ensure_inventor_ready,
    force_restart_autocad_confirmed,
    force_restart_inventor_confirmed,
    launch_status,
    tool_specs,
    track_status,
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(title="Autodesk-MCP Test UI", version="0.2.0")
rag = get_rag_backend()
dispatch = build_dispatch(lambda q, k: rag.search(q, k), rag=rag)


class ChatMessage(BaseModel):
    """Chat turn. Extra fields (actions, pending_switch, elapsed_ms) are UI meta."""

    model_config = ConfigDict(extra="allow")

    role: str
    content: str = ""


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    track: str = "inventor"
    chat_id: str | None = None
    stream: bool = False
    # Restrict tools to launch + base modelling (A/B vs full surface)
    base_modelling_kit: bool = False


class NewChatRequest(BaseModel):
    track: str | None = None
    title: str = "New chat"


class SaveChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    title: str | None = None
    track: str | None = None


class LaunchCadRequest(BaseModel):
    app: str
    wait_s: float = 90.0
    drawing_path: str | None = None


class ForceRestartCadRequest(BaseModel):
    app: str = "autocad"
    wait_s: float = 90.0
    drawing_path: str | None = None
    reason: str = ""


class LlmSettingsRequest(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    clear_api_key: bool = False
    mode: str | None = None
    max_tokens: int | None = None


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "test-ui",
        "rag": rag.status(),
    }


@app.get("/api/settings/llm")
def api_get_llm_settings():
    """Public LLM settings (API key masked)."""
    return {"ok": True, **llm_settings.public_settings()}


@app.put("/api/settings/llm")
def api_put_llm_settings(body: LlmSettingsRequest):
    """Save provider / model / API key; applies immediately (no restart)."""
    patch = body.model_dump(exclude_unset=True)
    try:
        saved = llm_settings.save_settings(patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not save settings: {exc}"
        ) from exc
    return {"ok": True, **saved}


@app.get("/api/status")
async def status():
    mode = await resolve_mode()
    llm = llm_settings.public_settings()
    try:
        tracks = track_status()
    except Exception as exc:  # noqa: BLE001
        tracks = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "llm_mode": mode,
        "llm_provider": llm.get("provider"),
        "llm_base_url": llm.get("base_url") or os.getenv("LLM_BASE_URL", ""),
        "llm_model": llm.get("model") or os.getenv("LLM_MODEL", ""),
        "llm_api_key_set": llm.get("api_key_set"),
        "llm_api_key_hint": llm.get("api_key_hint"),
        "rag": rag.status(),
        "cad_mode": "remote" if is_remote() else "local",
        "cad_agent": agent_status(),
        "tracks": tracks,
        "inventor_backend": os.getenv("INVENTOR_BACKEND", "mcp"),
        "autocad_backend": os.getenv("AUTOCAD_BACKEND", "mcp"),
        "tools_inventor": [t["function"]["name"] for t in tool_specs("inventor")],
        "tools_autocad": [t["function"]["name"] for t in tool_specs("autocad")],
        "tools_inventor_count": len(tool_specs("inventor")),
        "tools_autocad_count": len(tool_specs("autocad")),
        "tools_inventor_base_modelling_kit": [
            t["function"]["name"]
            for t in tool_specs("inventor", base_modelling_kit=True)
        ],
        "tools_autocad_base_modelling_kit": [
            t["function"]["name"]
            for t in tool_specs("autocad", base_modelling_kit=True)
        ],
        "tools_inventor_base_modelling_kit_count": len(
            tool_specs("inventor", base_modelling_kit=True)
        ),
        "tools_autocad_base_modelling_kit_count": len(
            tool_specs("autocad", base_modelling_kit=True)
        ),
    }


@app.get("/api/samples")
def api_samples(track: str | None = None):
    samples = samples_mod.load_samples()
    if track:
        track = track.lower().strip()
        filtered = []
        for s in samples:
            blob = f"{s.get('title', '')} {s.get('prompt', '')}".lower()
            if track == "inventor" and ("autocad" in blob and "inventor" not in blob):
                continue
            if track == "autocad" and ("inventor" in blob and "autocad" not in blob):
                continue
            # Keep shared samples (health, rag, echo) for both
            filtered.append(s)
        samples = filtered
    return {"samples": samples}


@app.get("/api/samples/raw", response_class=PlainTextResponse)
def api_samples_raw():
    return samples_mod.raw_markdown()


@app.get("/api/tools")
def api_tools(track: str | None = None, base_modelling_kit: bool = False):
    specs = tool_specs(track, base_modelling_kit=base_modelling_kit)
    return {
        "tools": specs,
        "base_modelling_kit": base_modelling_kit,
        "count": len(specs),
    }


@app.get("/api/cad/launch")
def api_cad_launch_status(app: str):
    """Non-mutating status for an allowlisted CAD app."""
    try:
        return {"ok": True, **launch_status(app)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/cad/launch")
def api_cad_launch(body: LaunchCadRequest):
    """Start allowlisted Inventor/AutoCAD after UI Confirm (attach if already running).

    AutoCAD also opens a drawing; Inventor waits for the add-in target and opens a part.
    """
    app = (body.app or "").lower().strip()
    if app not in {"inventor", "autocad"}:
        raise HTTPException(status_code=400, detail="app must be inventor or autocad")
    wait_s = max(5.0, min(float(body.wait_s or 90.0), 180.0))
    path = (body.drawing_path or "").strip() or None
    if app == "inventor":
        return ensure_inventor_ready(force_reset=True, wait_s=wait_s)
    return ensure_autocad_ready(
        force_reset=True, wait_s=wait_s, drawing_path=path
    )


@app.post("/api/cad/force-restart")
def api_cad_force_restart(body: ForceRestartCadRequest):
    """Quit and relaunch AutoCAD/Inventor only after explicit UI Confirm (never silent)."""
    app = (body.app or "autocad").lower().strip()
    if app not in {"autocad", "inventor"}:
        raise HTTPException(
            status_code=400,
            detail="force-restart is only supported for autocad or inventor",
        )
    reason = (body.reason or "").strip()
    if not reason:
        label = "AutoCAD" if app == "autocad" else "Inventor"
        raise HTTPException(
            status_code=400,
            detail=f"reason is required before quitting {label}",
        )
    wait_s = max(5.0, min(float(body.wait_s or 90.0), 180.0))
    path = (body.drawing_path or "").strip() or None
    if app == "inventor":
        return force_restart_inventor_confirmed(
            wait_s=wait_s,
            reason=reason,
        )
    return force_restart_autocad_confirmed(
        drawing_path=path,
        wait_s=wait_s,
        reason=reason,
    )


@app.get("/api/chats")
def api_list_chats(track: str | None = None):
    return {"chats": chats_mod.list_chats(track)}


@app.post("/api/chats")
def api_create_chat(body: NewChatRequest):
    try:
        return chats_mod.create_chat(body.track, body.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/chats/{chat_id}")
def api_get_chat(chat_id: str):
    data = chats_mod.get_chat(chat_id)
    if not data:
        raise HTTPException(status_code=404, detail="chat not found")
    return data


@app.put("/api/chats/{chat_id}")
def api_save_chat(chat_id: str, body: SaveChatRequest):
    messages = [m.model_dump() for m in body.messages]
    title = body.title or chats_mod.title_from_messages(messages)
    data = chats_mod.save_chat(
        chat_id,
        messages=messages,
        title=title,
        track=body.track,
    )
    if not data:
        raise HTTPException(status_code=404, detail="chat not found")
    return data


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str):
    if not chats_mod.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="chat not found")
    return {"ok": True}


def _persist_chat_result(body: ChatRequest, track: str, result: dict) -> dict:
    """Persist conversation when chat_id provided (UI meta for Confirm/Cancel + tools)."""
    chat_id = body.chat_id
    if not chat_id:
        return result
    stored = [m.model_dump() for m in body.messages]
    if result.get("reply") or result.get("error"):
        assistant: dict = {
            "role": "assistant",
            "content": result.get("reply") or result.get("error") or "",
        }
        if result.get("actions"):
            assistant["actions"] = result["actions"]
        if result.get("pending_switch"):
            assistant["pending_switch"] = result["pending_switch"]
        if result.get("pending_launch"):
            assistant["pending_launch"] = result["pending_launch"]
        if result.get("usage"):
            assistant["usage"] = result["usage"]
        stored.append(assistant)
    chats_mod.save_chat(
        chat_id,
        messages=stored,
        title=chats_mod.title_from_messages(stored),
        track=track,
    )
    result["chat_id"] = chat_id
    return result


@app.post("/api/chat")
async def api_chat(request: Request, body: ChatRequest):
    messages = [m.model_dump() for m in body.messages]
    track = (body.track or "inventor").lower().strip()
    base_modelling_kit = bool(body.base_modelling_kit)

    async def cancelled() -> bool:
        return await request.is_disconnected()

    if body.stream:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def on_event(event: dict) -> None:
            await queue.put(event)

        async def run_chat() -> None:
            try:
                result = await llm_chat(
                    messages,
                    dispatch,
                    track=track,
                    cancelled=cancelled,
                    on_event=on_event,
                    base_modelling_kit=base_modelling_kit,
                )
                result = _persist_chat_result(body, track, result)
                result["base_modelling_kit"] = base_modelling_kit
                await queue.put({"type": "final", **result})
            except Exception as exc:  # noqa: BLE001 — surface to UI
                await queue.put(
                    {
                        "type": "final",
                        "mode": "live",
                        "track": track,
                        "base_modelling_kit": base_modelling_kit,
                        "error": f"{type(exc).__name__}: {exc}",
                        "reply": "",
                        "actions": [],
                    }
                )
            finally:
                await queue.put(None)

        async def event_stream():
            task = asyncio.create_task(run_chat())
            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = await llm_chat(
            messages,
            dispatch,
            track=track,
            cancelled=cancelled,
            base_modelling_kit=base_modelling_kit,
        )
    except Exception as exc:  # noqa: BLE001 — surface to UI
        return {
            "mode": "live",
            "track": track,
            "base_modelling_kit": base_modelling_kit,
            "error": f"{type(exc).__name__}: {exc}",
            "reply": "",
            "actions": [],
        }

    result = _persist_chat_result(body, track, result)
    result["base_modelling_kit"] = base_modelling_kit
    return result


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
@app.get("/favicon.png")
def favicon():
    path = STATIC_DIR / "favicon.png"
    return FileResponse(path, media_type="image/png")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
