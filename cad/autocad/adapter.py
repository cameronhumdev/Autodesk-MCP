"""AutoCAD track contract — separate from Inventor."""

from __future__ import annotations

from typing import Any, Protocol


class AutocadBackend(Protocol):
    name: str
    mode: str  # mock | mcp

    def status(self) -> dict[str, Any]: ...

    def create_rectangle(
        self, width: float, height: float, layer: str = "0"
    ) -> dict[str, Any]: ...

    def list_layers(self) -> dict[str, Any]: ...

    def export_summary(self) -> dict[str, Any]: ...
