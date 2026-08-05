"""Download / resolve agent — local relative MCP or gateway download + session."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import ClientConfig, load_config
from .download import download_bundles
from .gateway import GatewayClient, GatewayError
from .local import resolve_local
from .paths import McpPaths


@dataclass
class AgentResult:
    paths: McpPaths
    session_token: str | None
    gateway_ok: bool
    message: str


class ClientAgent:
    def __init__(self, config: ClientConfig | None = None) -> None:
        self.config = config or load_config()
        self.gateway = GatewayClient(self.config.gateway_url, self.config.license_key)

    def ensure_mcp(self) -> McpPaths:
        """Local → relative paths. Cloud → activate + download bundles, then resolve."""
        if self.config.is_local:
            return resolve_local(self.config.install_root, self.config.tracks)
        self.gateway.activate()
        return download_bundles(
            self.gateway,
            self.config.bundle_cache,
            self.config.tracks,
            version=self.config.bundle_version,
        )

    def connect_gateway(self) -> str:
        """Outbound session to cloud gateway (cloud mode). Local mode is a no-op token."""
        if self.config.is_local:
            return "local-no-gateway"
        if not self.gateway.session:
            self.gateway.activate()
        assert self.gateway.session is not None
        self.gateway.heartbeat()
        return self.gateway.session.token

    def run(self) -> AgentResult:
        """Ensure MCP paths, connect gateway when cloud, write runtime env files."""
        paths = self.ensure_mcp()
        token: str | None = None
        gateway_ok = False
        if self.config.is_cloud:
            try:
                token = self.connect_gateway()
                gateway_ok = True
                msg = f"cloud: MCP from gateway download; session ok (tenant relay at {self.config.gateway_url})"
            except GatewayError as exc:
                msg = f"cloud: MCP resolved but gateway error: {exc}"
        else:
            msg = "local: MCP from relative install paths (no download)"
            gateway_ok = True

        runtime = self.config.bundle_cache / "runtime"
        paths.write_runtime_env(runtime / "mcp")
        # Apply into this process so callers importing after run() see commands
        for k, v in paths.as_env().items():
            os.environ[k] = v
        if token and token != "local-no-gateway":
            os.environ["CLIENT_SESSION_TOKEN"] = token
        os.environ["DEPLOY_MODE"] = self.config.deploy_mode
        os.environ["GATEWAY_URL"] = self.config.gateway_url

        return AgentResult(paths=paths, session_token=token, gateway_ok=gateway_ok, message=msg)
