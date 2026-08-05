"""CLI: python -m client ensure|connect|run|gateway"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python -m client` from repo root without installing the package
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="client", description="DC CAD client agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ensure", help="Resolve MCP paths (local relative or cloud download)")
    sub.add_parser("connect", help="Outbound gateway activate + heartbeat")
    sub.add_parser("run", help="ensure + connect + write runtime env")
    g = sub.add_parser("gateway", help="Run local gateway stub (dev)")
    g.add_argument("--host", default="127.0.0.1")
    g.add_argument("--port", type=int, default=8790)

    args = parser.parse_args(argv)

    if args.cmd == "gateway":
        from client.gateway_stub import main as gw_main

        return gw_main(["--host", args.host, "--port", str(args.port)])

    from client.agent import ClientAgent
    from client.config import load_config

    agent = ClientAgent(load_config())

    if args.cmd == "ensure":
        paths = agent.ensure_mcp()
        runtime = agent.config.bundle_cache / "runtime"
        paths.write_runtime_env(runtime / "mcp")
        print(json.dumps({"ok": True, **paths.__dict__, "env_dir": str(runtime)}, indent=2))
        return 0

    if args.cmd == "connect":
        token = agent.connect_gateway()
        print(json.dumps({"ok": True, "token_preview": token[:8] + "…", "mode": agent.config.deploy_mode}, indent=2))
        return 0

    if args.cmd == "run":
        result = agent.run()
        print(
            json.dumps(
                {
                    "ok": result.gateway_ok,
                    "message": result.message,
                    "source": result.paths.source,
                    "root": result.paths.root,
                    "inventor_command": result.paths.inventor_command,
                    "autocad_command": result.paths.autocad_command,
                    "session": bool(result.session_token),
                    "runtime_env": str(agent.config.bundle_cache / "runtime"),
                },
                indent=2,
            )
        )
        return 0 if result.gateway_ok else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
