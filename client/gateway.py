"""Outbound gateway client — activate session + fetch bundle manifest."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Session:
    token: str
    tenant_id: str
    expires_in_s: int
    raw: dict[str, Any]


class GatewayError(RuntimeError):
    pass


class GatewayClient:
    def __init__(self, base_url: str, license_key: str = "", timeout_s: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.license_key = license_key
        self.timeout_s = timeout_s
        self.session: Session | None = None

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json", "User-Agent": "dc-cad-client/0.1"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif self.license_key:
            headers["X-License-Key"] = self.license_key
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GatewayError(f"{method} {path} → HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GatewayError(f"{method} {path} → {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health")

    def activate(self) -> Session:
        payload = {"license_key": self.license_key or "dev-local"}
        data = self._request("POST", "/v1/session/activate", body=payload)
        token = str(data.get("token") or "")
        if not token:
            raise GatewayError("activate response missing token")
        self.session = Session(
            token=token,
            tenant_id=str(data.get("tenant_id") or "default"),
            expires_in_s=int(data.get("expires_in_s") or 3600),
            raw=data,
        )
        return self.session

    def heartbeat(self) -> dict[str, Any]:
        if not self.session:
            raise GatewayError("not activated")
        return self._request("POST", "/v1/session/heartbeat", body={}, token=self.session.token)

    def fetch_manifest(self, version: str = "latest") -> dict[str, Any]:
        token = self.session.token if self.session else None
        return self._request("GET", f"/v1/bundles/manifest?version={version}", token=token)

    def download_url(self, track: str, version: str) -> str:
        """Absolute URL for a track bundle zip."""
        return f"{self.base_url}/v1/bundles/{track}/{version}.zip"
