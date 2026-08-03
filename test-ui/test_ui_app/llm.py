from __future__ import annotations

import json
import os
from typing import Any

import httpx

from test_ui_app.tools import run_tool, tool_specs


def llm_mode() -> str:
    mode = os.getenv("LLM_MODE", "auto").lower().strip()
    if mode in {"auto", "live", "demo"}:
        return mode
    return "auto"


def _client_config() -> tuple[str, str, str]:
    base = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "llama3.2")
    key = os.getenv("LLM_API_KEY", "") or "no-key"
    return base, model, key


async def _probe_live(base: str, key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            return r.status_code < 500
    except Exception:
        return False


async def resolve_mode() -> str:
    mode = llm_mode()
    if mode != "auto":
        return mode
    base, _, key = _client_config()
    return "live" if await _probe_live(base, key) else "demo"


def _demo_reply(user_text: str, dispatch: dict) -> tuple[str, list[dict]]:
    """Deterministic demo path when no LLM is available."""
    actions: list[dict] = []
    lower = user_text.lower()
    bits: list[str] = ["[demo mode - no live LLM]"]

    if "health" in lower:
        out = run_tool(dispatch, "health", {})
        actions.append({"tool": "health", "result": json.loads(out)})
        bits.append(f"health → {out}")

    if "echo" in lower or "hello from" in lower:
        msg = "hello from Autodesk-MCP test UI"
        out = run_tool(dispatch, "echo", {"message": msg})
        actions.append({"tool": "echo", "result": json.loads(out)})
        bits.append(f"echo → {out}")

    if "flange" in lower or "thickness" in lower or "layer" in lower or "knowledge" in lower or "search" in lower:
        q = user_text
        out = run_tool(dispatch, "knowledge_search", {"query": q, "top_k": 4})
        actions.append({"tool": "knowledge_search", "result": json.loads(out)})
        bits.append(f"knowledge_search → {out}")

    if "inventor" in lower or "demoflange" in lower or "part" in lower:
        out = run_tool(dispatch, "mock_inventor_create_part", {"name": "DemoFlange"})
        actions.append({"tool": "mock_inventor_create_part", "result": json.loads(out)})
        bits.append(f"mock_inventor_create_part → {out}")
        if "thickness" in lower or "8" in lower or "parameter" in lower:
            out2 = run_tool(
                dispatch,
                "mock_inventor_set_parameter",
                {"name": "Thickness", "expression": "8 mm"},
            )
            actions.append({"tool": "mock_inventor_set_parameter", "result": json.loads(out2)})
            bits.append(f"mock_inventor_set_parameter → {out2}")

    if "autocad" in lower or "rectangle" in lower or "walls" in lower:
        out = run_tool(
            dispatch,
            "mock_autocad_create_rectangle",
            {"width": 100, "height": 50, "layer": "WALLS"},
        )
        actions.append({"tool": "mock_autocad_create_rectangle", "result": json.loads(out)})
        bits.append(f"mock_autocad_create_rectangle → {out}")
        out2 = run_tool(dispatch, "mock_autocad_list_layers", {})
        actions.append({"tool": "mock_autocad_list_layers", "result": json.loads(out2)})
        bits.append(f"mock_autocad_list_layers → {out2}")

    if len(actions) == 0:
        bits.append(
            "No matching demo keywords. Try a sample from the sidebar, "
            "or set LLM_BASE_URL to a live OpenAI-compatible API."
        )
    return "\n".join(bits), actions


async def chat(
    messages: list[dict[str, Any]],
    dispatch: dict,
) -> dict[str, Any]:
    mode = await resolve_mode()
    user_text = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )

    if mode == "demo":
        reply, actions = _demo_reply(user_text, dispatch)
        return {"mode": "demo", "reply": reply, "actions": actions}

    base, model, key = _client_config()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    actions: list[dict] = []
    working = list(messages)

    system = {
        "role": "system",
        "content": (
            "You are the Autodesk-MCP test assistant. "
            "Use tools for health, knowledge_search, and mock Inventor/AutoCAD actions. "
            "Prefer tools over guessing company standards."
        ),
    }
    if not working or working[0].get("role") != "system":
        working = [system, *working]

    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(6):
            payload = {
                "model": model,
                "messages": working,
                "tools": tool_specs(),
                "tool_choice": "auto",
            }
            r = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
            if r.status_code >= 400:
                return {
                    "mode": "live",
                    "error": f"LLM error {r.status_code}: {r.text[:500]}",
                    "reply": "",
                    "actions": actions,
                }
            data = r.json()
            choice = data["choices"][0]["message"]
            working.append(choice)
            tool_calls = choice.get("tool_calls") or []
            if not tool_calls:
                return {
                    "mode": "live",
                    "reply": choice.get("content") or "",
                    "actions": actions,
                }
            for call in tool_calls:
                fn = call["function"]["name"]
                raw_args = call["function"].get("arguments") or "{}"
                result = run_tool(dispatch, fn, raw_args)
                try:
                    parsed = json.loads(result)
                except json.JSONDecodeError:
                    parsed = {"raw": result}
                actions.append({"tool": fn, "arguments": raw_args, "result": parsed})
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", fn),
                        "content": result,
                    }
                )

    return {
        "mode": "live",
        "reply": "Stopped after max tool rounds.",
        "actions": actions,
    }
