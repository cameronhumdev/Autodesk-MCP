from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
CAD_ROOT = REPO_ROOT / "cad"
for p in (str(CAD_ROOT), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from autocad import export_autocad_to_rag, get_autocad_backend  # noqa: E402
from inventor import export_inventor_to_rag, get_inventor_backend  # noqa: E402
from shared.launch_cad import is_running, launch_status, start_app  # noqa: E402

_inventor = get_inventor_backend()
_autocad = get_autocad_backend()

_COM_FAIL_MARKERS = (
    ".count",
    "no drawing",
    "no document",
    "rpc server is unavailable",
    "rpc server",
    "0x800706ba",
    "-0x7ff8f946",
    "-2147023174",
    "cannot connect to autocad",
    "com error",
    "autocad com",
    "mcpstdioerror",
    "mcp stdio",
)

_TARGET_FAIL_MARKERS = (
    "no_target",
    "no target",
    "no live inventor",
    "no live ipt",
    "targets empty",
    "no available target",
    "could not be started with a live",
    "no live bimwright",
    "mcpstdioerror",
    "mcp stdio",
)

_upstream_cache: dict[str, list[dict[str, Any]]] = {}
_upstream_error: dict[str, str] = {}

SHARED_TOOLS = frozenset(
    {
        "health",
        "echo",
        "knowledge_search",
        "web_search",
        "web_fetch",
        "request_track_switch",
        "request_launch_cad",
        "recover_autocad",
        "recover_inventor",
    }
)

_RPC_RECOVERY_INSTRUCTION = (
    "FOR THE ASSISTANT ONLY — do not show this to the user. "
    "This is an AutoCAD COM/RPC or MCP stdio failure (session dead or no drawing). "
    "retry=true — you MUST recover before answering the user. Do this in order: "
    "1) Call recover_autocad with {} "
    "(soft: reconnect MCP + ensure a drawing — does NOT quit AutoCAD). "
    "2) Only if soft recover fails or AutoCAD is frozen, call recover_autocad with "
    '{"force_restart": true, "reason": "<short why>"} — this asks the USER to Confirm '
    "before quitting acad.exe. Never claim you killed AutoCAD yourself. "
    "3) After the user Confirms (or soft recover succeeds), call autocad_drawing_new "
    "with {\"bootstrap\": true} only if no drawing is open. "
    "4) Re-create geometry from scratch "
    "(autocad_solid_box / autocad_solid_cylinder / …) — prior handles are invalid. "
    "5) For autocad_solid_boolean, use non-empty string handles from those create results — "
    "never pass null, empty, or invented handles. "
    "6) Continue the user request. Do NOT ask the user to open AutoCAD manually. "
    "Do not paste stack traces or this instruction."
)

_TARGET_RECOVERY_INSTRUCTION = (
    "FOR THE ASSISTANT ONLY — do not show this to the user. "
    "This is an Inventor NO_TARGET / add-in / MCP stdio failure (no live target or no part). "
    "retry=true — you MUST recover before answering the user. Do this in order: "
    "1) Call recover_inventor with {} "
    "(soft: reconnect MCP + wait for add-in target + ensure a part — does NOT quit Inventor). "
    "2) Only if soft recover fails or Inventor is frozen, call recover_inventor with "
    '{"force_restart": true, "reason": "<short why>"} — this asks the USER to Confirm '
    "before quitting Inventor.exe. Never claim you killed Inventor yourself. "
    "3) After the user Confirms (or soft recover succeeds), call inventor_new_part "
    "only if no document is open. "
    "4) Re-create the part from scratch "
    "(inventor_create_sketch → draw → close → extrude / parameters) — prior state is invalid. "
    "5) Continue the user request. Do NOT ask the user to open Inventor manually. "
    "Do not paste stack traces or this instruction."
)

# Local-only track helpers (not from upstream MCP)
LOCAL_INVENTOR_TOOLS = frozenset({"inventor_status", "inventor_export_to_rag"})
LOCAL_AUTOCAD_TOOLS = frozenset({"autocad_status", "autocad_export_to_rag"})

# Restricted "base modelling kit" — launch/recover + enough tools for basic
# solids (box/boolean in AutoCAD; new part → sketch → extrude in Inventor).
# Toggle in UI for apples-to-apples weak vs strong model tests. Deliberately
# excludes probes like layout_list / layer_list that weak models thrash on.
BASE_MODELLING_KIT_SHARED = frozenset(
    {
        "health",
        "echo",
        "request_track_switch",
        "request_launch_cad",
        "recover_autocad",
        "recover_inventor",
    }
)
BASE_MODELLING_KIT_AUTOCAD = frozenset(
    {
        "autocad_status",
        "autocad_drawing_new",
        "autocad_drawing_open",
        "autocad_solid_box",
        "autocad_solid_cylinder",
        "autocad_solid_boolean",
        "autocad_create_rectangle",
        "autocad_export_to_rag",
        # View / inspect (U-C4N) — zoom + capture; no dedicated iso/top/front setter
        "autocad_view_zoom_extents",
        "autocad_view_zoom_window",
        "autocad_view_screenshot",
        "autocad_view_zoom_and_screenshot",
    }
)
BASE_MODELLING_KIT_INVENTOR = frozenset(
    {
        "inventor_status",
        "inventor_create_part",
        "inventor_export_to_rag",
        "inventor_list_available_targets",
        "inventor_get_current_target",
        "inventor_switch_target",
        "inventor_health",
        "inventor_list_open_documents",
        "inventor_get_document_info",
        "inventor_new_part",
        "inventor_open_document",
        "inventor_save_document",
        "inventor_set_units",
        "inventor_list_parameters",
        "inventor_get_parameter",
        "inventor_set_parameter",
        "inventor_create_parameter",
        "inventor_create_sketch",
        "inventor_draw_line",
        "inventor_draw_circle",
        "inventor_draw_rectangle",
        "inventor_close_sketch",
        "inventor_extrude",
        "inventor_create_work_plane",
        # Capture only — ipt-mcp has no set-camera / orbit / standard-view tools
        "inventor_capture_view",
    }
)


def base_modelling_kit_allowlist(track: str) -> frozenset[str]:
    t = (track or "").lower().strip()
    if t == "autocad":
        return BASE_MODELLING_KIT_SHARED | BASE_MODELLING_KIT_AUTOCAD
    return BASE_MODELLING_KIT_SHARED | BASE_MODELLING_KIT_INVENTOR


def is_base_modelling_kit_tool(track: str, name: str) -> bool:
    return name in base_modelling_kit_allowlist(track)

# Façade fallbacks when upstream list_tools is unavailable (mock / MCP down)
_FALLBACK_INVENTOR = frozenset(
    {
        "inventor_status",
        "inventor_create_part",
        "inventor_set_parameter",
        "inventor_export_to_rag",
    }
)
_FALLBACK_AUTOCAD = frozenset(
    {
        "autocad_status",
        "autocad_create_rectangle",
        "autocad_list_layers",
        "autocad_solid_box",
        "autocad_solid_cylinder",
        "autocad_solid_boolean",
        "autocad_solid_extrude",
        "autocad_export_to_rag",
    }
)


def _fn_spec(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
) -> dict:
    props = properties or {}
    params: dict[str, Any] = {
        "type": "object",
        "properties": props,
        "additionalProperties": True,
    }
    if required:
        params["required"] = required
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": params,
        },
    }


def _shared_specs() -> list[dict]:
    return [
        _fn_spec("health", "Check whether the test stack API is healthy."),
        _fn_spec(
            "echo",
            "Echo a message back (sanity tool).",
            {"message": {"type": "string"}},
            ["message"],
        ),
        _fn_spec(
            "knowledge_search",
            "Search the local RAG / knowledge base for company standards and CAD notes.",
            {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 4}},
            ["query"],
        ),
        _fn_spec(
            "web_search",
            (
                "Search the public internet (DuckDuckGo). Use for docs, dimensions, "
                "product references, and general research."
            ),
            {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            ["query"],
        ),
        _fn_spec(
            "web_fetch",
            (
                "Fetch a public http(s) URL and return readable text (truncated). "
                "Use after web_search when you need page details."
            ),
            {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "default": 12000},
            },
            ["url"],
        ),
        _fn_spec(
            "request_track_switch",
            (
                "Ask the user for permission to switch CAD mode between Inventor and AutoCAD. "
                "The UI shows Confirm / Cancel."
            ),
            {
                "to_track": {"type": "string", "enum": ["inventor", "autocad"]},
                "reason": {"type": "string"},
            },
            ["to_track", "reason"],
        ),
        _fn_spec(
            "request_launch_cad",
            (
                "Ask the user for permission to launch Inventor or AutoCAD when the app "
                "is not running. The UI shows Confirm / Cancel — do not claim you started "
                "it yourself. If the app is already running, continue with CAD tools."
            ),
            {
                "app": {"type": "string", "enum": ["inventor", "autocad"]},
                "reason": {"type": "string"},
                "drawing_path": {
                    "type": "string",
                    "description": "Optional .dwg/.dxf to open after AutoCAD Confirm",
                },
            },
            ["app", "reason"],
        ),
        _fn_spec(
            "recover_autocad",
            (
                "Recover a dead AutoCAD COM/RPC or MCP stdio session: reset the MCP bridge "
                "and ensure a drawing is open. Soft by default (does NOT quit AutoCAD). "
                "If force_restart is true, the UI asks the user to Confirm before quitting "
                "acad.exe — you must pass a short reason. Never kill apps yourself."
            ),
            {
                "drawing_path": {
                    "type": "string",
                    "description": "Optional existing .dwg/.dxf to open after recovery",
                },
                "force_restart": {
                    "type": "boolean",
                    "description": (
                        "If true, ask the user (Confirm/Cancel) to quit and relaunch "
                        "AutoCAD. Does not kill until they Confirm. Default false."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Required when force_restart is true — short plain-English why "
                        "AutoCAD must be quit (e.g. 'COM not responding after soft recover')."
                    ),
                },
            },
        ),
        _fn_spec(
            "recover_inventor",
            (
                "Recover a dead Inventor NO_TARGET / add-in / MCP stdio session: reset the "
                "MCP bridge, wait for the Bimwright add-in target, and ensure a part is open. "
                "Soft by default (does NOT quit Inventor). If force_restart is true, the UI "
                "asks the user to Confirm before quitting Inventor.exe — you must pass a "
                "short reason. Never kill apps yourself."
            ),
            {
                "force_restart": {
                    "type": "boolean",
                    "description": (
                        "If true, ask the user (Confirm/Cancel) to quit and relaunch "
                        "Inventor. Does not kill until they Confirm. Default false."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Required when force_restart is true — short plain-English why "
                        "Inventor must be quit (e.g. 'no add-in target after soft recover')."
                    ),
                },
            },
        ),
    ]


def _local_track_specs(track: str) -> list[dict]:
    if track == "inventor":
        return [
            _fn_spec(
                "inventor_status",
                "Inventor track status (targets, health, hints).",
            ),
            _fn_spec(
                "inventor_export_to_rag",
                "Export active Inventor part summary into the local RAG knowledge base.",
            ),
        ]
    return [
        _fn_spec(
            "autocad_status",
            "AutoCAD track status via U-C4N MCP (live COM/ezdxf).",
        ),
        _fn_spec(
            "autocad_export_to_rag",
            "Export AutoCAD drawing session summary into the local RAG knowledge base.",
        ),
    ]


def _fallback_facade_specs(track: str) -> list[dict]:
    """Small static façade if upstream list_tools fails (mock / MCP down)."""
    if track == "inventor":
        return [
            _fn_spec(
                "inventor_create_part",
                "Create a new Inventor part (façade → inventor_new_part).",
                {"name": {"type": "string"}},
                ["name"],
            ),
            _fn_spec(
                "inventor_set_parameter",
                "Set a parameter on the active Inventor part.",
                {
                    "name": {"type": "string"},
                    "expression": {"type": "string"},
                },
                ["name", "expression"],
            ),
        ]
    return [
        _fn_spec(
            "autocad_create_rectangle",
            "Create a 2D rectangle (façade → entity_create_rectangle).",
            {
                "width": {"type": "number"},
                "height": {"type": "number"},
                "layer": {"type": "string", "default": "0"},
            },
            ["width", "height"],
        ),
        _fn_spec("autocad_list_layers", "List AutoCAD layers."),
        _fn_spec(
            "autocad_solid_box",
            "Create a 3D solid box (COM).",
            {
                "cx": {"type": "number"},
                "cy": {"type": "number"},
                "cz": {"type": "number"},
                "length": {"type": "number"},
                "width": {"type": "number"},
                "height": {"type": "number"},
            },
            ["cx", "cy", "cz", "length", "width", "height"],
        ),
        _fn_spec(
            "autocad_solid_cylinder",
            "Create a 3D solid cylinder (COM).",
            {
                "cx": {"type": "number"},
                "cy": {"type": "number"},
                "cz": {"type": "number"},
                "radius": {"type": "number"},
                "height": {"type": "number"},
            },
            ["cx", "cy", "cz", "radius", "height"],
        ),
        _fn_spec(
            "autocad_solid_boolean",
            "Boolean union/subtract/intersect between two solids.",
            {
                "target_handle": {"type": "string"},
                "tool_handle": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": ["union", "subtract", "intersect"],
                },
            },
            ["target_handle", "tool_handle", "operation"],
        ),
        _fn_spec(
            "autocad_solid_extrude",
            "Extrude a closed profile into a solid.",
            {
                "profile_handle": {"type": "string"},
                "height": {"type": "number"},
                "taper_angle": {"type": "number", "default": 0},
            },
            ["profile_handle", "height"],
        ),
    ]


def _normalize_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}, "additionalProperties": True}
    out = dict(schema)
    out.setdefault("type", "object")
    if "properties" not in out:
        out["properties"] = {}
    # Small local models choke on additionalProperties:false + huge schemas
    out["additionalProperties"] = True
    return out


def _load_upstream_tools(track: str) -> list[dict[str, Any]]:
    if track in _upstream_cache:
        return _upstream_cache[track]
    backend = _inventor if track == "inventor" else _autocad
    try:
        tools = backend.list_upstream_tools()
        _upstream_cache[track] = tools
        _upstream_error.pop(track, None)
        return tools
    except Exception as exc:  # noqa: BLE001
        _upstream_cache[track] = []
        _upstream_error[track] = f"{type(exc).__name__}: {exc}"
        return []


def _upstream_to_openai_specs(track: str) -> list[dict]:
    specs: list[dict] = []
    reserved = SHARED_TOOLS | LOCAL_INVENTOR_TOOLS | LOCAL_AUTOCAD_TOOLS
    for tool in _load_upstream_tools(track):
        raw_name = (tool.get("name") or "").strip()
        if not raw_name:
            continue
        if track == "autocad":
            # Upstream has no product prefix — add autocad_ for track filtering
            name = (
                raw_name
                if raw_name.startswith("autocad_")
                else f"autocad_{raw_name}"
            )
        else:
            # ipt-mcp already uses inventor_*
            name = raw_name
            if not name.startswith("inventor_"):
                name = f"inventor_{raw_name}"
        if name in reserved:
            continue
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description") or name,
                    "parameters": _normalize_schema(tool.get("inputSchema")),
                },
            }
        )
    return specs


def tool_specs(
    track: str | None = None, *, base_modelling_kit: bool = False
) -> list[dict]:
    """OpenAI-style tools: shared + internet + full upstream MCP for the track."""
    specs = _shared_specs()
    if not track:
        # Unfiltered: both tracks' upstream (status / debug)
        specs.extend(_local_track_specs("inventor"))
        specs.extend(_local_track_specs("autocad"))
        specs.extend(_upstream_to_openai_specs("inventor"))
        specs.extend(_upstream_to_openai_specs("autocad"))
        if base_modelling_kit:
            allow = base_modelling_kit_allowlist(
                "inventor"
            ) | base_modelling_kit_allowlist("autocad")
            specs = [s for s in specs if s["function"]["name"] in allow]
        return specs

    track = track.lower().strip()
    if track not in {"inventor", "autocad"}:
        raise ValueError("track must be inventor or autocad")

    specs.extend(_local_track_specs(track))
    upstream = _upstream_to_openai_specs(track)
    if upstream:
        specs.extend(upstream)
    else:
        # MCP unavailable — keep small façade so the UI still works
        specs.extend(_fallback_facade_specs(track))

    if base_modelling_kit:
        allow = base_modelling_kit_allowlist(track)
        # Deduplicate by name (façade + upstream can overlap), keep first
        seen: set[str] = set()
        filtered: list[dict] = []
        for s in specs:
            name = s["function"]["name"]
            if name not in allow or name in seen:
                continue
            seen.add(name)
            filtered.append(s)
        return filtered
    return specs


def refresh_upstream_tools(track: str | None = None) -> dict[str, Any]:
    """Clear cache and re-list MCP tools (for /api/status diagnostics)."""
    tracks = [track] if track else ["inventor", "autocad"]
    out: dict[str, Any] = {}
    for t in tracks:
        _upstream_cache.pop(t, None)
        tools = _load_upstream_tools(t)
        out[t] = {
            "count": len(tools),
            "error": _upstream_error.get(t),
            "names": [x.get("name") for x in tools[:40]],
        }
    return out


def _health(_: dict) -> dict:
    return {
        "ok": True,
        "service": "test-ui",
        "inventor": _inventor.status(),
        "autocad": _autocad.status(),
        "upstream_tools": {
            "inventor": len(_load_upstream_tools("inventor")),
            "autocad": len(_load_upstream_tools("autocad")),
            "errors": dict(_upstream_error),
        },
    }


def _echo(args: dict) -> dict:
    return {"echo": args.get("message", "")}


def _request_track_switch(args: dict) -> dict:
    to_track = (args.get("to_track") or "").lower().strip()
    if to_track not in {"inventor", "autocad"}:
        return {"error": "to_track must be inventor or autocad"}
    reason = (args.get("reason") or "").strip() or f"Switch to {to_track} tools"
    label = "Inventor" if to_track == "inventor" else "AutoCAD"
    return {
        "needs_confirmation": True,
        "to_track": to_track,
        "reason": reason,
        "ui": "confirm_cancel",
        "prompt": f"Switch to {label} mode? {reason}",
    }


def _request_launch_cad(args: dict) -> dict:
    """UI-gated launch request — does not start the process (POST /api/cad/launch does)."""
    app = (args.get("app") or "").lower().strip()
    if app not in {"inventor", "autocad"}:
        return {"error": "app must be inventor or autocad"}
    reason = (args.get("reason") or "").strip() or f"Start {app}"
    status = launch_status(app)
    label = status["label"]
    drawing_path = args.get("drawing_path") or args.get("path")

    if status["running"]:
        return {
            "needs_confirmation": False,
            "ok": True,
            "already_running": True,
            "app": app,
            "reason": reason,
            "status": status,
            "message": (
                f"{label} is already running. Immediately continue with live "
                f"{app}_* CAD tools — do not ask the user to Confirm launch again."
            ),
            "instruction": (
                f"FOR THE ASSISTANT ONLY — {label} is already running. "
                f"Continue modeling with {app}_* tools now."
            ),
        }

    if not status["installed"]:
        return {
            "needs_confirmation": False,
            "ok": False,
            "app": app,
            "reason": reason,
            "status": status,
            "error": (
                f"{label} was not found in the allowlisted install paths. "
                f"Install it or set the approved path before launching."
            ),
        }

    payload: dict[str, Any] = {
        "needs_confirmation": True,
        "app": app,
        "reason": reason,
        "ui": "confirm_cancel",
        "prompt": f"Launch {label}? {reason}",
        "status": status,
        "instruction": (
            f"FOR THE ASSISTANT ONLY — wait for the user to Confirm or Cancel "
            f"launching {label}. Do not claim you started it."
        ),
    }
    if drawing_path and app == "autocad":
        payload["drawing_path"] = str(drawing_path).strip()
    return payload


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _web_search(args: dict) -> dict:
    import os
    from urllib.parse import parse_qs, unquote, urlparse as _urlparse

    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "query is required"}
    max_results = max(1, min(int(args.get("max_results") or 5), 10))
    results: list[dict[str, str]] = []
    sources: list[str] = []
    # Wikimedia requires an identifying UA + contact (generic bots get 403).
    wiki_headers = {
        "User-Agent": (
            "Autodesk-MCP-TestUI/1.0 "
            "(https://github.com/designconsultingaus; research tool for local CAD demo; "
            "contact: cameron@designconsulting.com.au)"
        ),
        "Accept": "application/json",
    }
    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json,*/*",
    }

    def _add(title: str, url: str, snippet: str = "") -> None:
        if not title or not url:
            return
        if any(x.get("url") == url for x in results):
            return
        results.append(
            {"title": title, "url": url, "snippet": (snippet or "").strip()}
        )

    # Optional: Brave Search API if BRAVE_API_KEY is set
    brave_key = (os.getenv("BRAVE_API_KEY") or "").strip()
    if brave_key and len(results) < max_results:
        try:
            with httpx.Client(timeout=20.0) as client:
                br = client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": max_results},
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": brave_key,
                    },
                )
                if br.is_success:
                    for item in (br.json().get("web") or {}).get("results") or []:
                        _add(
                            item.get("title") or "",
                            item.get("url") or "",
                            item.get("description") or "",
                        )
                        if len(results) >= max_results:
                            break
                    if results:
                        sources.append("brave")
        except Exception:
            pass

    # DuckDuckGo Instant Answer API (no key; Abstract + RelatedTopics)
    if len(results) < max_results:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                dr = client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                    headers=browser_headers,
                )
                if dr.is_success:
                    data = dr.json()
                    abs_text = (data.get("AbstractText") or "").strip()
                    abs_url = (data.get("AbstractURL") or "").strip()
                    heading = (data.get("Heading") or query).strip()
                    if abs_text and abs_url:
                        _add(heading, abs_url, abs_text)
                        sources.append("duckduckgo-api")
                    for topic in data.get("RelatedTopics") or []:
                        if len(results) >= max_results:
                            break
                        if "Topics" in topic:
                            for sub in topic.get("Topics") or []:
                                _add(
                                    (sub.get("Text") or "")[:80],
                                    sub.get("FirstURL") or "",
                                    sub.get("Text") or "",
                                )
                                if len(results) >= max_results:
                                    break
                            continue
                        _add(
                            (topic.get("Text") or "")[:80],
                            topic.get("FirstURL") or "",
                            topic.get("Text") or "",
                        )
        except Exception:
            pass

    # Wikipedia search + REST summary (identifying UA required)
    if len(results) < max_results:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                wr = client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": max_results,
                        "srprop": "snippet",
                        "format": "json",
                    },
                    headers=wiki_headers,
                )
                if wr.is_success:
                    hits = ((wr.json().get("query") or {}).get("search")) or []
                    for hit in hits:
                        title = hit.get("title") or ""
                        if not title:
                            continue
                        snippet = re.sub(r"<[^>]+>", "", hit.get("snippet") or "")
                        snippet = (
                            snippet.replace("&amp;", "&")
                            .replace("&quot;", '"')
                            .replace("&#039;", "'")
                        )
                        url = (
                            "https://en.wikipedia.org/wiki/"
                            + quote_plus(title.replace(" ", "_")).replace("+", "_")
                        )
                        # Prefer fuller extract when available
                        if not snippet or len(snippet) < 40:
                            try:
                                sr = client.get(
                                    "https://en.wikipedia.org/api/rest_v1/page/summary/"
                                    + quote_plus(title.replace(" ", "_")),
                                    headers=wiki_headers,
                                )
                                if sr.is_success:
                                    snippet = (
                                        (sr.json().get("extract") or snippet)[:400]
                                    )
                                    url = (
                                        (sr.json().get("content_urls") or {})
                                        .get("desktop", {})
                                        .get("page")
                                        or url
                                    )
                            except Exception:
                                pass
                        _add(title, url, snippet)
                        if len(results) >= max_results:
                            break
                    if hits:
                        sources.append("wikipedia")
        except Exception:
            pass

    # DuckDuckGo lite HTML fallback
    if len(results) < max_results:
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                r = client.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                    headers=browser_headers,
                )
                if r.is_success:
                    for m in re.finditer(
                        r' rel="nofollow" href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                        r.text,
                        re.I | re.S,
                    ):
                        href = m.group(1)
                        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                        if "duckduckgo.com" in href:
                            continue
                        _add(title, href, "")
                        if len(results) >= max_results:
                            break
                    if results and "duckduckgo-lite" not in sources:
                        sources.append("duckduckgo-lite")
        except Exception:
            pass

    # Classic DuckDuckGo HTML (last resort; often bot-blocked)
    if len(results) < max_results:
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                r = client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query},
                    headers=browser_headers,
                )
                if r.is_success and "result__a" in r.text:
                    blocks = re.split(r'class="result__body"', r.text, flags=re.I)
                    for block in blocks[1:]:
                        m = re.search(
                            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                            block,
                            re.I | re.S,
                        )
                        if not m:
                            continue
                        href = m.group(1)
                        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                        title = title.replace("&amp;", "&")
                        sn_m = re.search(
                            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
                            block,
                            re.I | re.S,
                        )
                        snippet = ""
                        if sn_m:
                            snippet = re.sub(r"<[^>]+>", "", sn_m.group(1)).strip()
                            snippet = snippet.replace("&amp;", "&")
                        if "uddg=" in href:
                            qs = parse_qs(
                                _urlparse("http://x?" + href.split("?", 1)[-1]).query
                            )
                            href = unquote((qs.get("uddg") or [href])[0])
                        if not href.startswith("http") or "duckduckgo.com" in href:
                            continue
                        _add(title, href, snippet)
                        if len(results) >= max_results:
                            break
                    if results and "duckduckgo" not in sources:
                        sources.append("duckduckgo")
        except Exception:
            pass

    if not results:
        return {
            "error": (
                "No search hits returned (search providers blocked or empty). "
                "Try web_fetch with a known URL, or set BRAVE_API_KEY for Brave Search."
            ),
            "query": query,
            "search_url": f"https://duckduckgo.com/?q={quote_plus(query)}",
        }

    return {
        "query": query,
        "results": results[:max_results],
        "source": "+".join(dict.fromkeys(sources)) or "mixed",
        "search_url": f"https://duckduckgo.com/?q={quote_plus(query)}",
    }


def _web_fetch(args: dict) -> dict:
    url = (args.get("url") or "").strip()
    if not url:
        return {"error": "url is required"}
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"error": "only http/https URLs are allowed"}
    max_chars = max(1000, min(int(args.get("max_chars") or 12000), 50000))
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            r = client.get(
                url,
                headers={"User-Agent": "Autodesk-MCP-TestUI/1.0"},
            )
            ctype = (r.headers.get("content-type") or "").lower()
            body = r.text
            if "html" in ctype or body.lstrip().startswith("<"):
                text = _strip_html(body)
            else:
                text = body
            truncated = len(text) > max_chars
            return {
                "ok": r.is_success,
                "status_code": r.status_code,
                "url": str(r.url),
                "content_type": ctype,
                "truncated": truncated,
                "text": text[:max_chars],
            }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"web_fetch failed: {type(exc).__name__}: {exc}", "url": url}


def _is_autocad_com_fail_text(text: str) -> bool:
    lower = (text or "").lower()
    return any(k in lower for k in _COM_FAIL_MARKERS)


def _is_autocad_com_fail_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    blob = json.dumps(result, ensure_ascii=False).lower()
    if _is_autocad_com_fail_text(blob):
        return True
    # ok:true but every layer create failed via COM
    layers = result.get("layers")
    if isinstance(layers, dict) and layers:
        vals = list(layers.values())
        if all(isinstance(v, str) and "failed" in v.lower() for v in vals):
            return True
    return False


def _is_inventor_target_fail_text(text: str) -> bool:
    lower = (text or "").lower()
    return any(k in lower for k in _TARGET_FAIL_MARKERS)


def _is_inventor_target_fail_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    err = result.get("error")
    if isinstance(err, dict) and str(err.get("code") or "").upper() == "NO_TARGET":
        return True
    if result.get("ok") is False or err:
        blob = json.dumps(result, ensure_ascii=False).lower()
        return _is_inventor_target_fail_text(blob)
    return False


def ensure_autocad_ready(
    *,
    wait_s: float = 90.0,
    force_reset: bool = False,
    drawing_path: str | None = None,
    force_restart: bool = False,
) -> dict[str, Any]:
    """
    Start AutoCAD if needed, open a drawing, reset the MCP COM session when needed.

    If drawing_path is set, open that existing .dwg/.dxf; otherwise a blank drawing.
    Restarts the MCP stdio server only if AutoCAD was started, a drawing was
    created/opened, or force_reset=True (after COM/RPC failure).
    force_restart quits a zombie acad.exe first when COM/RPC is dead — callers
    should escalate to this only after a soft (MCP-only) recover fails.
    """
    was_running = False
    try:
        was_running = bool(is_running("autocad"))
    except Exception:  # noqa: BLE001
        was_running = False
    ready = start_app(
        "autocad",
        wait_s=wait_s,
        drawing_path=drawing_path,
        force_restart=force_restart,
    )
    if ready.get("ok"):
        need_reset = bool(
            force_reset
            or force_restart
            or ready.get("started")
            or ready.get("force_restarted")
            or ready.get("created_drawing")
            or ready.get("opened_existing")
            or not was_running
        )
        if need_reset:
            try:
                _autocad.reset_connection()
            except Exception:  # noqa: BLE001
                _autocad._started_drawing = False
            else:
                # Existing file already open — don't let the next tool auto drawing_new.
                if ready.get("opened_existing") or drawing_path:
                    _autocad._started_drawing = True
        # Drawing already open and we kept the MCP process — still mark bootstrap
        # so the next tool does not call drawing_new and open Drawing2.
        if ready.get("drawing") and not getattr(_autocad, "_started_drawing", False):
            _autocad._started_drawing = True
        ready = {**ready, "mcp_reset": need_reset}
    return ready


def ensure_inventor_ready(
    *,
    wait_s: float = 90.0,
    force_reset: bool = False,
    force_restart: bool = False,
) -> dict[str, Any]:
    """
    Start Inventor if needed, wait for the Bimwright add-in target, open a part,
    and reset the MCP stdio session when needed.
    """
    was_running = False
    try:
        was_running = bool(is_running("inventor"))
    except Exception:  # noqa: BLE001
        was_running = False
    ready = start_app(
        "inventor",
        wait_s=wait_s,
        force_restart=force_restart,
    )
    if not ready.get("ok"):
        return ready

    need_reset = bool(
        force_reset
        or force_restart
        or ready.get("started")
        or ready.get("force_restarted")
        or not was_running
    )
    if need_reset:
        try:
            reset = getattr(_inventor, "reset_connection", None)
            if callable(reset):
                reset()
            else:
                setattr(_inventor, "_started_part", False)
        except Exception:  # noqa: BLE001
            setattr(_inventor, "_started_part", False)

    # Poll for add-in target + open/create a part.
    deadline = time.monotonic() + max(20.0, float(wait_s) * 0.7)
    last_err: str | None = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            ensure = getattr(_inventor, "_ensure_part", None)
            if callable(ensure):
                ensure(force=True)
            else:
                _inventor.call_upstream_tool("inventor_new_part", {})
                setattr(_inventor, "_started_part", True)
            return {
                **ready,
                "ok": True,
                "mcp_reset": need_reset,
                "part": True,
                "created_part": True,
                "target_wait_attempts": attempt,
                "message": (
                    str(ready.get("message") or "Inventor started.")
                    + " Live add-in target ready; part open."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            if not _is_inventor_target_fail_text(last_err):
                break
            time.sleep(2.0 + min(attempt, 6) * 0.5)

    return {
        **ready,
        "ok": False,
        "mcp_reset": need_reset,
        "error": last_err
        or (
            "Inventor.exe is running but no live Bimwright add-in target appeared. "
            "This is often a stuck background Inventor with no window. "
            "Quit/restart Inventor, and ensure Tools → Add-Ins → "
            "'Bimwright Inventor MCP' is loaded (Load Automatically)."
        ),
        "hint": (
            "Inventor.exe can be running with no visible UI and still block a "
            "fresh launch. Soft recover resets MCP; force_restart asks the user "
            "to Confirm quitting Inventor.exe."
        ),
        "target_wait_attempts": attempt,
    }


def request_force_restart_autocad(
    *,
    reason: str,
    drawing_path: str | None = None,
    soft_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask the user (Confirm/Cancel) before quitting AutoCAD. Never kills here."""
    why = (reason or "").strip()
    if not why:
        return {
            "ok": False,
            "error": (
                "force_restart requires a non-empty reason explaining why AutoCAD "
                "must be quit."
            ),
            "retry": True,
            "audience": "assistant_only",
            "instruction": (
                "FOR THE ASSISTANT ONLY — call recover_autocad again with "
                'force_restart=true and a short reason string. Do not kill apps yourself.'
            ),
        }
    running = False
    try:
        running = bool(is_running("autocad"))
    except Exception:  # noqa: BLE001
        running = False
    prompt = (
        f"Quit and restart **AutoCAD**?\n\n"
        f"**Reason:** {why}\n\n"
        "This will close the AutoCAD process (unsaved work may be lost), then reopen it."
    )
    return {
        "ok": False,
        "needs_confirmation": True,
        "ui": "confirm_cancel",
        "action": "force_restart",
        "app": "autocad",
        "reason": why,
        "prompt": prompt,
        "drawing_path": drawing_path,
        "soft_attempt": soft_attempt,
        "status": {"running": running, "installed": True},
        "retry": False,
        "instruction": (
            "FOR THE ASSISTANT ONLY — AutoCAD quit/restart is waiting on user "
            "Confirm or Cancel. Do not claim AutoCAD was restarted. Do not retry "
            "kill loops. Wait for the UI confirmation result."
        ),
    }


def _soft_then_hard_recover(
    *,
    drawing_path: str | None = None,
    wait_s: float = 90.0,
    reason: str | None = None,
) -> dict[str, Any]:
    """Soft MCP recover only. Cold-start asks Confirm; zombie process asks kill Confirm."""
    running = False
    try:
        running = bool(is_running("autocad"))
    except Exception:  # noqa: BLE001
        running = False

    # App down — never silent-start; UI Confirm via the same launch card.
    if not running:
        return _request_launch_cad(
            {
                "app": "autocad",
                "reason": (reason or "").strip()
                or "AutoCAD is not running — needed to recover the CAD session",
                **(
                    {"drawing_path": drawing_path}
                    if drawing_path
                    else {}
                ),
            }
        )

    soft = ensure_autocad_ready(
        force_reset=True,
        force_restart=False,
        drawing_path=drawing_path,
        wait_s=wait_s,
    )
    if soft.get("ok"):
        return {**soft, "recovery": "soft"}

    why = (reason or "").strip() or (
        "Soft recover failed — AutoCAD is running but COM/RPC is not responding "
        f"({soft.get('error') or 'unknown COM error'})."
    )
    return request_force_restart_autocad(
        reason=why,
        drawing_path=drawing_path,
        soft_attempt=soft,
    )


def force_restart_autocad_confirmed(
    *,
    drawing_path: str | None = None,
    wait_s: float = 90.0,
    reason: str | None = None,
) -> dict[str, Any]:
    """Perform taskkill + relaunch only after UI Confirm (API gate)."""
    why = (reason or "").strip() or "User confirmed AutoCAD quit/restart."
    ready = ensure_autocad_ready(
        force_reset=True,
        force_restart=True,
        drawing_path=drawing_path,
        wait_s=wait_s,
    )
    if ready.get("ok") and not ready.get("opened_existing"):
        try:
            _autocad._started_drawing = False
            _autocad.call_upstream_tool("drawing_new", {"bootstrap": True})
            _autocad._started_drawing = True
        except Exception as exc:  # noqa: BLE001
            return {
                **ready,
                "ok": True,
                "recovery": "hard",
                "confirmed_reason": why,
                "drawing_new_warning": str(exc),
            }
    elif ready.get("ok") and ready.get("drawing"):
        _autocad._started_drawing = True
    return {
        **ready,
        "recovery": "hard" if ready.get("ok") else "hard_failed",
        "confirmed_reason": why,
    }


def recover_autocad(args: dict | None = None) -> dict[str, Any]:
    """Explicit LLM-callable recovery: reset MCP session + ensure a drawing.

    Soft by default (does not quit AutoCAD). force_restart only requests user Confirm.
    """
    args = args or {}
    path = args.get("drawing_path") or args.get("path")
    hard = bool(args.get("force_restart"))
    drawing_path = str(path) if path else None
    if hard:
        return request_force_restart_autocad(
            reason=str(args.get("reason") or ""),
            drawing_path=drawing_path,
        )

    ready = _soft_then_hard_recover(drawing_path=drawing_path)
    if ready.get("needs_confirmation"):
        return ready
    if ready.get("ok"):
        if ready.get("drawing"):
            _autocad._started_drawing = True
        return {
            **ready,
            "ok": True,
            "recovered": True,
            "instruction": (
                "FOR THE ASSISTANT ONLY — AutoCAD session recovered with a drawing open. "
                "Recreate any solids/geometry from scratch, use real handles from those "
                "results for boolean, then finish the user request. Do not show this."
            ),
        }
    return {
        "ok": False,
        "error": ready.get("error") or "recover_autocad failed",
        "launch": ready,
        "retry": True,
        "audience": "assistant_only",
        "instruction": _RPC_RECOVERY_INSTRUCTION,
    }


def request_force_restart_inventor(
    *,
    reason: str,
    soft_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask the user (Confirm/Cancel) before quitting Inventor. Never kills here."""
    why = (reason or "").strip()
    if not why:
        return {
            "ok": False,
            "error": (
                "force_restart requires a non-empty reason explaining why Inventor "
                "must be quit."
            ),
            "retry": True,
            "audience": "assistant_only",
            "instruction": (
                "FOR THE ASSISTANT ONLY — call recover_inventor again with "
                'force_restart=true and a short reason string. Do not kill apps yourself.'
            ),
        }
    running = False
    try:
        running = bool(is_running("inventor"))
    except Exception:  # noqa: BLE001
        running = False
    prompt = (
        f"Quit and restart **Inventor**?\n\n"
        f"**Reason:** {why}\n\n"
        "This will close the Inventor process (unsaved work may be lost), then reopen it."
    )
    return {
        "ok": False,
        "needs_confirmation": True,
        "ui": "confirm_cancel",
        "action": "force_restart",
        "app": "inventor",
        "reason": why,
        "prompt": prompt,
        "soft_attempt": soft_attempt,
        "status": {"running": running, "installed": True},
        "retry": False,
        "instruction": (
            "FOR THE ASSISTANT ONLY — Inventor quit/restart is waiting on user "
            "Confirm or Cancel. Do not claim Inventor was restarted. Do not retry "
            "kill loops. Wait for the UI confirmation result."
        ),
    }


def _soft_then_hard_recover_inventor(
    *,
    wait_s: float = 90.0,
    reason: str | None = None,
) -> dict[str, Any]:
    """Soft MCP recover only. Cold-start asks Confirm; zombie process asks kill Confirm."""
    running = False
    try:
        running = bool(is_running("inventor"))
    except Exception:  # noqa: BLE001
        running = False

    # App down — never silent-start; UI Confirm via the same launch card.
    if not running:
        return _request_launch_cad(
            {
                "app": "inventor",
                "reason": (reason or "").strip()
                or "Inventor is not running — needed to recover the CAD session",
            }
        )

    soft = ensure_inventor_ready(
        force_reset=True,
        force_restart=False,
        wait_s=wait_s,
    )
    if soft.get("ok"):
        return {**soft, "recovery": "soft"}

    why = (reason or "").strip() or (
        "Soft recover failed — Inventor is running but no live add-in target "
        f"({soft.get('error') or 'NO_TARGET'})."
    )
    return request_force_restart_inventor(
        reason=why,
        soft_attempt=soft,
    )


def force_restart_inventor_confirmed(
    *,
    wait_s: float = 90.0,
    reason: str | None = None,
) -> dict[str, Any]:
    """Perform taskkill + relaunch only after UI Confirm (API gate)."""
    why = (reason or "").strip() or "User confirmed Inventor quit/restart."
    ready = ensure_inventor_ready(
        force_reset=True,
        force_restart=True,
        wait_s=wait_s,
    )
    if ready.get("ok") and not ready.get("part"):
        try:
            setattr(_inventor, "_started_part", False)
            _inventor.call_upstream_tool("inventor_new_part", {})
            setattr(_inventor, "_started_part", True)
            ready = {**ready, "part": True, "created_part": True}
        except Exception as exc:  # noqa: BLE001
            return {
                **ready,
                "ok": True,
                "recovery": "hard",
                "confirmed_reason": why,
                "new_part_warning": str(exc),
            }
    elif ready.get("ok"):
        setattr(_inventor, "_started_part", True)
    return {
        **ready,
        "recovery": "hard" if ready.get("ok") else "hard_failed",
        "confirmed_reason": why,
    }


def recover_inventor(args: dict | None = None) -> dict[str, Any]:
    """Explicit LLM-callable recovery: reset MCP session + ensure target/part.

    Soft by default (does not quit Inventor). force_restart only requests user Confirm.
    """
    args = args or {}
    hard = bool(args.get("force_restart"))
    if hard:
        return request_force_restart_inventor(
            reason=str(args.get("reason") or ""),
        )

    ready = _soft_then_hard_recover_inventor()
    if ready.get("needs_confirmation"):
        return ready
    if ready.get("ok"):
        setattr(_inventor, "_started_part", True)
        return {
            **ready,
            "ok": True,
            "recovered": True,
            "instruction": (
                "FOR THE ASSISTANT ONLY — Inventor session recovered with a part open. "
                "Recreate sketches/features from scratch, then finish the user request. "
                "Do not show this."
            ),
        }
    return {
        "ok": False,
        "error": ready.get("error") or "recover_inventor failed",
        "launch": ready,
        "retry": True,
        "audience": "assistant_only",
        "instruction": _TARGET_RECOVERY_INSTRUCTION,
    }


def _call_inventor_upstream(name: str, args: dict) -> Any:
    try:
        result = _inventor.call_upstream_tool(name, args)
    except Exception as exc:  # noqa: BLE001
        if not _is_inventor_target_fail_text(str(exc)):
            raise
        ready = _soft_then_hard_recover_inventor(
            reason=f"Tool {name} hit NO_TARGET/add-in error: {exc}"
        )
        if ready.get("needs_confirmation"):
            return {
                **ready,
                "host_recovery_attempted": True,
                "prior_error": str(exc),
            }
        if not ready.get("ok"):
            raise RuntimeError(
                f"Inventor could not be prepared ({ready.get('error')}). "
                f"Original error: {exc}"
            ) from exc
        try:
            result = _inventor.call_upstream_tool(name, args)
        except Exception as exc2:  # noqa: BLE001
            payload = _tool_error_payload(name, exc2)
            payload["host_recovery_attempted"] = True
            payload["launch"] = ready
            payload["retry"] = True
            payload["instruction"] = _TARGET_RECOVERY_INSTRUCTION
            return payload
        if isinstance(result, dict):
            result = {**result, "host_recovered": True, "launch": ready}
        return result

    if _is_inventor_target_fail_result(result):
        ready = _soft_then_hard_recover_inventor(
            reason=(
                f"Tool {name} returned NO_TARGET after soft checks "
                f"({result.get('error') or 'NO_TARGET'})."
            )
        )
        if ready.get("needs_confirmation"):
            return {
                **ready,
                "host_recovery_attempted": True,
                "prior": result,
            }
        if not ready.get("ok"):
            return {
                "ok": False,
                "error": ready.get("error")
                or "Inventor could not be started with a live target and part open.",
                "prior": result,
                "retry": True,
                "audience": "assistant_only",
                "instruction": _TARGET_RECOVERY_INSTRUCTION,
                "host_recovery_attempted": True,
            }
        try:
            result = _inventor.call_upstream_tool(name, args)
        except Exception as exc2:  # noqa: BLE001
            payload = _tool_error_payload(name, exc2)
            payload["host_recovery_attempted"] = True
            payload["launch"] = ready
            payload["retry"] = True
            payload["instruction"] = _TARGET_RECOVERY_INSTRUCTION
            return payload
        if isinstance(result, dict):
            result = {**result, "host_recovered": True, "launch": ready}
    return result


def _call_autocad_upstream(llm_name: str, args: dict) -> Any:
    upstream = llm_name[8:] if llm_name.startswith("autocad_") else llm_name
    try:
        result = _autocad.call_upstream_tool(upstream, args)
    except Exception as exc:  # noqa: BLE001
        if not _is_autocad_com_fail_text(str(exc)):
            raise
        # Soft MCP reset first — never taskkill without user Confirm.
        ready = _soft_then_hard_recover(
            reason=f"Tool {llm_name} hit COM/RPC error: {exc}"
        )
        if ready.get("needs_confirmation"):
            return {
                **ready,
                "host_recovery_attempted": True,
                "prior_error": str(exc),
            }
        if not ready.get("ok"):
            raise RuntimeError(
                f"AutoCAD could not be prepared ({ready.get('error')}). "
                f"Original error: {exc}"
            ) from exc
        try:
            result = _autocad.call_upstream_tool(upstream, args)
        except Exception as exc2:  # noqa: BLE001
            # Surface a recoverable payload instead of a bare exception
            payload = _tool_error_payload(llm_name, exc2)
            payload["host_recovery_attempted"] = True
            payload["launch"] = ready
            payload["retry"] = True
            payload["instruction"] = _RPC_RECOVERY_INSTRUCTION
            return payload
        if isinstance(result, dict):
            result = {**result, "host_recovered": True, "launch": ready}
        return result

    if _is_autocad_com_fail_result(result):
        ready = _soft_then_hard_recover(
            reason=(
                f"Tool {llm_name} returned COM/RPC failure after soft checks "
                f"({result.get('error') or 'COM error'})."
            )
        )
        if ready.get("needs_confirmation"):
            return {
                **ready,
                "host_recovery_attempted": True,
                "prior": result,
            }
        if not ready.get("ok"):
            return {
                "ok": False,
                "error": ready.get("error")
                or "AutoCAD could not be started with a drawing open.",
                "prior": result,
                "retry": True,
                "audience": "assistant_only",
                "instruction": _RPC_RECOVERY_INSTRUCTION,
                "host_recovery_attempted": True,
            }
        try:
            result = _autocad.call_upstream_tool(upstream, args)
        except Exception as exc2:  # noqa: BLE001
            payload = _tool_error_payload(llm_name, exc2)
            payload["host_recovery_attempted"] = True
            payload["launch"] = ready
            payload["retry"] = True
            payload["instruction"] = _RPC_RECOVERY_INSTRUCTION
            return payload
        if isinstance(result, dict):
            result = {**result, "host_recovered": True, "launch": ready}
    return result


def build_dispatch(
    rag_search: Callable[[str, int], list],
    rag: Any = None,
) -> dict[str, Callable[[dict], Any]]:
    def knowledge_search(args: dict) -> dict:
        query = args["query"]
        top_k = int(args.get("top_k") or 4)
        hits = rag_search(query, top_k)
        return {
            "hits": [
                {"source": h.source, "text": h.text, "score": h.score} for h in hits
            ]
        }

    def inventor_export(_: dict) -> dict:
        if rag is None:
            return {"error": "RAG backend not wired"}
        return export_inventor_to_rag(_inventor, rag)

    def autocad_export(_: dict) -> dict:
        if rag is None:
            return {"error": "RAG backend not wired"}
        return export_autocad_to_rag(_autocad, rag)

    dispatch: dict[str, Callable[[dict], Any]] = {
        "health": _health,
        "echo": _echo,
        "knowledge_search": knowledge_search,
        "web_search": _web_search,
        "web_fetch": _web_fetch,
        "request_track_switch": _request_track_switch,
        "request_launch_cad": _request_launch_cad,
        "recover_autocad": recover_autocad,
        "recover_inventor": recover_inventor,
        "inventor_status": lambda _: _inventor.status(),
        "inventor_export_to_rag": inventor_export,
        "autocad_status": lambda _: _autocad.status(),
        "autocad_export_to_rag": autocad_export,
        # Façade fallbacks (also used by demo mode)
        "inventor_create_part": lambda a: _inventor.create_part(a["name"]),
        "inventor_set_parameter": lambda a: _inventor.set_parameter(
            a["name"], a["expression"]
        ),
        "autocad_create_rectangle": lambda a: _autocad.create_rectangle(
            a["width"], a["height"], a.get("layer") or "0"
        ),
        "autocad_list_layers": lambda _: _autocad.list_layers(),
        "autocad_solid_box": lambda a: _autocad.solid_box(
            a["cx"], a["cy"], a["cz"], a["length"], a["width"], a["height"]
        ),
        "autocad_solid_cylinder": lambda a: _autocad.solid_cylinder(
            a["cx"], a["cy"], a["cz"], a["radius"], a["height"]
        ),
        "autocad_solid_boolean": lambda a: _autocad.solid_boolean(
            a["target_handle"], a["tool_handle"], a["operation"]
        ),
        "autocad_solid_extrude": lambda a: _autocad.solid_extrude(
            a["profile_handle"], a["height"], float(a.get("taper_angle") or 0)
        ),
    }

    # Full upstream MCP surface — overwrites façades with the same LLM name
    local_only = SHARED_TOOLS | LOCAL_INVENTOR_TOOLS | LOCAL_AUTOCAD_TOOLS

    def _make_inv(u: str) -> Callable[[dict], Any]:
        return lambda a, _u=u: _call_inventor_upstream(_u, a)

    def _make_acad(llm_n: str) -> Callable[[dict], Any]:
        return lambda a, _n=llm_n: _call_autocad_upstream(_n, a)

    for tool in _load_upstream_tools("inventor"):
        raw = (tool.get("name") or "").strip()
        if not raw:
            continue
        upstream_name = raw if raw.startswith("inventor_") else f"inventor_{raw}"
        name = upstream_name
        if name in local_only:
            continue
        dispatch[name] = _make_inv(upstream_name)

    for tool in _load_upstream_tools("autocad"):
        raw = (tool.get("name") or "").strip()
        if not raw:
            continue
        name = raw if raw.startswith("autocad_") else f"autocad_{raw}"
        if name in local_only:
            continue
        dispatch[name] = _make_acad(name)

    return dispatch


def _tool_error_payload(name: str, exc: BaseException) -> dict[str, Any]:
    """Shape tool failures so the model retries — not dump them to the user."""
    msg = str(exc)
    lower = msg.lower()
    com_rpc = _is_autocad_com_fail_text(msg) or name.startswith("autocad_") and any(
        k in lower for k in ("rpc", "com error", "no drawing", "stdio")
    )
    no_target = _is_inventor_target_fail_text(msg) or (
        name.startswith("inventor_")
        and any(k in lower for k in ("no_target", "no target", "no live inventor", "stdio"))
    )
    bad_handles = (
        "solid_boolean" in (name or "")
        and (
            "target_handle" in lower
            or "tool_handle" in lower
            or "null" in lower
            or "none" in lower
        )
        and ("validation" in lower or "string_type" in lower or "valid string" in lower)
    )
    retryable = com_rpc or no_target or bad_handles or any(
        k in lower
        for k in (
            "validation error",
            "unexpected keyword",
            "missing",
            "required",
            "invalid",
            "field required",
            "extra inputs are not permitted",
            "type_error",
        )
    )
    payload: dict[str, Any] = {
        "ok": False,
        "error": msg,
        "error_type": type(exc).__name__,
        "tool": name,
        "retry": bool(retryable),
        "audience": "assistant_only",
    }
    if com_rpc:
        payload["retry"] = True
        payload["instruction"] = _RPC_RECOVERY_INSTRUCTION
    elif no_target:
        payload["retry"] = True
        payload["instruction"] = _TARGET_RECOVERY_INSTRUCTION
    elif bad_handles:
        payload["retry"] = True
        payload["instruction"] = (
            "FOR THE ASSISTANT ONLY — do not show this to the user. "
            "autocad_solid_boolean needs real non-empty string handles from prior "
            "successful autocad_solid_box / autocad_solid_cylinder (or similar) results. "
            "If those creates failed (RPC/COM), call recover_autocad, recreate both solids, "
            "then boolean with the new handles. Never pass null or \"\"."
        )
    elif retryable:
        payload["instruction"] = (
            "FOR THE ASSISTANT ONLY — do not show this to the user. "
            "Re-read this tool's parameter schema, remove invalid kwargs, fix types, "
            "and call the tool again. Do not paste pydantic/validation text or "
            "JSON-schema tutorials into the chat."
        )
    else:
        payload["instruction"] = (
            "FOR THE ASSISTANT ONLY — try once more with corrected arguments if the "
            "error looks fixable. If it is an AutoCAD COM/RPC/stdio error, call "
            "recover_autocad then recreate geometry. If it is an Inventor NO_TARGET/"
            "add-in error, call recover_inventor then recreate the part. Only if that "
            "still fails, tell the user in one short plain sentence. Do not paste "
            "stack traces."
        )
    return payload


def _annotate_autocad_result(name: str, result: Any) -> Any:
    """Force RPC/COM failures to carry retry + recover_autocad instructions."""
    if not isinstance(result, dict):
        return result
    # User Confirm/Cancel for quit/restart — do not rewrite into a retry loop.
    if result.get("needs_confirmation") and result.get("action") == "force_restart":
        return result
    if not (
        name.startswith("autocad_")
        or name in {"recover_autocad", "request_launch_cad", "ensure_autocad_ready"}
    ):
        return result
    blob = json.dumps(result, ensure_ascii=False)
    if not _is_autocad_com_fail_text(blob) and not _is_autocad_com_fail_result(result):
        return result
    out = dict(result)
    out["ok"] = False
    out["retry"] = True
    out["audience"] = "assistant_only"
    out["instruction"] = _RPC_RECOVERY_INSTRUCTION
    # Keep a short recover hint at the top-level for small models
    out["recover"] = {
        "call": "recover_autocad",
        "arguments": {},
        "then": "autocad_drawing_new (if needed) -> recreate solids -> retry",
    }
    return out


def _annotate_inventor_result(name: str, result: Any) -> Any:
    """Force NO_TARGET failures to carry retry + recover_inventor instructions."""
    if not isinstance(result, dict):
        return result
    if result.get("needs_confirmation") and result.get("action") == "force_restart":
        return result
    if not (
        name.startswith("inventor_")
        or name in {"recover_inventor", "request_launch_cad", "ensure_inventor_ready"}
    ):
        return result
    if not _is_inventor_target_fail_result(result) and not _is_inventor_target_fail_text(
        json.dumps(result, ensure_ascii=False)
    ):
        return result
    out = dict(result)
    out["ok"] = False
    out["retry"] = True
    out["audience"] = "assistant_only"
    out["instruction"] = _TARGET_RECOVERY_INSTRUCTION
    out["recover"] = {
        "call": "recover_inventor",
        "arguments": {},
        "then": "inventor_new_part (if needed) -> recreate features -> retry",
    }
    return out


def run_tool(dispatch: dict[str, Callable[[dict], Any]], name: str, arguments: str | dict) -> str:
    """Run a tool and always return JSON — exceptions become error payloads for the LLM."""
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments or {}

    fn = dispatch.get(name)
    if not fn:
        # Late-bind upstream tools discovered after dispatch was built
        if name.startswith("inventor_"):
            try:
                result = _call_inventor_upstream(name, args)
                return json.dumps(
                    _annotate_inventor_result(name, result), ensure_ascii=False
                )
            except Exception as exc:  # noqa: BLE001
                return json.dumps(_tool_error_payload(name, exc), ensure_ascii=False)
        if name.startswith("autocad_"):
            try:
                result = _call_autocad_upstream(name, args)
                return json.dumps(
                    _annotate_autocad_result(name, result), ensure_ascii=False
                )
            except Exception as exc:  # noqa: BLE001
                return json.dumps(_tool_error_payload(name, exc), ensure_ascii=False)
        return json.dumps(
            {
                "ok": False,
                "error": f"unknown tool {name}",
                "retry": False,
                "audience": "assistant_only",
            }
        )

    try:
        result = fn(args)
        # Façade paths that skip _call_autocad_upstream still get one recovery.
        if (
            name.startswith("autocad_")
            and name not in ("autocad_status",)
            and _is_autocad_com_fail_result(result)
            and not (isinstance(result, dict) and result.get("host_recovered"))
        ):
            ready = _soft_then_hard_recover(
                reason=f"Tool {name} returned COM/RPC failure."
            )
            if ready.get("needs_confirmation"):
                result = {**ready, "host_recovery_attempted": True, "prior": result}
            elif ready.get("ok"):
                result = fn(args)
                if isinstance(result, dict):
                    result = {**result, "host_recovered": True, "launch": ready}
            elif isinstance(result, dict):
                result = {
                    **result,
                    "ok": False,
                    "retry": True,
                    "audience": "assistant_only",
                    "instruction": _RPC_RECOVERY_INSTRUCTION,
                    "host_recovery_attempted": True,
                    "launch": ready,
                }
        if (
            name.startswith("inventor_")
            and name not in ("inventor_status",)
            and _is_inventor_target_fail_result(result)
            and not (isinstance(result, dict) and result.get("host_recovered"))
        ):
            ready = _soft_then_hard_recover_inventor(
                reason=f"Tool {name} returned NO_TARGET failure."
            )
            if ready.get("needs_confirmation"):
                result = {**ready, "host_recovery_attempted": True, "prior": result}
            elif ready.get("ok"):
                result = fn(args)
                if isinstance(result, dict):
                    result = {**result, "host_recovered": True, "launch": ready}
            elif isinstance(result, dict):
                result = {
                    **result,
                    "ok": False,
                    "retry": True,
                    "audience": "assistant_only",
                    "instruction": _TARGET_RECOVERY_INSTRUCTION,
                    "host_recovery_attempted": True,
                    "launch": ready,
                }
        # Upstream sometimes returns error dicts without raising
        if isinstance(result, dict) and result.get("error") and "retry" not in result:
            err_text = str(result.get("error"))
            if any(
                k in err_text.lower()
                for k in ("validation error", "unexpected keyword", "missing")
            ):
                result = {
                    **result,
                    "ok": False,
                    "retry": True,
                    "audience": "assistant_only",
                    "instruction": (
                        "FOR THE ASSISTANT ONLY — fix arguments from the tool schema "
                        "and call again. Do not paste this error to the user."
                    ),
                }
        result = _annotate_autocad_result(name, result)
        result = _annotate_inventor_result(name, result)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 — surface to LLM tool loop
        if name.startswith("autocad_") and _is_autocad_com_fail_text(str(exc)):
            ready = _soft_then_hard_recover(
                reason=f"Tool {name} raised COM/RPC error: {exc}"
            )
            if ready.get("needs_confirmation"):
                return json.dumps(
                    {**ready, "host_recovery_attempted": True, "prior_error": str(exc)},
                    ensure_ascii=False,
                )
            if ready.get("ok"):
                try:
                    result = fn(args)
                    if isinstance(result, dict):
                        result = {**result, "host_recovered": True, "launch": ready}
                    result = _annotate_autocad_result(name, result)
                    return json.dumps(result, ensure_ascii=False)
                except Exception as exc2:  # noqa: BLE001
                    payload = _tool_error_payload(name, exc2)
                    payload["host_recovery_attempted"] = True
                    payload["launch"] = ready
                    payload["retry"] = True
                    payload["instruction"] = _RPC_RECOVERY_INSTRUCTION
                    payload["recover"] = {
                        "call": "recover_autocad",
                        "arguments": {},
                        "then": "recreate solids -> retry",
                    }
                    return json.dumps(payload, ensure_ascii=False)
            payload = _tool_error_payload(name, exc)
            payload["host_recovery_attempted"] = True
            payload["launch"] = ready
            payload["retry"] = True
            payload["instruction"] = _RPC_RECOVERY_INSTRUCTION
            payload["recover"] = {
                "call": "recover_autocad",
                "arguments": {},
                "then": "recreate solids -> retry",
            }
            return json.dumps(payload, ensure_ascii=False)
        if name.startswith("inventor_") and _is_inventor_target_fail_text(str(exc)):
            ready = _soft_then_hard_recover_inventor(
                reason=f"Tool {name} raised NO_TARGET error: {exc}"
            )
            if ready.get("needs_confirmation"):
                return json.dumps(
                    {**ready, "host_recovery_attempted": True, "prior_error": str(exc)},
                    ensure_ascii=False,
                )
            if ready.get("ok"):
                try:
                    result = fn(args)
                    if isinstance(result, dict):
                        result = {**result, "host_recovered": True, "launch": ready}
                    result = _annotate_inventor_result(name, result)
                    return json.dumps(result, ensure_ascii=False)
                except Exception as exc2:  # noqa: BLE001
                    payload = _tool_error_payload(name, exc2)
                    payload["host_recovery_attempted"] = True
                    payload["launch"] = ready
                    payload["retry"] = True
                    payload["instruction"] = _TARGET_RECOVERY_INSTRUCTION
                    payload["recover"] = {
                        "call": "recover_inventor",
                        "arguments": {},
                        "then": "recreate part -> retry",
                    }
                    return json.dumps(payload, ensure_ascii=False)
            payload = _tool_error_payload(name, exc)
            payload["host_recovery_attempted"] = True
            payload["launch"] = ready
            payload["retry"] = True
            payload["instruction"] = _TARGET_RECOVERY_INSTRUCTION
            payload["recover"] = {
                "call": "recover_inventor",
                "arguments": {},
                "then": "recreate part -> retry",
            }
            return json.dumps(payload, ensure_ascii=False)
        return json.dumps(_tool_error_payload(name, exc), ensure_ascii=False)


def track_status() -> dict[str, Any]:
    """Best-effort CAD status — never fail the UI status endpoint."""
    out: dict[str, Any] = {}
    try:
        out["inventor"] = _inventor.status()
    except Exception as exc:  # noqa: BLE001
        out["inventor"] = {"track": "inventor", "error": f"{type(exc).__name__}: {exc}"}
    try:
        out["autocad"] = _autocad.status()
    except Exception as exc:  # noqa: BLE001
        out["autocad"] = {"track": "autocad", "error": f"{type(exc).__name__}: {exc}"}
    out["upstream_tools"] = {
        "inventor_count": len(_load_upstream_tools("inventor")),
        "autocad_count": len(_load_upstream_tools("autocad")),
        "errors": dict(_upstream_error),
    }
    return out
