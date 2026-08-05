"""Minimal local gateway for testing activate + bundle download (stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import REPO_ROOT
from .download import build_track_zip
from .relay import HUB

_SESSIONS: dict[str, dict] = {}
_BUNDLES: dict[str, Path] = {}
_VERSION = "0.1.0-dev"
_SERVICE_KEY = (os.getenv("CAD_SERVICE_KEY") or "dev-cloud").strip()


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _prepare_bundles(install_root: Path, bundle_dir: Path) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for track in ("inventor", "autocad"):
        zpath = bundle_dir / f"{track}-{_VERSION}.zip"
        build_track_zip(track, install_root, zpath)
        _BUNDLES[track] = zpath


class Handler(BaseHTTPRequestHandler):
    server_version = "DCCadGatewayStub/0.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print(f"[gateway] {self.address_string()} {fmt % args}")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _token(self) -> str | None:
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        return None

    def _tenant(self) -> str | None:
        token = self._token()
        if not token or token not in _SESSIONS:
            return None
        return str(_SESSIONS[token].get("tenant_id") or "dev")

    def _service_ok(self) -> bool:
        key = self.headers.get("X-Service-Key") or ""
        return bool(_SERVICE_KEY) and key == _SERVICE_KEY

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/v1/health":
            self._json(
                200,
                {
                    "ok": True,
                    "service": "dc-cad-gateway-stub",
                    "version": _VERSION,
                    "agent_online": HUB.agent_online("dev"),
                },
            )
            return
        if parsed.path == "/v1/agent/status":
            tenant = self._tenant() or "dev"
            self._json(
                200,
                {
                    "ok": True,
                    "tenant_id": tenant,
                    "agent_online": HUB.agent_online(tenant),
                },
            )
            return
        if parsed.path == "/v1/agent/poll":
            tenant = self._tenant()
            if not tenant:
                self._json(401, {"error": "invalid session"})
                return
            qs = parse_qs(parsed.query)
            wait_s = float((qs.get("wait") or ["25"])[0])
            HUB.agent_hello(tenant)
            job = HUB.poll(tenant, wait_s=wait_s)
            self._json(200, {"ok": True, "job": job})
            return
        if parsed.path == "/v1/bundles/manifest":
            qs = parse_qs(parsed.query)
            ver = (qs.get("version") or ["latest"])[0]
            if ver == "latest":
                ver = _VERSION
            base = f"http://{self.headers.get('Host')}"
            tracks = {}
            for track, zpath in _BUNDLES.items():
                tracks[track] = {
                    "version": ver,
                    "url": f"{base}/v1/bundles/{track}/{ver}.zip",
                    "sha256": _file_sha256(zpath),
                    "bytes": zpath.stat().st_size,
                }
            self._json(200, {"version": ver, "tracks": tracks})
            return
        # /v1/bundles/{track}/{version}.zip
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[0] == "v1" and parts[1] == "bundles" and parts[3].endswith(".zip"):
            track = parts[2]
            zpath = _BUNDLES.get(track)
            if not zpath or not zpath.is_file():
                self._json(404, {"error": f"no bundle for {track}"})
                return
            data = zpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-SHA256", hashlib.sha256(data).hexdigest())
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/v1/session/activate":
            body = self._read_json()
            key = body.get("license_key") or self.headers.get("X-License-Key") or "dev-local"
            token = secrets.token_urlsafe(24)
            _SESSIONS[token] = {"license_key": key, "tenant_id": "dev"}
            self._json(
                200,
                {
                    "token": token,
                    "tenant_id": "dev",
                    "expires_in_s": 3600,
                    "license_key_preview": str(key)[:4] + "…",
                },
            )
            return
        if parsed.path == "/v1/session/heartbeat":
            token = self._token()
            if not token or token not in _SESSIONS:
                self._json(401, {"error": "invalid session"})
                return
            tenant = str(_SESSIONS[token]["tenant_id"])
            HUB.agent_heartbeat(tenant)
            self._json(200, {"ok": True, "tenant_id": tenant})
            return
        if parsed.path == "/v1/agent/hello":
            tenant = self._tenant()
            if not tenant:
                self._json(401, {"error": "invalid session"})
                return
            body = self._read_json()
            HUB.agent_hello(tenant, meta=body.get("meta") or {})
            self._json(200, {"ok": True, "tenant_id": tenant})
            return
        if parsed.path == "/v1/agent/result":
            tenant = self._tenant()
            if not tenant:
                self._json(401, {"error": "invalid session"})
                return
            body = self._read_json()
            job_id = str(body.get("id") or "")
            ok = bool(body.get("ok", True))
            if not job_id:
                self._json(400, {"error": "id required"})
                return
            found = HUB.submit_result(
                job_id,
                ok=ok,
                result=body.get("result"),
                error=body.get("error"),
            )
            if not found:
                self._json(404, {"error": "unknown job"})
                return
            self._json(200, {"ok": True})
            return
        if parsed.path == "/v1/tools/call":
            if not self._service_ok():
                self._json(401, {"error": "invalid service key"})
                return
            body = self._read_json()
            tool = str(body.get("tool") or "").strip()
            if not tool:
                self._json(400, {"error": "tool required"})
                return
            args = body.get("arguments")
            if not isinstance(args, dict):
                args = {}
            tenant = str(body.get("tenant_id") or "dev")
            timeout_s = float(body.get("timeout_s") or 120)
            result = HUB.call_tool(tool, args, tenant_id=tenant, timeout_s=timeout_s)
            self._json(200, result)
            return
        self._json(404, {"error": "not found"})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Dev gateway stub (activate + MCP bundle download)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8790)
    p.add_argument("--root", type=Path, default=REPO_ROOT, help="Install/repo root to pack from")
    args = p.parse_args(argv)

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((args.host, args.port))
    except OSError as exc:
        print(f"Port {args.host}:{args.port} already in use — stop the other gateway stub first ({exc})", flush=True)
        return 1
    finally:
        probe.close()

    bundle_dir = Path(__file__).resolve().parent / ".bundles" / "stub-serve"
    print(f"Packing track zips from {args.root} …", flush=True)
    _prepare_bundles(args.root.resolve(), bundle_dir)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Gateway stub listening on http://{args.host}:{args.port}", flush=True)
    print("  GET  /v1/health", flush=True)
    print("  POST /v1/session/activate", flush=True)
    print("  GET  /v1/agent/poll  (+ hello/result) — laptop CAD agent", flush=True)
    print("  POST /v1/tools/call — cloud UI → laptop (X-Service-Key)", flush=True)
    print("  GET  /v1/bundles/manifest", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
