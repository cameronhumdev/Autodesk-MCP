from __future__ import annotations

import os
from pathlib import Path
from typing import Any

CAD_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CAD_ROOT.parent
VENDOR_SERVER = (
    REPO_ROOT
    / "vendor"
    / "ipt-mcp"
    / "src"
    / "server"
    / "bin"
    / "Release"
    / "net10.0"
    / "Bimwright.Ipt.Server.exe"
)


def default_inventor_command() -> str:
    env = os.getenv("INVENTOR_MCP_COMMAND", "").strip()
    if env:
        return env
    if VENDOR_SERVER.is_file():
        return str(VENDOR_SERVER)
    raise RuntimeError(
        "Inventor MCP server not found. Build vendor/ipt-mcp "
        "(Bimwright.Ipt.Server.exe) or set INVENTOR_MCP_COMMAND."
    )


def get_inventor_backend() -> Any:
    """
    Real ipt-mcp by default.

    INVENTOR_BACKEND=mcp (default) | mock (dev escape hatch only)
    INVENTOR_MCP_COMMAND= path to Bimwright.Ipt.Server.exe
    """
    mode = os.getenv("INVENTOR_BACKEND", "mcp").lower().strip() or "mcp"
    if mode == "mock":
        from inventor.mock_backend import MockInventorBackend

        return MockInventorBackend()
    if mode == "mcp":
        from inventor.mcp_backend import McpInventorBackend, parse_command

        return McpInventorBackend(parse_command(default_inventor_command()))
    raise ValueError(f"Unknown INVENTOR_BACKEND={mode!r} (use mcp|mock)")
