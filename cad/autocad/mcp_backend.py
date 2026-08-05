"""AutoCAD backend that talks to U-C4N/Autocad-MCP (autocad-mcp-pro) over stdio."""

from __future__ import annotations

import shlex
from typing import Any

from shared.stdio_client import McpStdioClient, McpStdioError


class McpAutocadBackend:
    """
    Live COM AutoCAD or headless ezdxf via upstream server.

    Typical:
      AUTOCAD_BACKEND=mcp
      AUTOCAD_MCP_COMMAND=autocad-mcp
      AUTOCAD_MCP_ENV: AUTOCAD_MCP_BACKEND=ezdxf   (no AutoCAD app needed)
    """

    name = "autocad"
    mode = "mcp"

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env or {}
        self._client = McpStdioClient(command, env=env, timeout_s=120.0)
        self._entities: list[dict[str, Any]] = []
        self._started_drawing = False
        self._upstream_tools_cache: list[dict[str, Any]] | None = None

    def list_upstream_tools(self) -> list[dict[str, Any]]:
        """All tools advertised by U-C4N (honours TOOL_PROFILE / ENABLE_3D)."""
        if self._upstream_tools_cache is None:
            self._upstream_tools_cache = self._client.list_tools()
        return list(self._upstream_tools_cache)

    def reset_connection(self) -> None:
        """Drop the MCP stdio process so the next call gets a fresh COM session.

        Upstream caches a dead AutoCAD.Application after RPC failures; restarting
        the server is the reliable fix after we launch/open a drawing ourselves.
        """
        self._started_drawing = False
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass
        self._client = McpStdioClient(
            self._command, env=self._env, timeout_s=120.0
        )

    # Tools that must not auto-create a drawing (lifecycle / status / already create one).
    _NO_AUTO_DRAWING = frozenset(
        {
            "drawing_new",
            "drawing_open",
            "drawing_close",
            "system_status",
            "system_about",
            "system_set_variable",
            "system_get_variable",
        }
    )

    @staticmethod
    def _needs_drawing_recovery(msg: str) -> bool:
        lower = (msg or "").lower()
        return any(
            k in lower
            for k in (
                ".count",
                "no drawing",
                "no document",
                "rpc server is unavailable",
                "0x800706ba",
                "-0x7ff8f946",
            )
        )

    def call_upstream_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call any upstream MCP tool by name (no façade).

        Most tools need an open document — auto-run drawing_new when the host
        has not yet bootstrapped one (user asked to create, no .dwg open yet).

        Host may launch AutoCAD + open a drawing on COM failure (see tools.py).
        """
        args = arguments or {}
        if name not in self._NO_AUTO_DRAWING:
            self._ensure_drawing()
        try:
            return self._client.call_tool(name, args)
        except McpStdioError as exc:
            # Stale session / start screen / COM not ready yet
            if name not in self._NO_AUTO_DRAWING and self._needs_drawing_recovery(str(exc)):
                self._started_drawing = False
                self._ensure_drawing(force=True)
                return self._client.call_tool(name, args)
            raise

    def _ensure_drawing(self, force: bool = False) -> None:
        if self._started_drawing and not force:
            return
        # Prefer reusing an already-open document — drawing_new opens Drawing2+
        # and looks like AutoCAD "restarting" when the host already attached.
        try:
            from shared.launch_cad import is_running

            if is_running("autocad"):
                import pythoncom  # type: ignore
                import win32com.client  # type: ignore

                pythoncom.CoInitialize()
                try:
                    app = win32com.client.GetActiveObject("AutoCAD.Application")
                    if int(app.Documents.Count) > 0:
                        self._started_drawing = True
                        return
                finally:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass
        except Exception:  # noqa: BLE001 — fall through to drawing_new
            pass

        last_exc: McpStdioError | None = None
        # Fresh AutoCAD often needs a few seconds before Documents.Add works.
        for attempt in range(6):
            try:
                self._client.call_tool("drawing_new", {"bootstrap": True})
                self._started_drawing = True
                return
            except McpStdioError as exc:
                last_exc = exc
                msg = str(exc).lower()
                # Already have a document — treat as success.
                if "already" in msg and "open" in msg:
                    self._started_drawing = True
                    return
                if self._needs_drawing_recovery(msg) or "cannot connect" in msg:
                    import time

                    time.sleep(2.0 + attempt)
                    continue
                # Unexpected error — do not pretend a drawing exists.
                break
        self._started_drawing = False
        if last_exc is not None:
            raise last_exc

    def status(self) -> dict[str, Any]:
        """Non-mutating status — never calls COM (Dispatch would auto-launch AutoCAD)."""
        from shared.launch_cad import is_running

        return {
            "track": "autocad",
            "mode": self.mode,
            "upstream": "U-C4N/Autocad-MCP",
            "command": self._command,
            "env_backend": self._env.get("AUTOCAD_MCP_BACKEND"),
            "process_running": is_running("autocad"),
            "entity_count": len(self._entities),
            "drawing_bootstrapped": self._started_drawing,
            "hint": (
                "Status never launches AutoCAD. When CAD tools need it, the host "
                "starts AutoCAD and opens a new drawing, then retries."
            ),
        }

    def create_rectangle(
        self, width: float, height: float, layer: str = "0"
    ) -> dict[str, Any]:
        self._ensure_drawing()
        layer = layer or "0"
        if layer and layer != "0":
            try:
                self._client.call_tool("layer_create", {"name": layer})
            except McpStdioError:
                pass
            try:
                self._client.call_tool("layer_set_current", {"name": layer})
            except McpStdioError:
                pass
        result = self._client.call_tool(
            "entity_create_rectangle",
            {"x1": 0.0, "y1": 0.0, "x2": float(width), "y2": float(height), "layer": layer},
        )
        ent = {
            "type": "rectangle",
            "width": width,
            "height": height,
            "layer": layer,
            "upstream": result,
        }
        self._entities.append(ent)
        return {
            "entity": {"type": "rectangle", "width": width, "height": height, "layer": layer},
            "count": len(self._entities),
            "track": "autocad",
            "mode": self.mode,
            "upstream_result": result,
        }

    def list_layers(self) -> dict[str, Any]:
        self._ensure_drawing()
        result = self._client.call_tool("layer_list", {})
        names: list[str] = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    names.append(str(item.get("name") or item.get("Name") or item))
                else:
                    names.append(str(item))
        elif isinstance(result, dict):
            names = [str(x) for x in (result.get("layers") or [])]
        return {
            "layers": names or result,
            "mode": self.mode,
            "track": "autocad",
            "upstream_result": result,
        }

    def _record_solid(self, kind: str, params: dict[str, Any], upstream: Any) -> dict[str, Any]:
        handle = None
        if isinstance(upstream, dict):
            handle = (
                upstream.get("handle")
                or upstream.get("Handle")
                or (upstream.get("entity") or {}).get("handle")
            )
        ent = {"type": kind, **params, "handle": handle, "upstream": upstream}
        self._entities.append(ent)
        return {
            "entity": {"type": kind, **params, "handle": handle},
            "handle": handle,
            "count": len(self._entities),
            "track": "autocad",
            "mode": self.mode,
            "upstream_result": upstream,
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
        """Native 3D solid box (requires ENABLE_3D + live AutoCAD COM)."""
        self._ensure_drawing()
        result = self._client.call_tool(
            "solid_box",
            {
                "cx": float(cx),
                "cy": float(cy),
                "cz": float(cz),
                "length": float(length),
                "width": float(width),
                "height": float(height),
            },
        )
        return self._record_solid(
            "solid_box",
            {
                "cx": cx,
                "cy": cy,
                "cz": cz,
                "length": length,
                "width": width,
                "height": height,
            },
            result,
        )

    def solid_cylinder(
        self,
        cx: float,
        cy: float,
        cz: float,
        radius: float,
        height: float,
    ) -> dict[str, Any]:
        self._ensure_drawing()
        result = self._client.call_tool(
            "solid_cylinder",
            {
                "cx": float(cx),
                "cy": float(cy),
                "cz": float(cz),
                "radius": float(radius),
                "height": float(height),
            },
        )
        return self._record_solid(
            "solid_cylinder",
            {"cx": cx, "cy": cy, "cz": cz, "radius": radius, "height": height},
            result,
        )

    def solid_boolean(
        self, target_handle: str, tool_handle: str, operation: str
    ) -> dict[str, Any]:
        self._ensure_drawing()
        op = (operation or "subtract").lower().strip()
        if op not in {"union", "subtract", "intersect"}:
            return {"error": "operation must be union, subtract, or intersect"}
        result = self._client.call_tool(
            "solid_boolean",
            {
                "target_handle": str(target_handle),
                "tool_handle": str(tool_handle),
                "operation": op,
            },
        )
        return self._record_solid(
            "solid_boolean",
            {
                "target_handle": target_handle,
                "tool_handle": tool_handle,
                "operation": op,
            },
            result,
        )

    def solid_extrude(
        self, profile_handle: str, height: float, taper_angle: float = 0.0
    ) -> dict[str, Any]:
        self._ensure_drawing()
        result = self._client.call_tool(
            "solid_extrude",
            {
                "profile_handle": str(profile_handle),
                "height": float(height),
                "taper_angle": float(taper_angle or 0.0),
            },
        )
        return self._record_solid(
            "solid_extrude",
            {
                "profile_handle": profile_handle,
                "height": height,
                "taper_angle": taper_angle,
            },
            result,
        )

    def export_summary(self) -> dict[str, Any]:
        self._ensure_drawing()
        layers = self.list_layers()
        entities: Any = {}
        try:
            entities = self._client.call_tool("entity_list", {"limit": 200})
        except McpStdioError as exc:
            entities = {"error": str(exc), "local_session": self._entities}

        text = (
            "AutoCAD drawing summary (live U-C4N MCP).\n"
            f"Layers: {layers.get('layers')}\n"
            f"Session entities recorded: {len(self._entities)}\n"
            f"Upstream entity_list: {entities}\n"
            "Source track: autocad\n"
        )
        return {
            "track": "autocad",
            "mode": self.mode,
            "doc_id": "autocad:drawing:session",
            "source": "autocad/uc4n/session",
            "text": text,
            "layers": layers.get("layers"),
            "entities": entities,
        }


def parse_command(cmd: str) -> list[str]:
    cmd = cmd.strip()
    if not cmd:
        raise ValueError("empty AUTOCAD_MCP_COMMAND")
    return shlex.split(cmd, posix=False)
