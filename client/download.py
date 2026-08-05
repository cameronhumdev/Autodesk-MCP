"""Cloud mode: download MCP track bundles from the gateway into a local cache."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .gateway import GatewayClient, GatewayError
from .local import resolve_local
from .paths import McpPaths


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_file(url: str, dest: Path, token: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "dc-cad-client/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


def download_bundles(
    gateway: GatewayClient,
    cache_dir: Path,
    tracks: tuple[str, ...],
    version: str = "latest",
) -> McpPaths:
    """
    Fetch manifest → download each track zip → extract under cache_dir/current/.
    Then resolve commands the same way as local (relative to extract root).
    """
    if not gateway.session:
        gateway.activate()

    manifest = gateway.fetch_manifest(version)
    resolved_version = str(manifest.get("version") or version)
    tracks_meta = manifest.get("tracks") or {}
    extract_root = cache_dir / "current"
    extract_root.mkdir(parents=True, exist_ok=True)

    token = gateway.session.token if gateway.session else None

    for track in tracks:
        meta = tracks_meta.get(track)
        if not meta:
            raise GatewayError(f"manifest missing track {track!r}")
        url = str(meta.get("url") or gateway.download_url(track, resolved_version))
        expect_sha = (meta.get("sha256") or "").strip().lower()
        zip_path = cache_dir / "downloads" / f"{track}-{resolved_version}.zip"
        _download_file(url, zip_path, token=token)
        if expect_sha:
            got = _sha256(zip_path)
            if got != expect_sha:
                raise GatewayError(f"{track} sha256 mismatch: got {got}, want {expect_sha}")
        track_dir = extract_root / track
        _extract_zip(zip_path, track_dir)

    # Marker so local resolver treats cache as install root for both tracks
    paths = resolve_local(extract_root, tracks)
    return McpPaths(
        inventor_command=paths.inventor_command,
        autocad_command=paths.autocad_command,
        source="download",
        root=str(extract_root),
    )


def build_track_zip(track: str, install_root: Path, out_zip: Path) -> str:
    """Dev helper: zip local MCP bits for the gateway stub to serve."""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / track
        staging.mkdir(parents=True)
        if track == "inventor":
            server = None
            base = install_root / "vendor" / "ipt-mcp" / "src" / "server" / "bin" / "Release"
            for tfm in ("net10.0", "net9.0", "net8.0"):
                candidate = base / tfm / "Bimwright.Ipt.Server.exe"
                if candidate.is_file():
                    server = candidate
                    break
            if server is None:
                # Tiny placeholder so download path is testable without a build
                placeholder = staging / "Bimwright.Ipt.Server.exe"
                placeholder.write_bytes(b"MZ-PLACEHOLDER-INVENTOR-MCP\n")
            else:
                # Stub/dev zip: server exe only (full dependency pack comes later)
                shutil.copy2(server, staging / server.name)
        elif track == "autocad":
            venv_exe = install_root / ".venv" / "Scripts" / "autocad-mcp.exe"
            target = staging / "autocad-mcp.exe"
            if venv_exe.is_file():
                shutil.copy2(venv_exe, target)
            else:
                target.write_bytes(b"MZ-PLACEHOLDER-AUTOCAD-MCP\n")
            (staging / "README.txt").write_text(
                "AutoCAD MCP stub/bundle. Prefer real autocad-mcp-pro in production.\n",
                encoding="utf-8",
            )
        else:
            raise ValueError(f"unknown track {track!r}")

        if out_zip.exists():
            out_zip.unlink()
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in staging.rglob("*"):
                if f.is_file():
                    zf.write(f, arcname=str(f.relative_to(staging)))
    return _sha256(out_zip)
