"""Laptop CAD agent — long-poll gateway and run tools against local MCP."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import load_config
from .gateway import GatewayClient, GatewayError

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_paths() -> None:
    cad = REPO_ROOT / "cad"
    test_ui = REPO_ROOT / "test-ui"
    for p in (str(cad), str(REPO_ROOT), str(test_ui)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _build_dispatch():
    _ensure_paths()
    from test_ui_app.tools import build_dispatch

    def _no_rag(query: str, k: int = 4):
        return []

    return build_dispatch(_no_rag)


def _http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json", "User-Agent": "dc-cad-agent/0.1"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _run_job(dispatch, job: dict[str, Any]) -> dict[str, Any]:
    from test_ui_app.tools import (
        ensure_autocad_ready,
        ensure_inventor_ready,
        force_restart_autocad_confirmed,
        force_restart_inventor_confirmed,
        run_tool,
    )
    from shared.launch_cad import launch_status

    tool = str(job.get("tool") or "")
    args = job.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}

    try:
        if tool == "__list_tools__":
            track = str(args.get("track") or "inventor").lower()
            backend_name = "inventor" if track == "inventor" else "autocad"
            from inventor import get_inventor_backend
            from autocad import get_autocad_backend

            backend = (
                get_inventor_backend()
                if backend_name == "inventor"
                else get_autocad_backend()
            )
            return {"ok": True, "tools": backend.list_upstream_tools()}
        if tool == "__cad_launch_status__":
            return {"ok": True, **launch_status(str(args.get("app") or ""))}
        if tool == "__cad_launch__":
            app = str(args.get("app") or "").lower()
            wait_s = float(args.get("wait_s") or 90)
            path = (args.get("drawing_path") or "").strip() or None
            force_restart = bool(args.get("force_restart"))
            if app == "inventor":
                return ensure_inventor_ready(
                    force_reset=True, wait_s=wait_s, force_restart=force_restart
                )
            if app == "autocad":
                return ensure_autocad_ready(
                    force_reset=True,
                    wait_s=wait_s,
                    drawing_path=path,
                    force_restart=force_restart,
                )
            return {"ok": False, "error": "app must be inventor or autocad"}
        if tool == "__cad_force_restart__":
            app = str(args.get("app") or "autocad").lower()
            reason = str(args.get("reason") or "").strip()
            wait_s = float(args.get("wait_s") or 90)
            path = (args.get("drawing_path") or "").strip() or None
            if not reason:
                return {"ok": False, "error": "reason required"}
            if app == "inventor":
                return force_restart_inventor_confirmed(wait_s=wait_s, reason=reason)
            return force_restart_autocad_confirmed(
                drawing_path=path, wait_s=wait_s, reason=reason
            )

        raw = run_tool(dispatch, tool, args)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"ok": True, "raw": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"ok": True, "result": parsed}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def serve_agent(poll_wait_s: float = 25.0) -> int:
    """Block forever: activate → hello → poll → execute local MCP tools."""
    cfg = load_config()
    # Force cloud gateway URL even if DEPLOY_MODE=local for MCP paths
    gw = GatewayClient(cfg.gateway_url, cfg.license_key or "dev-local")
    print(f"Activating at {cfg.gateway_url} …", flush=True)
    try:
        session = gw.activate()
    except GatewayError as exc:
        print(f"activate failed: {exc}", flush=True)
        return 1
    token = session.token
    print(f"Session ok (tenant={session.tenant_id}). Loading local CAD tools…", flush=True)
    dispatch = _build_dispatch()
    _http_json(
        "POST",
        f"{cfg.gateway_url}/v1/agent/hello",
        token=token,
        body={"meta": {"host": "windows-laptop", "role": "cad-agent"}},
    )
    print(
        "CAD agent online — keep this window open.\n"
        f"  Gateway: {cfg.gateway_url}\n"
        "  Cloud UI tools will run against Inventor/AutoCAD on THIS PC.",
        flush=True,
    )
    while True:
        try:
            data = _http_json(
                "GET",
                f"{cfg.gateway_url}/v1/agent/poll?wait={poll_wait_s}",
                token=token,
                timeout=poll_wait_s + 10,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                print("Session expired — re-activating…", flush=True)
                session = gw.activate()
                token = session.token
                continue
            print(f"poll HTTP {exc.code}: {exc.read()[:200]}", flush=True)
            time.sleep(2)
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"poll error: {exc}", flush=True)
            time.sleep(2)
            continue

        job = data.get("job")
        if not job:
            continue
        jid = job.get("id")
        tool = job.get("tool")
        print(f"→ job {jid}: {tool}", flush=True)
        result = _run_job(dispatch, job)
        # Keep structured failures/Confirm cards in `result` for the cloud UI.
        hard_fail = (
            isinstance(result, dict)
            and result.get("ok") is False
            and not result.get("needs_confirmation")
            and bool(result.get("error"))
        )
        try:
            _http_json(
                "POST",
                f"{cfg.gateway_url}/v1/agent/result",
                token=token,
                body={
                    "id": jid,
                    "ok": not hard_fail,
                    "result": result,
                    "error": (result.get("error") if hard_fail and isinstance(result, dict) else None),
                },
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"result post failed: {exc}", flush=True)
        print(f"← done {tool} hard_fail={hard_fail}", flush=True)
