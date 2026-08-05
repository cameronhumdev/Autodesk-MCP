from __future__ import annotations

from typing import Any


class MockInventorBackend:
    """In-process Inventor stand-in (no Autodesk install required)."""

    name = "inventor"
    mode = "mock"

    def __init__(self) -> None:
        self._parts: dict[str, dict[str, Any]] = {}
        self._active: str | None = None

    def list_upstream_tools(self) -> list[dict[str, Any]]:
        return []

    def reset_connection(self) -> None:
        """No-op — mock has no stdio session."""

    def call_upstream_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return {"error": f"mock backend has no upstream tool {name}"}

    def status(self) -> dict[str, Any]:
        return {
            "track": "inventor",
            "mode": self.mode,
            "upstream": None,
            "active": self._active,
            "parts": list(self._parts.keys()),
            "note": "mock only — not real Inventor",
        }

    def create_part(self, name: str) -> dict[str, Any]:
        self._parts[name] = {"name": name, "parameters": {}}
        self._active = name
        return {
            "created": name,
            "active": name,
            "track": "inventor",
            "mode": self.mode,
            "note": "mock only — not real Inventor",
        }

    def set_parameter(self, name: str, expression: str) -> dict[str, Any]:
        if not self._active or self._active not in self._parts:
            return {"error": "no active Inventor part — create one first", "track": "inventor"}
        self._parts[self._active]["parameters"][name] = expression
        return {
            "part": self._active,
            "parameters": dict(self._parts[self._active]["parameters"]),
            "track": "inventor",
            "mode": self.mode,
            "note": "mock only",
        }

    def export_summary(self) -> dict[str, Any]:
        if not self._active or self._active not in self._parts:
            return {"error": "no active Inventor part to export", "track": "inventor"}
        part = self._parts[self._active]
        params = part.get("parameters") or {}
        param_lines = ", ".join(f"{k}={v}" for k, v in params.items()) or "(none)"
        text = (
            f"Inventor part summary (mock).\n"
            f"Part: {part['name']}\n"
            f"Parameters: {param_lines}\n"
            f"Source track: inventor\n"
        )
        return {
            "track": "inventor",
            "mode": self.mode,
            "doc_id": f"inventor:part:{part['name']}",
            "source": f"inventor/mock/{part['name']}",
            "text": text,
            "part": part["name"],
            "parameters": params,
        }
