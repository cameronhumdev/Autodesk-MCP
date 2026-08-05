from __future__ import annotations

from typing import Any


class MockAutocadBackend:
    """In-process AutoCAD stand-in (no Autodesk install required)."""

    name = "autocad"
    mode = "mock"

    def __init__(self) -> None:
        self._layers = ["0", "WALLS", "DOORS", "DIMS", "TEXT", "TITLE"]
        self._entities: list[dict[str, Any]] = []

    def list_upstream_tools(self) -> list[dict[str, Any]]:
        return []

    def call_upstream_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return {"error": f"mock backend has no upstream tool {name}"}

    def status(self) -> dict[str, Any]:
        return {
            "track": "autocad",
            "mode": self.mode,
            "upstream": None,
            "layers": list(self._layers),
            "entity_count": len(self._entities),
            "note": "mock only — not real AutoCAD",
        }

    def create_rectangle(
        self, width: float, height: float, layer: str = "0"
    ) -> dict[str, Any]:
        ent = {
            "type": "rectangle",
            "width": width,
            "height": height,
            "layer": layer or "0",
        }
        self._entities.append(ent)
        if ent["layer"] not in self._layers:
            self._layers.append(ent["layer"])
        return {
            "entity": ent,
            "count": len(self._entities),
            "track": "autocad",
            "mode": self.mode,
            "note": "mock only",
        }

    def list_layers(self) -> dict[str, Any]:
        return {
            "layers": list(self._layers),
            "track": "autocad",
            "mode": self.mode,
            "note": "mock only",
        }

    def export_summary(self) -> dict[str, Any]:
        if not self._entities:
            return {"error": "no AutoCAD entities to export", "track": "autocad"}
        lines = []
        for i, e in enumerate(self._entities, 1):
            lines.append(
                f"{i}. {e.get('type')} {e.get('width')}x{e.get('height')} on layer {e.get('layer')}"
            )
        text = (
            "AutoCAD drawing summary (mock).\n"
            f"Layers: {', '.join(self._layers)}\n"
            f"Entities ({len(self._entities)}):\n"
            + "\n".join(lines)
            + "\nSource track: autocad\n"
        )
        return {
            "track": "autocad",
            "mode": self.mode,
            "doc_id": "autocad:drawing:session",
            "source": "autocad/mock/session",
            "text": text,
            "layers": list(self._layers),
            "entity_count": len(self._entities),
        }

    def _mock_solid(self, kind: str, params: dict[str, Any]) -> dict[str, Any]:
        handle = f"MOCK{len(self._entities) + 1:04X}"
        ent = {"type": kind, **params, "handle": handle}
        self._entities.append(ent)
        return {
            "entity": ent,
            "handle": handle,
            "count": len(self._entities),
            "track": "autocad",
            "mode": self.mode,
            "note": "mock only — not real AutoCAD solids",
        }

    def solid_box(
        self,
        cx: float,
        cy: float,
        cz: float,
        length: float,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        return self._mock_solid(
            "solid_box",
            {
                "cx": cx,
                "cy": cy,
                "cz": cz,
                "length": length,
                "width": width,
                "height": height,
            },
        )

    def solid_cylinder(
        self, cx: float, cy: float, cz: float, radius: float, height: float
    ) -> dict[str, Any]:
        return self._mock_solid(
            "solid_cylinder",
            {"cx": cx, "cy": cy, "cz": cz, "radius": radius, "height": height},
        )

    def solid_boolean(
        self, target_handle: str, tool_handle: str, operation: str
    ) -> dict[str, Any]:
        return self._mock_solid(
            "solid_boolean",
            {
                "target_handle": target_handle,
                "tool_handle": tool_handle,
                "operation": operation,
            },
        )

    def solid_extrude(
        self, profile_handle: str, height: float, taper_angle: float = 0.0
    ) -> dict[str, Any]:
        return self._mock_solid(
            "solid_extrude",
            {
                "profile_handle": profile_handle,
                "height": height,
                "taper_angle": taper_angle,
            },
        )
