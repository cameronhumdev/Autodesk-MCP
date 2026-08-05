"""Client agent config — local (relative MCP) vs cloud (gateway + download)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLIENT_DIR.parent
DEFAULT_CACHE = CLIENT_DIR / ".bundles"


@dataclass(frozen=True)
class ClientConfig:
    """DEPLOY_MODE=local|cloud."""

    deploy_mode: str
    gateway_url: str
    license_key: str
    install_root: Path
    bundle_cache: Path
    bundle_version: str
    tracks: tuple[str, ...]

    @property
    def is_local(self) -> bool:
        return self.deploy_mode == "local"

    @property
    def is_cloud(self) -> bool:
        return self.deploy_mode == "cloud"


def _mode() -> str:
    raw = (os.getenv("DEPLOY_MODE") or os.getenv("CLIENT_MODE") or "local").strip().lower()
    if raw in ("local", "dev", "onprem", "on-prem"):
        return "local"
    if raw in ("cloud", "download", "remote"):
        return "cloud"
    raise ValueError(f"Unknown DEPLOY_MODE={raw!r} (use local|cloud)")


def load_config() -> ClientConfig:
    root = Path(os.getenv("CLIENT_INSTALL_ROOT", str(REPO_ROOT))).expanduser().resolve()
    cache = Path(os.getenv("CLIENT_BUNDLE_CACHE", str(DEFAULT_CACHE))).expanduser().resolve()
    tracks_raw = (os.getenv("CLIENT_TRACKS") or "inventor,autocad").strip()
    tracks = tuple(t.strip() for t in tracks_raw.split(",") if t.strip())
    return ClientConfig(
        deploy_mode=_mode(),
        gateway_url=(os.getenv("GATEWAY_URL") or "http://127.0.0.1:8790").rstrip("/"),
        license_key=(os.getenv("LICENSE_KEY") or "").strip(),
        install_root=root,
        bundle_cache=cache,
        bundle_version=(os.getenv("CLIENT_BUNDLE_VERSION") or "latest").strip() or "latest",
        tracks=tracks or ("inventor", "autocad"),
    )
