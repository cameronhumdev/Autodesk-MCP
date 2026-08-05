"""Local mode: point at MCP binaries relative to the install / repo root."""

from __future__ import annotations

import shutil
from pathlib import Path

from .paths import McpPaths

_TFMS = ("net10.0", "net9.0", "net8.0")


def _find_inventor_server(root: Path) -> Path | None:
    base = root / "vendor" / "ipt-mcp" / "src" / "server" / "bin" / "Release"
    for tfm in _TFMS:
        candidate = base / tfm / "Bimwright.Ipt.Server.exe"
        if candidate.is_file():
            return candidate
    for pattern in (
        "inventor/**/Bimwright.Ipt.Server.exe",
        "**/Bimwright.Ipt.Server.exe",
    ):
        hits = sorted(root.glob(pattern))
        if hits:
            return hits[0]
    return None


def _find_autocad_command(root: Path) -> str | None:
    venv_exe = root / ".venv" / "Scripts" / "autocad-mcp.exe"
    if venv_exe.is_file():
        return str(venv_exe)
    bundled = root / "autocad" / "autocad-mcp.exe"
    if bundled.is_file():
        return str(bundled)
    for name in ("autocad-mcp.exe", "autocad-mcp"):
        hit = next(root.glob(f"**/autocad/{name}"), None)
        if hit and hit.is_file():
            return str(hit)
    return shutil.which("autocad-mcp")


def resolve_local(install_root: Path, tracks: tuple[str, ...]) -> McpPaths:
    inventor = None
    autocad = None
    if "inventor" in tracks:
        found = _find_inventor_server(install_root)
        inventor = str(found) if found else None
    if "autocad" in tracks:
        autocad = _find_autocad_command(install_root)
    return McpPaths(
        inventor_command=inventor,
        autocad_command=autocad,
        source="local",
        root=str(install_root),
    )
