"""Resolved MCP command paths for Inventor / AutoCAD tracks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class McpPaths:
    inventor_command: str | None
    autocad_command: str | None
    source: str  # "local" | "download"
    root: str

    def as_env(self) -> dict[str, str]:
        env: dict[str, str] = {
            "CLIENT_MCP_SOURCE": self.source,
            "CLIENT_MCP_ROOT": self.root,
        }
        if self.inventor_command:
            env["INVENTOR_MCP_COMMAND"] = self.inventor_command
            env["INVENTOR_BACKEND"] = "mcp"
        if self.autocad_command:
            env["AUTOCAD_MCP_COMMAND"] = self.autocad_command
            env["AUTOCAD_BACKEND"] = "mcp"
        return env

    def write_runtime_env(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        env = self.as_env()
        # JSON for any consumer
        path.with_suffix(".json").write_text(json.dumps({**asdict(self), "env": env}, indent=2), encoding="utf-8")
        # PowerShell dot-source
        ps = path.with_suffix(".ps1")
        lines = [f'$env:{k} = "{v.replace(chr(34), chr(39))}"' for k, v in env.items()]
        ps.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # cmd set
        bat = path.with_suffix(".bat")
        bat_lines = [f'set "{k}={v}"' for k, v in env.items()]
        bat.write_text("\n".join(bat_lines) + "\n", encoding="utf-8")
