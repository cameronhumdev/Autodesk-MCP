"""Inventor track contract — separate from AutoCAD."""

from __future__ import annotations

from typing import Any, Protocol


class InventorBackend(Protocol):
    """Stable façade used by test-ui / RAG. Upstream MCP is an implementation detail."""

    name: str
    mode: str  # mock | mcp

    def status(self) -> dict[str, Any]: ...

    def create_part(self, name: str) -> dict[str, Any]: ...

    def set_parameter(self, name: str, expression: str) -> dict[str, Any]: ...

    def export_summary(self) -> dict[str, Any]:
        """Return a text-friendly summary of the active/session state for RAG."""
...