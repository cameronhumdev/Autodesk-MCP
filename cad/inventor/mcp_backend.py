"""Inventor backend that talks to bimwright/ipt-mcp over stdio."""

from __future__ import annotations

import shlex
import time
from typing import Any

from shared.stdio_client import McpStdioClient, McpStdioError


class McpInventorBackend:
    """Requires a built ipt-mcp server + Inventor add-in when calling live tools."""

    name = "inventor"
    mode = "mcp"

    # Tools that must not auto-create a part (lifecycle / status / already create one).
    _NO_AUTO_PART = frozenset(
        {
            "inventor_new_part",
            "inventor_open_document",
            "inventor_list_available_targets",
            "inventor_get_current_target",
            "inventor_switch_target",
            "inventor_health",
            "inventor_list_open_documents",
            "inventor_close_document",
        }
    )

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env or {}
        self._client = McpStdioClient(command, env=env, timeout_s=120.0)
        self._last_part: str | None = None
        self._parameters: dict[str, str] = {}
        self._started_part = False
        self._upstream_tools_cache: list[dict[str, Any]] | None = None

    def list_upstream_tools(self) -> list[dict[str, Any]]:
        """All tools advertised by ipt-mcp."""
        if self._upstream_tools_cache is None:
            self._upstream_tools_cache = self._client.list_tools()
        return list(self._upstream_tools_cache)

    def reset_connection(self) -> None:
        """Drop the MCP stdio process so the next call gets a fresh ipt-mcp session.

        After launching Inventor or recovering from NO_TARGET, the bridge may
        hold a stale empty-target view — restarting the server is the reliable fix.
        """
        self._started_part = False
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass
        self._client = McpStdioClient(
            self._command, env=self._env, timeout_s=120.0
        )

    @staticmethod
    def _needs_target_recovery(msg: str) -> bool:
        lower = (msg or "").lower()
        return any(
            k in lower
            for k in (
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
        )

    @staticmethod
    def _collection_nonempty(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, dict):
            err = value.get("error")
            if isinstance(err, dict) and str(err.get("code") or "").upper() == "NO_TARGET":
                return False
            if value.get("ok") is False:
                return False
            for key in ("targets", "documents", "items", "data", "result", "value"):
                nested = value.get(key)
                if isinstance(nested, list):
                    return len(nested) > 0
            # Single-target / document object without an error
            if err is None and value:
                return True
        return bool(value)

    def call_upstream_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call any upstream MCP tool by name (no façade).

        Most tools need a live add-in target + open document — auto-run
        inventor_new_part when the host has not yet bootstrapped one.

        Host may launch Inventor + open a part on NO_TARGET (see tools.py).
        """
        args = arguments or {}
        if name not in self._NO_AUTO_PART:
            self._ensure_part()
        try:
            result = self._client.call_tool(name, args)
        except McpStdioError as exc:
            if name not in self._NO_AUTO_PART and self._needs_target_recovery(str(exc)):
                self._started_part = False
                self._ensure_part(force=True)
                return self._client.call_tool(name, args)
            raise

        # ipt-mcp often returns {ok:false, error:{code:NO_TARGET}} without raising.
        if (
            name not in self._NO_AUTO_PART
            and isinstance(result, dict)
            and self._result_needs_recovery(result)
        ):
            self._started_part = False
            self._ensure_part(force=True)
            return self._client.call_tool(name, args)
        return result

    def _result_needs_recovery(self, result: dict[str, Any]) -> bool:
        if result.get("ok") is False or result.get("error"):
            blob = str(result.get("error") or result)
            return self._needs_target_recovery(blob)
        return False

    def _has_live_target(self) -> bool:
        try:
            targets = self._client.call_tool("inventor_list_available_targets", {})
        except McpStdioError:
            return False
        return self._collection_nonempty(targets)

    def _has_open_document(self) -> bool:
        try:
            docs = self._client.call_tool("inventor_list_open_documents", {})
        except McpStdioError:
            return False
        if self._collection_nonempty(docs):
            return True
        try:
            info = self._client.call_tool("inventor_get_document_info", {})
        except McpStdioError as exc:
            return not self._needs_target_recovery(str(exc))
        if isinstance(info, dict) and (info.get("ok") is False or info.get("error")):
            return not self._result_needs_recovery(info)
        return bool(info)

    def _ensure_part(self, force: bool = False) -> None:
        if self._started_part and not force:
            return

        # Prefer reusing an already-open document — new_part opens Part2+ and
        # looks like Inventor "restarting" when a document is already active.
        try:
            from shared.launch_cad import is_running

            if is_running("inventor") and self._has_live_target() and self._has_open_document():
                self._started_part = True
                return
        except Exception:  # noqa: BLE001 — fall through to new_part
            pass

        last_exc: McpStdioError | None = None
        # Fresh Inventor + add-in often needs a few seconds before targets appear.
        for attempt in range(8):
            try:
                if not self._has_live_target():
                    time.sleep(2.0 + attempt * 0.5)
                    continue
                if self._has_open_document():
                    self._started_part = True
                    return
                self._client.call_tool("inventor_new_part", {})
                self._started_part = True
                if not self._last_part:
                    self._last_part = "Part1"
                return
            except McpStdioError as exc:
                last_exc = exc
                msg = str(exc).lower()
                if "already" in msg and ("open" in msg or "document" in msg):
                    self._started_part = True
                    return
                if self._needs_target_recovery(msg):
                    time.sleep(2.0 + attempt * 0.5)
                    continue
                break

        self._started_part = False
        if last_exc is not None:
            raise last_exc
        raise McpStdioError(
            "No live Inventor target after waiting. Start Inventor with the "
            "Bimwright Inventor MCP add-in loaded (Tools → Add-Ins, Load Automatically)."
        )

    def status(self) -> dict[str, Any]:
        from shared.launch_cad import is_running

        try:
            targets = self._client.call_tool("inventor_list_available_targets", {})
            target = self._client.call_tool("inventor_get_current_target", {})
            health: Any = None
            try:
                health = self._client.call_tool("inventor_health", {})
            except McpStdioError as exc:
                health = {"error": str(exc)}
            return {
                "track": "inventor",
                "mode": self.mode,
                "upstream": "bimwright/ipt-mcp",
                "command": self._command,
                "process_running": is_running("inventor"),
                "targets": targets,
                "target": target,
                "health": health,
                "last_part": self._last_part,
                "part_bootstrapped": self._started_part,
                "hint": (
                    "Status never launches Inventor. When CAD tools need it, the host "
                    "starts Inventor, waits for the Bimwright add-in target, opens a new "
                    "part, then retries."
                ),
            }
        except McpStdioError as exc:
            return {
                "track": "inventor",
                "mode": self.mode,
                "upstream": "bimwright/ipt-mcp",
                "command": self._command,
                "process_running": is_running("inventor"),
                "error": str(exc),
                "hint": (
                    "If targets empty: open Inventor 2027 → Tools → Add-Ins → "
                    "enable 'Bimwright Inventor MCP (2027)' (Load Automatically)."
                ),
            }

    def create_part(self, name: str) -> dict[str, Any]:
        # ipt-mcp: inventor_new_part — optional template; name is our session label
        result = self.call_upstream_tool("inventor_new_part", {})
        self._last_part = name
        self._parameters = {}
        self._started_part = True
        # Best-effort: stamp part number / iProperty if available
        try:
            self._client.call_tool(
                "inventor_set_iproperty",
                {
                    "property_set": "Design Tracking Properties",
                    "name": "Part Number",
                    "value": name,
                },
            )
        except McpStdioError:
            pass
        return {
            "created": name,
            "active": name,
            "track": "inventor",
            "mode": self.mode,
            "upstream_result": result,
        }

    def set_parameter(self, name: str, expression: str) -> dict[str, Any]:
        try:
            result = self.call_upstream_tool(
                "inventor_set_parameter",
                {"name": name, "expression": expression},
            )
        except McpStdioError:
            # Parameter may not exist yet — create then set
            result = self.call_upstream_tool(
                "inventor_create_parameter",
                {"name": name, "expression": expression, "unit": "mm"},
            )
        self._parameters[name] = expression
        return {
            "part": self._last_part,
            "parameters": dict(self._parameters),
            "track": "inventor",
            "mode": self.mode,
            "upstream_result": result,
        }

    def export_summary(self) -> dict[str, Any]:
        info: Any = {}
        params: Any = {}
        mass: Any = {}
        try:
            info = self.call_upstream_tool("inventor_get_document_info", {})
        except McpStdioError as exc:
            info = {"error": str(exc)}
        try:
            params = self.call_upstream_tool("inventor_list_parameters", {})
        except McpStdioError as exc:
            params = {"error": str(exc)}
        try:
            mass = self.call_upstream_tool("inventor_get_mass_properties", {})
        except McpStdioError as exc:
            mass = {"error": str(exc)}

        label = self._last_part or "active"
        text = (
            f"Inventor part summary (live ipt-mcp).\n"
            f"Label: {label}\n"
            f"Document: {info}\n"
            f"Parameters: {params}\n"
            f"Mass properties: {mass}\n"
            f"Source track: inventor\n"
        )
        return {
            "track": "inventor",
            "mode": self.mode,
            "doc_id": f"inventor:part:{label}",
            "source": f"inventor/ipt-mcp/{label}",
            "text": text,
            "document": info,
            "parameters": params,
            "mass": mass,
        }


def parse_command(cmd: str) -> list[str]:
    """Parse INVENTOR_MCP_COMMAND (exe path or shell-like string)."""
    cmd = cmd.strip()
    if not cmd:
        raise ValueError("empty INVENTOR_MCP_COMMAND")
    return shlex.split(cmd, posix=False)
