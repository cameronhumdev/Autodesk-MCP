from __future__ import annotations

import json
from typing import Any, Callable

# In-memory mock CAD state for demos
_MOCK_INVENTOR: dict[str, Any] = {"parts": {}, "active": None}
_MOCK_AUTOCAD: dict[str, Any] = {
    "layers": ["0", "WALLS", "DOORS", "DIMS", "TEXT", "TITLE"],
    "entities": [],
}


def tool_specs() -> list[dict]:
    """OpenAI-style tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "health",
                "description": "Check whether the test stack API is healthy.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Echo a message back (sanity tool).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Text to echo"},
                    },
                    "required": ["message"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "knowledge_search",
                "description": "Search the local RAG / knowledge base for company standards and notes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "default": 4},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mock_inventor_create_part",
                "description": "MOCK: create an Inventor part (no real Autodesk). Stand-in for ipt-mcp.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mock_inventor_set_parameter",
                "description": "MOCK: set a parameter on the active mock Inventor part.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "expression": {"type": "string", "description": "e.g. 8 mm"},
                    },
                    "required": ["name", "expression"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mock_autocad_create_rectangle",
                "description": "MOCK: draw a rectangle in AutoCAD (no real Autodesk). Stand-in for U-C4N.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "layer": {"type": "string", "default": "0"},
                    },
                    "required": ["width", "height"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mock_autocad_list_layers",
                "description": "MOCK: list AutoCAD layers.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
    ]


def _health(_: dict) -> dict:
    return {"ok": True, "service": "test-ui"}


def _echo(args: dict) -> dict:
    return {"echo": args.get("message", "")}


def _mock_inventor_create_part(args: dict) -> dict:
    name = args["name"]
    _MOCK_INVENTOR["parts"][name] = {"name": name, "parameters": {}}
    _MOCK_INVENTOR["active"] = name
    return {"created": name, "active": name, "note": "mock only — not real Inventor"}


def _mock_inventor_set_parameter(args: dict) -> dict:
    active = _MOCK_INVENTOR.get("active")
    if not active or active not in _MOCK_INVENTOR["parts"]:
        return {"error": "no active mock part — create one first"}
    _MOCK_INVENTOR["parts"][active]["parameters"][args["name"]] = args["expression"]
    return {
        "part": active,
        "parameters": _MOCK_INVENTOR["parts"][active]["parameters"],
        "note": "mock only",
    }


def _mock_autocad_create_rectangle(args: dict) -> dict:
    ent = {
        "type": "rectangle",
        "width": args["width"],
        "height": args["height"],
        "layer": args.get("layer") or "0",
    }
    _MOCK_AUTOCAD["entities"].append(ent)
    layer = ent["layer"]
    if layer not in _MOCK_AUTOCAD["layers"]:
        _MOCK_AUTOCAD["layers"].append(layer)
    return {"entity": ent, "count": len(_MOCK_AUTOCAD["entities"]), "note": "mock only"}


def _mock_autocad_list_layers(_: dict) -> dict:
    return {"layers": list(_MOCK_AUTOCAD["layers"]), "note": "mock only"}


def build_dispatch(rag_search: Callable[[str, int], list]) -> dict[str, Callable[[dict], Any]]:
    def knowledge_search(args: dict) -> dict:
        query = args["query"]
        top_k = int(args.get("top_k") or 4)
        hits = rag_search(query, top_k)
        return {
            "hits": [
                {"source": h.source, "text": h.text, "score": h.score} for h in hits
            ]
        }

    return {
        "health": _health,
        "echo": _echo,
        "knowledge_search": knowledge_search,
        "mock_inventor_create_part": _mock_inventor_create_part,
        "mock_inventor_set_parameter": _mock_inventor_set_parameter,
        "mock_autocad_create_rectangle": _mock_autocad_create_rectangle,
        "mock_autocad_list_layers": _mock_autocad_list_layers,
    }


def run_tool(dispatch: dict[str, Callable[[dict], Any]], name: str, arguments: str | dict) -> str:
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments or {}
    fn = dispatch.get(name)
    if not fn:
        return json.dumps({"error": f"unknown tool {name}"})
    return json.dumps(fn(args), ensure_ascii=False)
