"""Proxy CAD tools/launch to the cloud gateway → laptop agent."""

from __future__ import annotations

import os
from typing import Any

import httpx

_GATEWAY = (os.getenv("GATEWAY_URL") or os.getenv("CAD_PROXY_URL") or "").rstrip("/")
_SERVICE_KEY = (os.getenv("CAD_SERVICE_KEY") or "dev-cloud").strip()
_TENANT = (os.getenv("CAD_TENANT_ID") or "dev").strip()


def cad_mode() -> str:
    return (os.getenv("CAD_MODE") or "local").lower().strip() or "local"


def is_remote() -> bool:
    return cad_mode() == "remote" and bool(_GATEWAY)


def call_remote_tool(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    timeout_s: float = 120.0,
) -> Any:
    if not _GATEWAY:
        raise RuntimeError("GATEWAY_URL not set for CAD_MODE=remote")
    payload = {
        "tool": tool,
        "arguments": arguments or {},
        "tenant_id": _TENANT,
        "timeout_s": timeout_s,
    }
    with httpx.Client(timeout=timeout_s + 15.0) as client:
        r = client.post(
            f"{_GATEWAY}/v1/tools/call",
            headers={"X-Service-Key": _SERVICE_KEY, "Accept": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


def agent_status() -> dict[str, Any]:
    if not _GATEWAY:
        return {"ok": False, "agent_online": False, "error": "GATEWAY_URL unset"}
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{_GATEWAY}/v1/health")
            r.raise_for_status()
            data = r.json()
            return {
                "ok": True,
                "agent_online": bool(data.get("agent_online")),
                "gateway": _GATEWAY,
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "agent_online": False, "error": str(exc), "gateway": _GATEWAY}
