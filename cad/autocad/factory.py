from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_AUTOCAD = REPO_ROOT / ".venv" / "Scripts" / "autocad-mcp.exe"


def default_autocad_command() -> str:
    env = os.getenv("AUTOCAD_MCP_COMMAND", "").strip()
    if env:
        return env
    if VENV_AUTOCAD.is_file():
        return str(VENV_AUTOCAD)
    which = shutil.which("autocad-mcp")
    if which:
        return which
    raise RuntimeError(
        "autocad-mcp not found. Run: pip install 'autocad-mcp-pro[com]' "
        "or set AUTOCAD_MCP_COMMAND."
    )


def get_autocad_backend() -> Any:
    """
    Real U-C4N AutoCAD MCP by default (COM when AutoCAD is available).

    AUTOCAD_BACKEND=mcp (default) | mock (dev escape hatch only)
    AUTOCAD_MCP_COMMAND=autocad-mcp
    AUTOCAD_MCP_BACKEND=com|ezdxf|auto  (default com on this Windows CAD box)
    """
    mode = os.getenv("AUTOCAD_BACKEND", "mcp").lower().strip() or "mcp"
    if mode == "mock":
        from autocad.mock_backend import MockAutocadBackend

        return MockAutocadBackend()
    if mode == "mcp":
        from autocad.mcp_backend import McpAutocadBackend, parse_command

        env: dict[str, str] = {}
        backend = os.getenv("AUTOCAD_MCP_BACKEND", "auto").strip() or "auto"
        env["AUTOCAD_MCP_BACKEND"] = backend
        # full + ENABLE_3D exposes solid_box / solid_cylinder / solid_boolean (COM only)
        profile = os.getenv("AUTOCAD_TOOL_PROFILE", "full").strip()
        if profile:
            env["TOOL_PROFILE"] = profile
        enable_3d = os.getenv("ENABLE_3D", "true").strip().lower() or "true"
        env["ENABLE_3D"] = enable_3d
        return McpAutocadBackend(parse_command(default_autocad_command()), env=env)
    raise ValueError(f"Unknown AUTOCAD_BACKEND={mode!r} (use mcp|mock)")
