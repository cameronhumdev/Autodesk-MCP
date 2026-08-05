from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from test_ui_app import llm_settings
from test_ui_app.tools import (
    _soft_then_hard_recover,
    _soft_then_hard_recover_inventor,
    ensure_autocad_ready,
    ensure_inventor_ready,
    request_force_restart_inventor,
    run_tool,
    tool_specs,
)

# tools.py puts cad/ on sys.path
try:
    from shared.launch_cad import is_running as _cad_is_running
except ImportError:  # pragma: no cover

    def _cad_is_running(_app: str) -> bool:  # type: ignore[misc]
        return False


def llm_mode() -> str:
    mode = (llm_settings.load_settings().get("mode") or "auto").lower().strip()
    if mode in {"auto", "live", "demo"}:
        return mode
    return "auto"


def _client_config() -> tuple[str, str, str]:
    base, model, key, _max_tokens = llm_settings.client_config()
    return base, model, key


def _client_config_full() -> tuple[str, str, str, int]:
    return llm_settings.client_config()


async def _probe_live(base: str, key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            # Anthropic OpenAI-compat may not expose /models the same way —
            # treat auth errors as "reachable enough" for live mode.
            if r.status_code in {401, 403}:
                return bool(key and key != "no-key")
            return r.status_code < 500
    except Exception:
        return False


async def resolve_mode() -> str:
    mode = llm_mode()
    if mode != "auto":
        return mode
    base, _, key = _client_config()
    return "live" if await _probe_live(base, key) else "demo"


def _system_prompt(track: str, *, base_modelling_kit: bool = False) -> str:
    other = "autocad" if track == "inventor" else "inventor"
    other_label = "AutoCAD" if other == "autocad" else "Inventor"
    current_label = "Inventor" if track == "inventor" else "AutoCAD"
    if track == "autocad":
        if base_modelling_kit:
            modeling = (
                "BASE MODELLING KIT mode is ON — only a small tool set is available. "
                "For a basic solid or cabinet: call autocad_drawing_new if needed, then "
                "autocad_solid_box for the carcass (e.g. length=600, width=400, height=720), "
                "more autocad_solid_box / autocad_solid_cylinder, then autocad_solid_boolean "
                "with real handles from create results. "
                "To show the result: autocad_view_zoom_extents, then "
                "autocad_view_screenshot or autocad_view_zoom_and_screenshot. "
                "If AutoCAD is not running, call request_launch_cad and wait for Confirm. "
                "Use recover_autocad if the host asks after a session failure. "
                "Do NOT probe layouts or layers — those tools are not available. "
                "NEVER pass empty handles. NEVER write Python. Use native tool_calls only. "
                "After tools succeed, briefly report what was created in AutoCAD."
            )
        else:
            modeling = (
                "When the user asks to open an existing drawing/project and gives a .dwg/.dxf path: "
                "call autocad_drawing_open with that full path (do NOT call autocad_drawing_new). "
                "When the user asks to model/build/draw something new: "
                "IMMEDIATELY call real tools. Prefer autocad_drawing_new first if no drawing exists, "
                "then create geometry with autocad_solid_box / autocad_solid_cylinder / "
                "autocad_solid_boolean for 3D, or autocad_entity_create_* for 2D. "
                "Do NOT start with layout_list / layer_list probes — create the drawing and entities. "
                "Pick reasonable default dimensions if the user did not specify them. "
                "NEVER write Python, NEVER invent function names like autocad_rectangle_create, "
                "NEVER paste tool-call JSON into the chat message — use native tool_calls only. "
                "NEVER say the task is beyond scope, NEVER describe what you would do instead of doing it. "
                "After tools succeed, briefly report what was opened or created in AutoCAD."
            )
    else:
        if base_modelling_kit:
            modeling = (
                "BASE MODELLING KIT mode is ON — only a small tool set is available. "
                "For a basic part or cabinet: inventor_new_part or inventor_create_part, then "
                "inventor_create_sketch → inventor_draw_rectangle (or line/circle) → "
                "inventor_close_sketch → inventor_extrude. Use inventor_set_parameter / "
                "inventor_create_parameter for sizes. "
                "If Inventor is not running, call request_launch_cad and wait for Confirm. "
                "Use recover_inventor if the host asks after a session failure. "
                "To capture the screen: inventor_capture_view (cannot change camera/orbit — "
                "user sets the view in Inventor if needed). "
                "NEVER write Python. Use native tool_calls only. "
                "After tools succeed, briefly report what was created in Inventor."
            )
        else:
            modeling = (
                "When the user asks to model/build a part: IMMEDIATELY call inventor_* tools "
                "(e.g. inventor_new_part / inventor_create_part, sketches, extrude, parameters). "
                "If Inventor is not running, the host will ask the user to Confirm launch. "
                "NEVER write Python or pretend-code. NEVER paste tool JSON in chat text. "
                "NEVER say the task is beyond scope."
            )
    tool_surface = (
        f"You have the BASE MODELLING KIT tool subset for {current_label} "
        f"(launch/recover + solids/sketch/extrude + view zoom/capture — "
        f"no layout/layer probes, no web tools). "
        if base_modelling_kit
        else (
            f"You have the FULL {current_label} MCP tool surface ({track}_* tools) plus "
            f"health/echo/knowledge_search/web_search/web_fetch/"
            f"request_track_switch/request_launch_cad. "
        )
    )
    research = (
        ""
        if base_modelling_kit
        else (
            "When the user asks to google/search online, look something up, or asks "
            "general knowledge (what is/are, who is), ALWAYS call web_search first "
            "(then web_fetch if you need page detail). Do not answer those from memory alone. "
            "Use web_search/web_fetch for online docs, dimensions, or references. "
        )
    )
    return (
        f"You are the Autodesk-MCP assistant. This product supports BOTH Inventor and AutoCAD "
        f"as separate modes. You are currently in {current_label} mode. "
        f"{tool_surface}"
        f"{research}"
        f"Do NOT call {other}_* tools while in this mode. "
        f"Stay in {current_label} mode for modeling/drawing requests unless the user "
        f"explicitly asks for {other_label} by name. "
        f"Do NOT switch to Inventor just because the user said 3D, model, part, or phone — "
        f"in AutoCAD mode, use AutoCAD tools for that work. "
        f"Only call request_track_switch when the user clearly names {other_label} "
        f"(e.g. 'in {other_label}', 'using {other_label}'). "
        f"For AutoCAD: if AutoCAD is not running, the host asks the user to Confirm "
        f"before launching (or call request_launch_cad). After Confirm, a drawing is opened. "
        f"If the user gave a .dwg/.dxf path, open that file with autocad_drawing_open; "
        f"otherwise use autocad_drawing_new for a blank drawing. "
        f"Never claim you started AutoCAD yourself — wait for Confirm. "
        f"If a tool fails with COM/RPC/stdio ('RPC server is unavailable', McpStdioError): "
        f"call recover_autocad with {{}} (soft — does not quit AutoCAD), then recreate "
        f"solids from scratch (do not boolean with null/empty handles), then continue. "
        f"Only if soft recover fails or AutoCAD is frozen, call recover_autocad with "
        f'{{"force_restart": true, "reason": "<short why>"}} — the UI asks the user to '
        f"Confirm before quitting acad.exe. Never kill applications yourself. "
        f"Follow any 'instruction' field on tool errors. "
        f"For Inventor: if Inventor is not running, the host asks the user to Confirm "
        f"before launching (or call request_launch_cad). After Confirm, the host waits for "
        f"the Bimwright add-in target and opens a new part. "
        f"Never claim you started Inventor yourself — wait for Confirm. "
        f"If a tool fails with NO_TARGET / add-in / stdio errors: "
        f"call recover_inventor with {{}} (soft — does not quit Inventor), then recreate "
        f"the part from scratch, then continue. "
        f"Only if soft recover fails or Inventor is frozen, call recover_inventor with "
        f'{{"force_restart": true, "reason": "<short why>"}} — the UI asks the user to '
        f"Confirm before quitting Inventor.exe. Never kill applications yourself. "
        f"CRITICAL — tool errors are for YOU, not the user: if a tool returns error/validation/"
        f"unexpected keyword/missing argument, silently fix the arguments using that tool's "
        f"schema and call it again. Never paste McpStdioError, pydantic dumps, JSON schemas, "
        f"tool names with argument blocks, result JSON, or 'how to call functions' tutorials "
        f"to the user. Final replies must be plain English only — the UI already shows tools "
        f"in the Worked dropdown. Only if retries still fail, tell the user in one short "
        f"plain sentence what blocked progress. "
        f"Never run shell commands. Never say you only support Inventor or only AutoCAD. "
        f"Never switch modes or launch apps yourself — the UI renders Confirm / Cancel. "
        f"After calling request_track_switch, request_launch_cad, or a force-restart Confirm, "
        f"reply with ONE short sentence pointing at Confirm or Cancel below. "
        f"Use knowledge_search for standards; use {track}_export_to_rag for CAD summaries. "
        f"{modeling} "
        f"Prefer tools over guessing. Do not claim a capability is impossible if a tool exists for it."
    )


def _pending_switch_from_actions(
    actions: list[dict], current_track: str
) -> dict[str, Any] | None:
    for action in reversed(actions):
        if action.get("tool") != "request_track_switch":
            continue
        result = action.get("result") or {}
        if not result.get("needs_confirmation"):
            continue
        to_track = result.get("to_track")
        if to_track not in {"inventor", "autocad"} or to_track == current_track:
            continue
        return {
            "from_track": current_track,
            "to_track": to_track,
            "reason": result.get("reason") or "",
            "prompt": result.get("prompt")
            or f"Switch from {current_track} to {to_track}?",
        }
    return None


def _last_retryable_tool_error(actions: list[dict]) -> dict[str, Any] | None:
    """Most recent tool result that asks the model to fix args and retry."""
    for action in reversed(actions or []):
        result = action.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("retry") is True:
            return action
        err = str(result.get("error") or "")
        if err and any(
            k in err.lower()
            for k in ("validation error", "unexpected keyword", "field required")
        ):
            return action
        # Stop at the latest non-empty tool result that isn't retryable
        if result.get("error") or result.get("ok") is True or "entity" in result:
            break
    return None


def _looks_like_schema_dump(reply: str) -> bool:
    lower = (reply or "").lower()
    return any(
        k in lower
        for k in (
            "validation error",
            "unexpected keyword",
            "pydantic",
            "for further information visit https://errors.pydantic",
            "here are examples of how to call",
            "error type: mcpstdioerror",
            '"type": "string"',
            "mcpstdioerror",
            "assistant_only",
            "missing required argument",
        )
    )


_TOOL_TRANSCRIPT_RE = re.compile(
    r"(?m)^(autocad_|inventor_)[a-z0-9_]+\s*\n\s*\{",
)


def _looks_like_tool_transcript(reply: str) -> bool:
    """Model pasted tool name + JSON args/results into the chat bubble."""
    text = reply or ""
    if _TOOL_TRANSCRIPT_RE.search(text):
        return True
    lower = text.lower()
    if '"audience": "assistant_only"' in lower or '"audience":"assistant_only"' in lower:
        return True
    if text.count("\n{") >= 2 and (
        "autocad_" in lower or "inventor_" in lower or '"ok":' in lower
    ):
        return True
    return False


def _sanitize_user_reply(reply: str, actions: list[dict]) -> str:
    """Never show raw tool JSON / validation dumps in the user-facing bubble."""
    if not _looks_like_schema_dump(reply) and not _looks_like_tool_transcript(reply):
        return reply
    cad = [
        a
        for a in (actions or [])
        if str(a.get("tool") or "").startswith(("autocad_", "inventor_"))
    ]
    inv = any(str(a.get("tool") or "").startswith("inventor_") for a in cad)
    product = "Inventor" if inv else "AutoCAD"
    doc = "part" if inv else "drawing"
    if not cad:
        return (
            "I hit a tool error and couldn't finish that step. "
            f"Ask me again and I'll retry ({product} + a new {doc} are started automatically)."
        )
    ok = 0
    bad = 0
    for a in cad:
        res = a.get("result") or {}
        if isinstance(res, dict) and res.get("ok") is False:
            bad += 1
        elif isinstance(res, dict) and res.get("error"):
            bad += 1
        else:
            ok += 1
    last = str((cad[-1] or {}).get("tool") or "a tool")
    if bad and not ok:
        return (
            f"{product} still rejected the CAD calls after starting it with a new {doc} "
            f"(last: {last}). Ask me again to retry, or check {product} isn't stuck on a dialog."
        )
    if bad:
        return (
            f"Partially done — {ok} tool(s) ok, {bad} failed (last: {last}). "
            f"Tell me what to try next."
        )
    return f"Finished {ok} {product} tool call(s). Check the {doc} for results."


def _modeling_intent(user_text: str) -> bool:
    lower = (user_text or "").lower()
    verbs = (
        "model",
        "modelled",
        "modeled",
        "draw",
        "create",
        "build",
        "make",
        "design",
        "generate",
        "extrude",
        "cabinet",
        "phone",
        "car",
        "part",
        "3d",
        "solid",
        "open",
        "opening",
        "project",
        ".dwg",
        ".dxf",
    )
    return any(v in lower for v in verbs)


def _research_intent(user_text: str) -> bool:
    """User wants a live internet lookup (not local RAG / CAD)."""
    lower = (user_text or "").lower().strip()
    if not lower:
        return False
    triggers = (
        "google",
        "bing",
        "duckduckgo",
        "search the web",
        "search online",
        "search the internet",
        "look up",
        "lookup",
        "look it up",
        "internet",
        "web search",
        "wikipedia",
        "browse",
        "online docs",
        "from the web",
        "on the internet",
    )
    if any(t in lower for t in triggers):
        return True
    # "what is/are …" / "who is/are …" — common research phrasing
    if re.search(r"\b(what|who)\s+(is|are|was|were)\b", lower):
        return True
    if re.search(r"\b(tell me about|define|definition of)\b", lower):
        return True
    return False


def _research_query(user_text: str) -> str:
    """Strip filler words so web_search gets a clean query."""
    q = (user_text or "").strip()
    q = re.sub(
        r"(?i)\b(please|can you|could you|google|search( the web| online| the internet)?"
        r"|look up|lookup|on the internet|from the web|for me)\b",
        " ",
        q,
    )
    q = re.sub(r"\s+", " ", q).strip(" ?!.,")
    return q or (user_text or "").strip()


def _has_web_actions(actions: list[dict]) -> bool:
    return any(
        str(a.get("tool") or "") in {"web_search", "web_fetch"} for a in (actions or [])
    )


def _looks_like_tool_avoidance(reply: str) -> bool:
    """Model is narrating / writing fake code instead of calling tools."""
    lower = (reply or "").lower()
    return any(
        k in lower
        for k in (
            "beyond the scope",
            "beyond scope",
            "quite involved",
            "i can provide a partial",
            "here's how we might",
            "here is how we might",
            "we define a function",
            "i'll create a function",
            "i will create a function",
            "def ",
            "pseudocode",
            "would be quite",
            "typically requires",
            "for simplicity, let's assume",
            "autocad_rectangle_create",
            "not directly supported",
            "more complex operations not",
        )
    )


def _modeling_nudge(track: str) -> str:
    if track == "autocad":
        return (
            "[host] Stop explaining. Call tools NOW using the API tool_calls mechanism "
            "(not JSON in the message text). For a cabinet, call autocad_solid_box "
            "for the carcass (e.g. length=600, width=400, height=720, cx=0, cy=0, cz=360), "
            "then more solid_box / solid_boolean as needed. "
            "Do not write Python or invent tool names. Do not say beyond scope."
        )
    return (
        "[host] Stop explaining. Call inventor_* tools NOW via tool_calls "
        "(not JSON in the message text). "
        "Do not write Python. Do not say beyond scope."
    )


def _extract_json_objects(text: str) -> list[Any]:
    """Pull top-level JSON objects out of free text (brace-balanced)."""
    objs: list[Any] = []
    i = 0
    n = len(text or "")
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        start = i
        in_str = False
        esc = False
        for j in range(i, n):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : j + 1]
                    try:
                        objs.append(json.loads(chunk))
                    except json.JSONDecodeError:
                        pass
                    i = j + 1
                    break
        else:
            break
    return objs


def _tool_calls_from_text(text: str, allowed: set[str]) -> list[dict[str, Any]]:
    """
    Recover tool calls when the model prints them as JSON in content
    instead of using the native tool_calls field (common with small local models).
    """
    calls: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(name: str, args: Any) -> None:
        if not name or name not in allowed:
            return
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return
        key = f"{name}:{json.dumps(args, sort_keys=True)}"
        if key in seen:
            return
        seen.add(key)
        calls.append(
            {
                "id": f"host_text_{len(calls)}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            }
        )

    # Transcript style: autocad_foo\n{ ... }
    for m in re.finditer(
        r"(?m)^(autocad_[a-z0-9_]+|inventor_[a-z0-9_]+)\s*\n(\{[\s\S]*?\n\})",
        text or "",
    ):
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        # Skip result blobs (ok/error) — only treat arg objects as calls
        if isinstance(args, dict) and (
            "ok" in args or "error_type" in args or "audience" in args
        ):
            continue
        _add(name, args)

    for obj in _extract_json_objects(text or ""):
        if not isinstance(obj, dict):
            continue
        name = obj.get("name")
        args = obj.get("arguments")
        if not name and isinstance(obj.get("function"), dict):
            name = obj["function"].get("name")
            args = obj["function"].get("arguments", args)
        _add(name, args)
    return calls


def _pending_launch_from_actions(actions: list[dict]) -> dict[str, Any] | None:
    for action in reversed(actions):
        result = action.get("result") or {}
        if not result.get("needs_confirmation"):
            continue
        app = result.get("app")
        if app not in {"inventor", "autocad"}:
            continue
        # Quit/restart — from recover_* or host soft-recover escalation.
        if result.get("action") == "force_restart":
            return {
                "app": app,
                "action": "force_restart",
                "reason": result.get("reason") or "",
                "prompt": result.get("prompt")
                or f"Quit and restart {app}?",
                "drawing_path": result.get("drawing_path"),
                "status": result.get("status") or {},
            }
        tool = action.get("tool")
        # Cold-start Confirm from request_launch_cad or recover_* when app is down.
        if tool not in {
            "request_launch_cad",
            "recover_autocad",
            "recover_inventor",
        } and result.get("ui") != "confirm_cancel":
            continue
        return {
            "app": app,
            "reason": result.get("reason") or "",
            "prompt": result.get("prompt") or f"Launch {app}?",
            "status": result.get("status") or {},
            "drawing_path": result.get("drawing_path"),
        }
    return None


def _switch_reply(pending: dict[str, Any]) -> str:
    label = "AutoCAD" if pending["to_track"] == "autocad" else "Inventor"
    reason = pending.get("reason") or f"use {label} tools"
    return (
        f"This chat is in a different CAD mode right now. "
        f"I can switch to **{label}** mode so I can help with that "
        f"({reason}). Confirm or Cancel below."
    )


def _launch_reply(pending: dict[str, Any]) -> str:
    label = "AutoCAD" if pending["app"] == "autocad" else "Inventor"
    reason = pending.get("reason") or f"use live {label} tools"
    status = pending.get("status") or {}
    if status.get("installed") is False:
        return (
            f"I could not find an allowlisted **{label}** install. "
            f"Install the product or set the approved path, then try again."
        )
    if pending.get("action") == "force_restart":
        return (
            f"**{label}** is not responding, so I need your approval to quit and "
            f"restart it.\n\n"
            f"**Reason:** {reason}\n\n"
            f"Confirm or Cancel below — I will not close **{label}** without your approval. "
            f"Unsaved work in that session may be lost if you Confirm."
        )
    return (
        f"I can launch **{label}** on this machine ({reason}). "
        f"Confirm or Cancel below — I will not start it without your approval."
    )


def _cross_track_target(user_text: str, track: str) -> str | None:
    """If the user clearly needs the other CAD product, return that track."""
    lower = (user_text or "").lower()
    mentions_acad = (
        "autocad" in lower
        or "auto cad" in lower
        or bool(re.search(r"\bacad\b", lower))
    )
    mentions_inv = "inventor" in lower
    not_inv = bool(re.search(r"\bnot\s+inventor\b", lower))
    not_acad = bool(
        re.search(r"\bnot\s+auto\s*cad\b", lower)
        or re.search(r"\bnot\s+acad\b", lower)
    )
    # Prefer explicit "in/with/using inventor|autocad" even when both are named.
    in_inv = bool(re.search(r"\b(?:in|with|using|via|for)\s+inventor\b", lower))
    in_acad = bool(
        re.search(r"\b(?:in|with|using|via|for)\s+auto\s*cad\b", lower)
        or re.search(r"\b(?:in|with|using|via|for)\s+acad\b", lower)
    )
    if in_inv and not not_inv and track == "autocad":
        return "inventor"
    if in_acad and not not_acad and track == "inventor":
        return "autocad"
    # "not inventor" while in AutoCAD / "not autocad" while in Inventor → stay
    if not_inv and track == "autocad":
        return None
    if not_acad and track == "inventor":
        return None
    # Both named without a clear "in X" preference → don't force a switch
    if mentions_acad and mentions_inv:
        return None
    if track == "inventor" and mentions_acad and not not_acad:
        return "autocad"
    if track == "autocad" and mentions_inv and not not_inv:
        return "inventor"
    return None


def _cad_app_for_tool(fn: str) -> str | None:
    """Map inventor_*/autocad_* tools to the local app they need."""
    name = (fn or "").lower()
    if name.startswith("inventor_"):
        return "inventor"
    if name.startswith("autocad_"):
        return "autocad"
    return None


def _extract_drawing_path(text: str) -> str | None:
    """Best-effort .dwg/.dxf path from user text (Windows, UNC, or quoted)."""
    if not text:
        return None
    patterns = (
        r'"([^"\n]+\.(?:dwg|dxf))"',
        r"'([^'\n]+\.(?:dwg|dxf))'",
        r"((?:[a-zA-Z]:\\|\\\\)[^\s\"'<>|?*]+\.(?:dwg|dxf))",
    )
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = (m.group(1) if m.lastindex else m.group(0)).strip().strip('"').strip("'")
        if candidate:
            return candidate
    return None


def _preflight_launch_if_needed(
    dispatch: dict, fn: str, *, drawing_path: str | None = None
) -> tuple[dict[str, Any] | None, list[dict]]:
    """
    Prepare the CAD app before a tool runs.

    If the app is not running: return a Confirm/Cancel launch prompt (do not start).
    If already running: ensure drawing (AutoCAD) or add-in target + part (Inventor).
    """
    app = _cad_app_for_tool(fn)
    if not app:
        return None, []

    label = "AutoCAD" if app == "autocad" else "Inventor"
    if not _cad_is_running(app):
        args: dict[str, Any] = {
            "app": app,
            "reason": f"{label} is needed for this modeling request",
        }
        if drawing_path and app == "autocad":
            args["drawing_path"] = drawing_path
        out = run_tool(dispatch, "request_launch_cad", args)
        try:
            result = json.loads(out)
        except json.JSONDecodeError:
            result = {"error": out, "needs_confirmation": False}
        actions = [
            {
                "tool": "request_launch_cad",
                "arguments": args,
                "result": result,
            }
        ]
        pending = _pending_launch_from_actions(actions)
        if pending:
            return pending, actions
        # Not installed / already-running race — surface the tool result.
        return None, actions

    # Already running — ensure drawing/part without Confirm (idempotent).
    if app == "autocad":
        ready = ensure_autocad_ready(drawing_path=drawing_path)
        actions = [
            {
                "tool": "ensure_autocad_ready",
                "arguments": {
                    "app": "autocad",
                    **({"drawing_path": drawing_path} if drawing_path else {}),
                },
                "result": ready,
            }
        ]
        if ready.get("ok"):
            return None, actions
        return None, [
            {
                "tool": fn,
                "arguments": {},
                "result": {
                    "ok": False,
                    "error": (
                        "AutoCAD is running but a drawing could not be opened. "
                        f"{ready.get('error') or ready}"
                    ),
                    "launch": ready,
                    "retry": True,
                    "audience": "assistant_only",
                    "instruction": (
                        "FOR THE ASSISTANT ONLY — call recover_autocad with {}. "
                        "If soft recover fails, use force_restart+reason for Confirm."
                    ),
                },
            }
        ]

    ready = ensure_inventor_ready()
    actions = [
        {
            "tool": "ensure_inventor_ready",
            "arguments": {"app": "inventor"},
            "result": ready,
        }
    ]
    if ready.get("ok"):
        return None, actions

    # Zombie Inventor.exe (often no UI) — ask to quit/restart instead of
    # claiming the app is "not installed" or telling the user to start it.
    ask = request_force_restart_inventor(
        reason=(
            "Inventor.exe is running in the background but the Bimwright MCP "
            "add-in has no live target (often a stuck session with no window). "
            "Quit and restart so a fresh Inventor + add-in can connect."
        ),
        soft_attempt=ready,
    )
    actions.append(
        {
            "tool": "recover_inventor",
            "arguments": {
                "app": "inventor",
                "force_restart": True,
                "reason": ask.get("reason"),
            },
            "result": ask,
        }
    )
    pending = _pending_launch_from_actions(actions)
    if pending:
        return pending, actions
    return None, [
        {
            "tool": fn,
            "arguments": {},
            "result": {
                "ok": False,
                "error": (
                    "Inventor.exe is running but no live add-in target is available. "
                    f"{ready.get('error') or ready}"
                ),
                "launch": ready,
                "retry": True,
                "audience": "assistant_only",
                "instruction": (
                    "FOR THE ASSISTANT ONLY — call recover_inventor with "
                    '{"force_restart": true, "reason": "no live add-in target"} '
                    "so the user can Confirm quitting Inventor.exe."
                ),
            },
        }
    ]


def _parse_tool_args(raw_args: str | dict) -> dict:
    if isinstance(raw_args, dict):
        return raw_args
    try:
        data = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _user_named_product(user_text: str, product: str) -> bool:
    lower = (user_text or "").lower()
    if product == "autocad":
        return "autocad" in lower or "auto cad" in lower or bool(re.search(r"\bacad\b", lower))
    if product == "inventor":
        return "inventor" in lower
    return False


def _guard_meta_tool(
    fn: str,
    raw_args: str | dict,
    *,
    track: str,
    user_text: str,
) -> str | None:
    """
    Block spurious mode-switch tool calls from small models.
    Launch is tool-driven only (no regex) — request_launch_cad runs normally.
    """
    if fn != "request_track_switch":
        return None
    args = _parse_tool_args(raw_args)
    to_track = (args.get("to_track") or "").lower().strip()
    if to_track == track:
        return json.dumps(
            {
                "error": (
                    f"Already in {track} mode. Do not switch — "
                    f"use {track}_* tools for the user's request."
                )
            }
        )
    if to_track in {"inventor", "autocad"} and not _user_named_product(
        user_text, to_track
    ):
        return json.dumps(
            {
                "error": (
                    f"Switch to {to_track} blocked: the user did not ask for "
                    f"{to_track} by name. Stay in {track} mode and use "
                    f"{track}_* tools (e.g. modeling/drawing in this mode)."
                )
            }
        )
    return None


def _force_pending_switch(
    dispatch: dict, track: str, to_track: str, reason: str
) -> tuple[dict[str, Any], list[dict]]:
    out = run_tool(
        dispatch,
        "request_track_switch",
        {"to_track": to_track, "reason": reason},
    )
    actions = [{"tool": "request_track_switch", "result": json.loads(out)}]
    pending = _pending_switch_from_actions(actions, track)
    return pending or {
        "from_track": track,
        "to_track": to_track,
        "reason": reason,
        "prompt": f"Switch to {to_track}?",
    }, actions


def _demo_reply_for_track(user_text: str, dispatch: dict, track: str) -> tuple[str, list[dict]]:
    """Demo path scoped to the active CAD track."""
    actions: list[dict] = []
    lower = user_text.lower()
    bits: list[str] = [f"[demo mode — {track} track]"]

    if "health" in lower:
        out = run_tool(dispatch, "health", {})
        actions.append({"tool": "health", "result": json.loads(out)})
        bits.append(f"health → {out}")

    if "echo" in lower or "hello from" in lower:
        out = run_tool(dispatch, "echo", {"message": "hello from Autodesk-MCP"})
        actions.append({"tool": "echo", "result": json.loads(out)})
        bits.append(f"echo → {out}")

    if _research_intent(user_text) or any(
        k in lower for k in ("google", "wikipedia", "internet", "web_search")
    ):
        out = run_tool(
            dispatch,
            "web_search",
            {"query": _research_query(user_text), "max_results": 5},
        )
        actions.append(
            {
                "tool": "web_search",
                "arguments": {"query": _research_query(user_text)},
                "result": json.loads(out),
            }
        )
        bits.append(f"web_search → {out}")
        return "\n".join(bits), actions

    if "flange" in lower or "thickness" in lower or "layer" in lower or "knowledge" in lower or "search" in lower:
        out = run_tool(dispatch, "knowledge_search", {"query": user_text, "top_k": 4})
        actions.append({"tool": "knowledge_search", "result": json.loads(out)})
        bits.append(f"knowledge_search → {out}")

    if track == "inventor":
        if "inventor" in lower or "demoflange" in lower or "part" in lower or "parameter" in lower or len(actions) == 0:
            out = run_tool(dispatch, "inventor_create_part", {"name": "DemoFlange"})
            actions.append({"tool": "inventor_create_part", "result": json.loads(out)})
            bits.append(f"inventor_create_part → {out}")
            out2 = run_tool(
                dispatch,
                "inventor_set_parameter",
                {"name": "Thickness", "expression": "8 mm"},
            )
            actions.append({"tool": "inventor_set_parameter", "result": json.loads(out2)})
            bits.append(f"inventor_set_parameter → {out2}")
            if "export" in lower or "rag" in lower:
                out3 = run_tool(dispatch, "inventor_export_to_rag", {})
                actions.append({"tool": "inventor_export_to_rag", "result": json.loads(out3)})
                bits.append(f"inventor_export_to_rag → {out3}")
    else:
        if "autocad" in lower or "rectangle" in lower or "walls" in lower or "layer" in lower or len(actions) == 0:
            out = run_tool(
                dispatch,
                "autocad_create_rectangle",
                {"width": 100, "height": 50, "layer": "WALLS"},
            )
            actions.append({"tool": "autocad_create_rectangle", "result": json.loads(out)})
            bits.append(f"autocad_create_rectangle → {out}")
            out2 = run_tool(dispatch, "autocad_list_layers", {})
            actions.append({"tool": "autocad_list_layers", "result": json.loads(out2)})
            bits.append(f"autocad_list_layers → {out2}")
            if "export" in lower or "rag" in lower:
                out3 = run_tool(dispatch, "autocad_export_to_rag", {})
                actions.append({"tool": "autocad_export_to_rag", "result": json.loads(out3)})
                bits.append(f"autocad_export_to_rag → {out3}")

    if len(actions) == 0:
        bits.append("No matching demo keywords for this track.")
    return "\n".join(bits), actions


async def chat(
    messages: list[dict[str, Any]],
    dispatch: dict,
    track: str = "inventor",
    cancelled: Callable[[], Awaitable[bool]] | None = None,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    base_modelling_kit: bool = False,
) -> dict[str, Any]:
    track = (track or "inventor").lower().strip()
    if track not in {"inventor", "autocad"}:
        track = "inventor"
    base_modelling_kit = bool(base_modelling_kit)

    async def _cancelled() -> bool:
        if cancelled is None:
            return False
        try:
            return bool(await cancelled())
        except Exception:  # noqa: BLE001
            return False

    async def _emit(event: dict[str, Any]) -> None:
        if on_event is None:
            return
        try:
            await on_event(event)
        except Exception:  # noqa: BLE001 — progress is best-effort
            pass

    mode = await resolve_mode()
    user_text = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )

    wanted = _cross_track_target(user_text, track)
    wants_model = _modeling_intent(user_text)
    wants_research = _research_intent(user_text) and not base_modelling_kit
    # Only ask to launch CAD when the user actually wants CAD work — never for
    # google/search/general chat (even while sitting in AutoCAD mode).
    wants_cad_preflight = wants_model and not wants_research

    if mode == "demo":
        if wanted:
            label = "AutoCAD" if wanted == "autocad" else "Inventor"
            pending, actions = _force_pending_switch(
                dispatch,
                track,
                wanted,
                f"You asked about {label} while in {track} mode",
            )
            return {
                "mode": "demo",
                "track": track,
                "reply": _switch_reply(pending),
                "actions": actions,
                "pending_switch": pending,
            }
        pre_actions: list[dict] = []
        if wants_cad_preflight:
            probe = (
                "autocad_create_rectangle"
                if track == "autocad"
                else "inventor_create_part"
            )
            pending_pre, pre_actions = _preflight_launch_if_needed(
                dispatch, probe, drawing_path=_extract_drawing_path(user_text)
            )
            if pending_pre:
                return {
                    "mode": "demo",
                    "track": track,
                    "reply": _launch_reply(pending_pre),
                    "actions": pre_actions,
                    "pending_launch": pending_pre,
                }
        reply, actions = _demo_reply_for_track(user_text, dispatch, track)
        if pre_actions:
            actions = pre_actions + actions
        return {"mode": "demo", "track": track, "reply": reply, "actions": actions}

    base, model, key, max_tokens = _client_config_full()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    actions: list[dict] = []
    # Cross-product request: ask to switch BEFORE opening the current-track app.
    if wanted:
        label = "AutoCAD" if wanted == "autocad" else "Inventor"
        pending, switch_actions = _force_pending_switch(
            dispatch,
            track,
            wanted,
            f"You asked about {label} while in {track} mode",
        )
        return {
            "mode": "live",
            "track": track,
            "reply": _switch_reply(pending),
            "actions": switch_actions,
            "pending_switch": pending,
        }
    # Early CAD launch only for modeling requests. Per-tool preflight still
    # covers the case where the model reaches for autocad_*/inventor_* later.
    if wants_cad_preflight and track in {"autocad", "inventor"}:
        open_path = _extract_drawing_path(user_text) if track == "autocad" else None
        if track == "autocad":
            probe = "autocad_drawing_open" if open_path else "autocad_drawing_new"
        else:
            probe = "inventor_new_part"
        pending_pre, pre_actions = await asyncio.to_thread(
            _preflight_launch_if_needed,
            dispatch,
            probe,
            drawing_path=open_path,
        )
        if pending_pre:
            for a in pre_actions:
                await _emit(
                    {
                        "type": "tool_end",
                        "tool": a.get("tool"),
                        "arguments": a.get("arguments"),
                        "result": a.get("result"),
                    }
                )
            return {
                "mode": "live",
                "track": track,
                "reply": _launch_reply(pending_pre),
                "actions": pre_actions,
                "pending_launch": pending_pre,
            }
        # Prep failed (not installed / ensure failed without a Confirm card)
        first = (pre_actions[0] if pre_actions else {}) or {}
        first_result = first.get("result") or {}
        if (
            pre_actions
            and not first_result.get("needs_confirmation")
            and not first_result.get("ok")
            and (
                first_result.get("error")
                or first.get("tool")
                in {
                    "autocad_drawing_new",
                    "autocad_drawing_open",
                    "inventor_new_part",
                    "request_launch_cad",
                }
            )
        ):
            for a in pre_actions:
                await _emit(
                    {
                        "type": "tool_end",
                        "tool": a.get("tool"),
                        "arguments": a.get("arguments"),
                        "result": a.get("result"),
                    }
                )
            err = first_result.get("error") or (
                "AutoCAD could not be prepared."
                if track == "autocad"
                else "Inventor could not be prepared."
            )
            return {
                "mode": "live",
                "track": track,
                "reply": str(err),
                "actions": pre_actions,
            }

    # Strip UI-only meta before sending to the LLM
    working = [
        {"role": m["role"], "content": m.get("content") or ""}
        for m in messages
        if m.get("role") in {"user", "assistant"}
    ]

    system = {
        "role": "system",
        "content": _system_prompt(track, base_modelling_kit=base_modelling_kit),
    }
    working = [system, *working]
    tools = tool_specs(track, base_modelling_kit=base_modelling_kit)
    forced_schema_retries = 0
    forced_modeling_retries = 0
    forced_research_retries = 0
    host_web_forced = False
    retry_streak = 0
    retry_tool: str | None = None

    # Large local models (e.g. qwen3:14b on CPU) need long per-request budgets.
    async with httpx.AsyncClient(timeout=900.0) as client:
        # No fixed round cap — stop when the model finishes, the user hits Stop
        # (client disconnect), or launch/switch Confirm is needed.
        while True:
            if await _cancelled():
                return {
                    "mode": "live",
                    "track": track,
                    "reply": "Stopped.",
                    "actions": actions,
                    "stopped": True,
                }
            payload: dict[str, Any] = {
                "model": model,
                "messages": working,
                "tools": tools,
                # Claude OpenAI-compat often requires max_tokens; harmless elsewhere.
                "max_tokens": max_tokens,
            }
            # Small models often ignore web_search among 100+ CAD tools — force it.
            if (
                wants_research
                and not _has_web_actions(actions)
                and not host_web_forced
                and forced_research_retries == 0
            ):
                payload["tool_choice"] = {
                    "type": "function",
                    "function": {"name": "web_search"},
                }
            r = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
            if (
                r.status_code >= 400
                and "tool_choice" in payload
            ):
                # Some local servers reject tool_choice — retry without it.
                payload.pop("tool_choice", None)
                r = await client.post(
                    f"{base}/chat/completions", headers=headers, json=payload
                )
            if r.status_code >= 400:
                return {
                    "mode": "live",
                    "track": track,
                    "error": f"LLM error {r.status_code}: {r.text[:500]}",
                    "reply": "",
                    "actions": actions,
                }
            data = r.json()
            choices = data.get("choices") or []
            if not choices:
                return {
                    "mode": "live",
                    "track": track,
                    "error": f"LLM returned no choices: {str(data)[:500]}",
                    "reply": "",
                    "actions": actions,
                }
            choice = choices[0].get("message") or {}
            content = choice.get("content") or ""
            tool_calls = choice.get("tool_calls") or []
            # Small models often print {"name":"...","arguments":{...}} as text
            # instead of native tool_calls — recover and execute them.
            if not tool_calls:
                allowed_names = {t["function"]["name"] for t in tools}
                recovered = _tool_calls_from_text(content, allowed_names)
                if recovered:
                    tool_calls = recovered
                    content = ""
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": content,
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            working.append(assistant_msg)
            if not tool_calls:
                reply = content or "(empty reply)"
                # Internet research: nudge, then host-run web_search if the model skips it.
                if wants_research and not _has_web_actions(actions):
                    if forced_research_retries < 1:
                        forced_research_retries += 1
                        working.append(
                            {
                                "role": "user",
                                "content": (
                                    "[host] Call web_search NOW with a short query for the "
                                    "user's question. Use native tool_calls — do not answer "
                                    "from memory and do not paste JSON in the chat."
                                ),
                            }
                        )
                        continue
                    if not host_web_forced:
                        host_web_forced = True
                        q = _research_query(user_text)
                        args = {"query": q, "max_results": 5}
                        await _emit(
                            {
                                "type": "tool_start",
                                "tool": "web_search",
                                "arguments": args,
                            }
                        )
                        result = await asyncio.to_thread(
                            run_tool, dispatch, "web_search", args
                        )
                        try:
                            parsed = json.loads(result)
                        except json.JSONDecodeError:
                            parsed = {"raw": result}
                        actions.append(
                            {
                                "tool": "web_search",
                                "arguments": args,
                                "result": parsed,
                            }
                        )
                        await _emit(
                            {
                                "type": "tool_end",
                                "tool": "web_search",
                                "arguments": args,
                                "result": parsed,
                            }
                        )
                        working.append(
                            {
                                "role": "user",
                                "content": (
                                    f"[host] web_search results for {q!r}:\n{result}\n\n"
                                    "Answer the user in plain English using these results. "
                                    "Include 1–3 source links. Do not mention tool names."
                                ),
                            }
                        )
                        continue
                # Small models dump validation errors instead of retrying — push them back.
                retryable = _last_retryable_tool_error(actions)
                if (
                    retryable
                    and forced_schema_retries < 2
                    and retry_streak < 3
                    and not _looks_like_tool_transcript(reply)
                ):
                    forced_schema_retries += 1
                    tool_name = retryable.get("tool") or "the tool"
                    working.append(
                        {
                            "role": "user",
                            "content": (
                                f"[host] {tool_name} failed argument validation. "
                                f"Call {tool_name} again with corrected arguments from its "
                                f"tool schema. Do not explain schemas, pydantic, or JSON "
                                f"examples to the user — just retry the tool call. "
                                f"Never paste tool names, arguments, or results into the chat."
                            ),
                        }
                    )
                    continue
                reply = _sanitize_user_reply(reply, actions)
                # Model narrated a plan / fake code instead of calling CAD tools
                cad_actions = [
                    a
                    for a in actions
                    if str(a.get("tool") or "").startswith(("inventor_", "autocad_"))
                ]
                if (
                    wants_model
                    and not cad_actions
                    and forced_modeling_retries < 2
                    and (_looks_like_tool_avoidance(reply) or len(actions) == 0)
                ):
                    forced_modeling_retries += 1
                    working.append(
                        {"role": "user", "content": _modeling_nudge(track)}
                    )
                    continue
                # Small models often *talk* about switching but skip the tool —
                # still show Confirm/Cancel when the other CAD product is needed.
                if wanted and not _pending_switch_from_actions(actions, track):
                    label = "AutoCAD" if wanted == "autocad" else "Inventor"
                    pending, switch_actions = _force_pending_switch(
                        dispatch,
                        track,
                        wanted,
                        f"You asked about {label} while in {track} mode",
                    )
                    actions.extend(switch_actions)
                    if "confirm" not in reply.lower():
                        reply = f"{reply}\n\n{_switch_reply(pending)}".strip()
                    return {
                        "mode": "live",
                        "track": track,
                        "reply": reply,
                        "actions": actions,
                        "pending_switch": pending,
                    }
                # Launch is tool-only — never force from regex / prose heuristics.
                # Avoid empty bubbles after web research (small models often go blank).
                if (not reply or reply == "(empty reply)") and _has_web_actions(
                    actions
                ):
                    last_web = next(
                        (
                            a
                            for a in reversed(actions)
                            if a.get("tool") in {"web_search", "web_fetch"}
                        ),
                        None,
                    )
                    res = (last_web or {}).get("result") or {}
                    hits = res.get("results") if isinstance(res, dict) else None
                    if isinstance(hits, list) and hits:
                        lines = []
                        for h in hits[:5]:
                            title = (h.get("title") or "").strip()
                            url = (h.get("url") or "").strip()
                            snip = (h.get("snippet") or "").strip()
                            if title and url:
                                lines.append(
                                    f"- **{title}** — {snip}".rstrip(" —")
                                    + f"\n  {url}"
                                )
                        reply = (
                            "Here's what I found online:\n\n" + "\n".join(lines)
                            if lines
                            else (
                                "I looked that up online — see web_search in Worked."
                            )
                        )
                    elif isinstance(res, dict) and res.get("error"):
                        reply = (
                            "I tried to search the web but the search providers "
                            "returned no usable results. "
                            f"You can open {res.get('search_url') or 'a search page'} "
                            "directly, or set BRAVE_API_KEY for more reliable search."
                        )
                    else:
                        reply = (
                            "I looked that up online — see the web_search results "
                            "in Worked for sources."
                        )
                return {
                    "mode": "live",
                    "track": track,
                    "reply": reply,
                    "actions": actions,
                }
            allowed = {t["function"]["name"] for t in tools}
            for call in tool_calls:
                fn = (call.get("function") or {}).get("name") or "unknown"
                raw_args = (call.get("function") or {}).get("arguments") or "{}"
                if not isinstance(raw_args, str):
                    raw_args = json.dumps(raw_args)
                await _emit(
                    {
                        "type": "tool_start",
                        "tool": fn,
                        "arguments": _parse_tool_args(raw_args),
                    }
                )
                if fn not in allowed:
                    result = json.dumps(
                        {"error": f"tool {fn} blocked — active track is {track}"}
                    )
                else:
                    guarded = _guard_meta_tool(
                        fn,
                        raw_args,
                        track=track,
                        user_text=user_text,
                    )
                    if guarded is not None:
                        result = guarded
                    else:
                        # Preflight: AutoCAD auto-starts+drawing; Inventor auto-starts+part.
                        tool_args = _parse_tool_args(raw_args)
                        open_path = None
                        if fn == "autocad_drawing_open":
                            open_path = (
                                tool_args.get("path")
                                or tool_args.get("file")
                                or _extract_drawing_path(user_text)
                            )
                        else:
                            open_path = _extract_drawing_path(user_text)
                        pending_pre, pre_actions = await asyncio.to_thread(
                            _preflight_launch_if_needed,
                            dispatch,
                            fn,
                            drawing_path=open_path,
                        )
                        if pending_pre:
                            actions.extend(pre_actions)
                            for a in pre_actions:
                                await _emit(
                                    {
                                        "type": "tool_end",
                                        "tool": a.get("tool"),
                                        "arguments": a.get("arguments"),
                                        "result": a.get("result"),
                                    }
                                )
                            return {
                                "mode": "live",
                                "track": track,
                                "reply": _launch_reply(pending_pre),
                                "actions": actions,
                                "pending_launch": pending_pre,
                            }
                        if pre_actions:
                            # Record ensure_autocad_ready / launch prep in the transcript
                            for a in pre_actions:
                                if a.get("tool") == fn:
                                    continue
                                actions.append(a)
                                await _emit(
                                    {
                                        "type": "tool_end",
                                        "tool": a.get("tool"),
                                        "arguments": a.get("arguments"),
                                        "result": a.get("result"),
                                    }
                                )
                        if pre_actions and pre_actions[0].get("tool") == fn:
                            # Not installed / cannot launch — let the LLM explain
                            parsed = pre_actions[0].get("result") or {}
                            result = json.dumps(parsed, ensure_ascii=False)
                            actions.append(
                                {
                                    "tool": fn,
                                    "arguments": raw_args,
                                    "result": parsed,
                                }
                            )
                            await _emit(
                                {
                                    "type": "tool_end",
                                    "tool": fn,
                                    "arguments": _parse_tool_args(raw_args),
                                    "result": parsed,
                                }
                            )
                            working.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.get("id") or fn,
                                    "content": result,
                                }
                            )
                            continue

                        # MCP stdio client owns its own loop thread; run sync tools
                        # off the uvicorn loop so we never nest event loops.
                        result = await asyncio.to_thread(
                            run_tool, dispatch, fn, raw_args
                        )
                try:
                    parsed = json.loads(result)
                except json.JSONDecodeError:
                    parsed = {"raw": result}
                # Upstream sometimes returns ok:true while every layer/entity failed COM.
                if isinstance(parsed, dict) and isinstance(parsed.get("layers"), dict):
                    layer_vals = list(parsed["layers"].values())
                    if layer_vals and all(
                        isinstance(v, str) and "failed" in v.lower() for v in layer_vals
                    ):
                        parsed = {
                            **parsed,
                            "ok": False,
                            "error": (
                                "AutoCAD COM could not create layers (<unknown>.Count). "
                                "AutoCAD must be running with a real drawing open."
                            ),
                            "retry": False,
                            "audience": "assistant_only",
                        }
                        result = json.dumps(parsed, ensure_ascii=False)
                actions.append({"tool": fn, "arguments": raw_args, "result": parsed})
                await _emit(
                    {
                        "type": "tool_end",
                        "tool": fn,
                        "arguments": _parse_tool_args(raw_args),
                        "result": parsed,
                    }
                )
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or fn,
                        "content": result,
                    }
                )

                # Launch / quit-restart Confirm — stop the tool loop immediately.
                if (
                    isinstance(parsed, dict)
                    and parsed.get("needs_confirmation")
                    and parsed.get("app") in {"inventor", "autocad"}
                ):
                    pending_ask = _pending_launch_from_actions(actions) or {
                        "app": parsed.get("app"),
                        "action": parsed.get("action"),
                        "reason": parsed.get("reason") or "",
                        "prompt": parsed.get("prompt"),
                        "drawing_path": parsed.get("drawing_path"),
                        "status": parsed.get("status") or {},
                    }
                    return {
                        "mode": "live",
                        "track": track,
                        "reply": _launch_reply(pending_ask),
                        "actions": actions,
                        "pending_launch": pending_ask,
                    }

                # Stop thrashing the same broken tool (small models loop on validation).
                err_blob = json.dumps(parsed).lower() if isinstance(parsed, dict) else ""
                is_retry = bool(isinstance(parsed, dict) and parsed.get("retry"))
                is_com = any(
                    k in err_blob
                    for k in (
                        ".count",
                        "no drawing",
                        "no document",
                        "rpc server is unavailable",
                        "0x800706ba",
                        "-0x7ff8f946",
                    )
                )
                is_no_target = any(
                    k in err_blob
                    for k in (
                        "no_target",
                        "no target",
                        "no live inventor",
                        "no live ipt",
                        "targets empty",
                        "no available target",
                        "could not be started with a live",
                    )
                )
                failed = bool(
                    isinstance(parsed, dict)
                    and (parsed.get("ok") is False or parsed.get("error") or is_retry)
                )
                if failed:
                    if fn == retry_tool:
                        retry_streak += 1
                    else:
                        retry_tool = fn
                        retry_streak = 1
                else:
                    retry_streak = 0
                    retry_tool = None

                # Host recovery: open AutoCAD + drawing, then retry the same tool once.
                if (
                    is_com
                    and fn.startswith("autocad_")
                    and not (isinstance(parsed, dict) and parsed.get("host_recovered"))
                    and retry_streak <= 2
                ):
                    ready = await asyncio.to_thread(
                        _soft_then_hard_recover,
                        wait_s=90.0,
                        reason=(
                            f"Tool {fn} failed with COM/RPC while AutoCAD appears "
                            "running but not responding."
                        ),
                    )
                    actions.append(
                        {
                            "tool": "recover_autocad",
                            "arguments": {
                                "app": "autocad",
                                "force_reset": True,
                                "recovery": ready.get("recovery"),
                            },
                            "result": ready,
                        }
                    )
                    await _emit(
                        {
                            "type": "tool_end",
                            "tool": "recover_autocad",
                            "arguments": {"app": "autocad"},
                            "result": ready,
                        }
                    )
                    if ready.get("needs_confirmation"):
                        pending_ask = _pending_launch_from_actions(actions) or {
                            "app": ready.get("app") or "autocad",
                            "action": ready.get("action"),
                            "reason": ready.get("reason") or "",
                            "prompt": ready.get("prompt"),
                            "drawing_path": ready.get("drawing_path"),
                            "status": ready.get("status") or {},
                        }
                        return {
                            "mode": "live",
                            "track": track,
                            "reply": _launch_reply(pending_ask),
                            "actions": actions,
                            "pending_launch": pending_ask,
                        }
                    if ready.get("ok"):
                        result = await asyncio.to_thread(
                            run_tool, dispatch, fn, raw_args
                        )
                        try:
                            parsed = json.loads(result)
                        except json.JSONDecodeError:
                            parsed = {"raw": result}
                        if isinstance(parsed, dict):
                            parsed = {**parsed, "host_recovered": True, "launch": ready}
                            result = json.dumps(parsed, ensure_ascii=False)
                        actions.append(
                            {"tool": fn, "arguments": raw_args, "result": parsed}
                        )
                        await _emit(
                            {
                                "type": "tool_end",
                                "tool": fn,
                                "arguments": _parse_tool_args(raw_args),
                                "result": parsed,
                            }
                        )
                        working[-1] = {
                            "role": "tool",
                            "tool_call_id": call.get("id") or fn,
                            "content": result,
                        }
                        err_blob = (
                            json.dumps(parsed).lower()
                            if isinstance(parsed, dict)
                            else ""
                        )
                        failed = bool(
                            isinstance(parsed, dict)
                            and (
                                parsed.get("ok") is False
                                or parsed.get("error")
                            )
                        )
                        if not failed:
                            retry_streak = 0
                            retry_tool = None

                # Host recovery: open Inventor + part, then retry the same tool once.
                if (
                    is_no_target
                    and fn.startswith("inventor_")
                    and not (isinstance(parsed, dict) and parsed.get("host_recovered"))
                    and retry_streak <= 2
                ):
                    ready = await asyncio.to_thread(
                        _soft_then_hard_recover_inventor,
                        wait_s=90.0,
                        reason=(
                            f"Tool {fn} failed with NO_TARGET while Inventor appears "
                            "running but the add-in is not connected."
                        ),
                    )
                    actions.append(
                        {
                            "tool": "recover_inventor",
                            "arguments": {
                                "app": "inventor",
                                "force_reset": True,
                                "recovery": ready.get("recovery"),
                            },
                            "result": ready,
                        }
                    )
                    await _emit(
                        {
                            "type": "tool_end",
                            "tool": "recover_inventor",
                            "arguments": {"app": "inventor"},
                            "result": ready,
                        }
                    )
                    if ready.get("needs_confirmation"):
                        pending_ask = _pending_launch_from_actions(actions) or {
                            "app": ready.get("app") or "inventor",
                            "action": ready.get("action"),
                            "reason": ready.get("reason") or "",
                            "prompt": ready.get("prompt"),
                            "status": ready.get("status") or {},
                        }
                        return {
                            "mode": "live",
                            "track": track,
                            "reply": _launch_reply(pending_ask),
                            "actions": actions,
                            "pending_launch": pending_ask,
                        }
                    if ready.get("ok"):
                        result = await asyncio.to_thread(
                            run_tool, dispatch, fn, raw_args
                        )
                        try:
                            parsed = json.loads(result)
                        except json.JSONDecodeError:
                            parsed = {"raw": result}
                        if isinstance(parsed, dict):
                            parsed = {**parsed, "host_recovered": True, "launch": ready}
                            result = json.dumps(parsed, ensure_ascii=False)
                        actions.append(
                            {"tool": fn, "arguments": raw_args, "result": parsed}
                        )
                        await _emit(
                            {
                                "type": "tool_end",
                                "tool": fn,
                                "arguments": _parse_tool_args(raw_args),
                                "result": parsed,
                            }
                        )
                        working[-1] = {
                            "role": "tool",
                            "tool_call_id": call.get("id") or fn,
                            "content": result,
                        }
                        failed = bool(
                            isinstance(parsed, dict)
                            and (
                                parsed.get("ok") is False
                                or parsed.get("error")
                            )
                        )
                        if not failed:
                            retry_streak = 0
                            retry_tool = None

                if retry_streak >= 4:
                    return {
                        "mode": "live",
                        "track": track,
                        "reply": _sanitize_user_reply(
                            f"tool transcript\n{fn}\n{json.dumps(parsed)}",
                            actions,
                        ),
                        "actions": actions,
                    }

            pending = _pending_switch_from_actions(actions, track)
            if pending:
                # Stop here — UI must Confirm/Cancel before changing mode
                reply = (assistant_msg.get("content") or "").strip() or _switch_reply(pending)
                reply = _sanitize_user_reply(reply, actions)
                if "confirm" not in reply.lower() and "cancel" not in reply.lower():
                    reply = f"{reply}\n\n{_switch_reply(pending)}".strip()
                return {
                    "mode": "live",
                    "track": track,
                    "reply": reply,
                    "actions": actions,
                    "pending_switch": pending,
                }

            pending_launch = _pending_launch_from_actions(actions)
            if pending_launch:
                # Stop here — use our short reply so text always matches the buttons
                return {
                    "mode": "live",
                    "track": track,
                    "reply": _launch_reply(pending_launch),
                    "actions": actions,
                    "pending_launch": pending_launch,
                }

            # Other tool errors stay in `actions` / working messages for the LLM
            # to explain on the next round.
            if await _cancelled():
                return {
                    "mode": "live",
                    "track": track,
                    "reply": "Stopped.",
                    "actions": actions,
                    "stopped": True,
                }
