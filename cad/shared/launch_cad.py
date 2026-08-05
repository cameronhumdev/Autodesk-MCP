"""Allowlisted local launch of Inventor / AutoCAD (never arbitrary executables)."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

# Fixed candidates only — env overrides must still resolve into this set.
_INVENTOR_ALLOWLIST = (
    Path(r"C:\Program Files\Autodesk\Inventor 2027\Bin\Inventor.exe"),
    Path(r"C:\Program Files\Autodesk\Inventor 2026\Bin\Inventor.exe"),
    Path(r"C:\Program Files\Autodesk\Inventor 2025\Bin\Inventor.exe"),
)
_AUTOCAD_ALLOWLIST = (
    Path(r"C:\Program Files\Autodesk\AutoCAD 2027\acad.exe"),
    Path(r"C:\Program Files\Autodesk\AutoCAD 2026\acad.exe"),
    Path(r"C:\Program Files\Autodesk\AutoCAD 2025\acad.exe"),
)

_INVENTOR_PROCESSES = frozenset({"inventor.exe"})
_AUTOCAD_PROCESSES = frozenset({"acad.exe"})


def _normalize_app(app: str) -> str:
    a = (app or "").lower().strip()
    if a in {"inventor", "inv"}:
        return "inventor"
    if a in {"autocad", "acad", "auto cad"}:
        return "autocad"
    raise ValueError("app must be inventor or autocad")


def _allowlist(app: str) -> tuple[Path, ...]:
    return _INVENTOR_ALLOWLIST if app == "inventor" else _AUTOCAD_ALLOWLIST


def _process_names(app: str) -> frozenset[str]:
    return _INVENTOR_PROCESSES if app == "inventor" else _AUTOCAD_PROCESSES


def _env_override(app: str) -> Path | None:
    key = "INVENTOR_EXE" if app == "inventor" else "AUTOCAD_EXE"
    raw = (os.getenv(key) or "").strip()
    if not raw:
        return None
    return Path(raw)


def resolve_exe(app: str) -> Path | None:
    """Return an existing allowlisted exe, or None if not installed."""
    app = _normalize_app(app)
    allowed = {p.resolve() for p in _allowlist(app)}
    override = _env_override(app)
    if override is not None:
        try:
            resolved = override.expanduser().resolve()
        except OSError:
            resolved = None
        if resolved is not None and resolved in allowed and resolved.is_file():
            return resolved
        # Override path must be an exact allowlisted file
        if resolved is not None and resolved.is_file():
            # Also accept if the override equals an allowlist entry by string
            for cand in _allowlist(app):
                if resolved == cand.resolve() and resolved.is_file():
                    return resolved
        return None

    for cand in _allowlist(app):
        if cand.is_file():
            return cand.resolve()
    return None


def is_running(app: str) -> bool:
    """True if a known process image for the app is running."""
    app = _normalize_app(app)
    names = _process_names(app)
    try:
        # tasklist is available on supported Windows hosts for this product
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        # "Image Name","PID",...
        line = line.strip()
        if not line.startswith('"'):
            continue
        image = line.split('","', 1)[0].strip('"').lower()
        if image in names:
            return True
    return False


def _force_quit(app: str) -> bool:
    """Force-end allowlisted CAD processes (used when COM/RPC is dead)."""
    app = _normalize_app(app)
    image = "acad.exe" if app == "autocad" else "inventor.exe"
    try:
        proc = subprocess.run(
            ["taskkill", "/IM", image, "/F"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    # Wait until the image disappears
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if not is_running(app):
            return True
        time.sleep(0.5)
    return not is_running(app) or proc.returncode == 0


def launch_status(app: str) -> dict[str, Any]:
    """Non-mutating status for UI / tools."""
    app = _normalize_app(app)
    exe = resolve_exe(app)
    running = is_running(app)
    label = "Inventor" if app == "inventor" else "AutoCAD"
    return {
        "app": app,
        "label": label,
        "running": running,
        "exe": str(exe) if exe else None,
        "installed": exe is not None,
    }


def _autocad_ensure_drawing(
    *, wait_s: float = 90.0, drawing_path: str | None = None
) -> dict[str, Any]:
    """
    Attach to a running AutoCAD via GetActiveObject only (never Dispatch/launch)
    and ensure a drawing is open.

    If drawing_path is set, open that .dwg/.dxf (existing project). Otherwise
    reuse an already-open document or create a blank one.
    """
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "error": (
                "pywin32 is required to open a drawing after launch. "
                "Install: pip install 'autocad-mcp-pro[com]'"
            ),
        }

    target: Path | None = None
    if drawing_path and str(drawing_path).strip():
        target = Path(str(drawing_path).strip().strip('"')).expanduser()
        try:
            target = target.resolve()
        except OSError:
            return {
                "ok": False,
                "error": f"Invalid drawing path: {drawing_path}",
            }
        if not target.is_file():
            return {
                "ok": False,
                "error": f"Drawing not found: {target}",
            }
        if target.suffix.lower() not in {".dwg", ".dxf"}:
            return {
                "ok": False,
                "error": f"Path must be a .dwg or .dxf file: {target}",
            }

    deadline = time.monotonic() + max(5.0, float(wait_s))
    last_err = "AutoCAD COM not ready"
    pythoncom.CoInitialize()
    try:
        while time.monotonic() < deadline:
            try:
                # GetActiveObject only — Dispatch would silently start AutoCAD.
                app = win32com.client.GetActiveObject("AutoCAD.Application")
                try:
                    app.Visible = True
                except Exception:
                    pass

                if target is not None:
                    # Reuse if already open (match by full path or file name).
                    want = str(target).lower()
                    want_name = target.name.lower()
                    for i in range(int(app.Documents.Count)):
                        try:
                            doc = app.Documents.Item(i)
                            full = str(getattr(doc, "FullName", "") or "").lower()
                            name = str(getattr(doc, "Name", "") or "").lower()
                            if full == want or name == want_name:
                                try:
                                    doc.Activate()
                                except Exception:
                                    pass
                                return {
                                    "ok": True,
                                    "drawing": str(getattr(doc, "Name", "") or target.name),
                                    "path": str(target),
                                    "created_drawing": False,
                                    "opened_existing": True,
                                    "message": f"Using already-open drawing {target.name}.",
                                }
                        except Exception:
                            continue
                    doc = app.Documents.Open(str(target))
                    name = str(getattr(doc, "Name", "") or target.name)
                    return {
                        "ok": True,
                        "drawing": name,
                        "path": str(target),
                        "created_drawing": False,
                        "opened_existing": True,
                        "message": f"Opened existing drawing {name}.",
                    }

                count = int(app.Documents.Count)
                if count <= 0:
                    doc = app.Documents.Add()
                    name = str(getattr(doc, "Name", "") or "Drawing1.dwg")
                    return {
                        "ok": True,
                        "drawing": name,
                        "created_drawing": True,
                        "opened_existing": False,
                        "message": f"Opened new drawing {name}.",
                    }
                doc = app.ActiveDocument
                name = str(getattr(doc, "Name", "") or "active")
                return {
                    "ok": True,
                    "drawing": name,
                    "created_drawing": False,
                    "opened_existing": False,
                    "message": f"Using open drawing {name}.",
                }
            except Exception as exc:  # noqa: BLE001 — poll until ready
                last_err = str(exc)
                time.sleep(1.5)
        return {
            "ok": False,
            "error": (
                "AutoCAD process is running but COM is not ready / no drawing "
                f"could be opened within {int(wait_s)}s: {last_err}"
            ),
        }
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def ensure_ready(
    app: str,
    *,
    wait_s: float = 90.0,
    drawing_path: str | None = None,
    force_restart: bool = False,
) -> dict[str, Any]:
    """Alias for start_app — start if needed; AutoCAD opens path or a new drawing."""
    return start_app(
        app,
        wait_s=wait_s,
        drawing_path=drawing_path,
        force_restart=force_restart,
    )


def start_app(
    app: str,
    *,
    wait_s: float = 90.0,
    drawing_path: str | None = None,
    force_restart: bool = False,
) -> dict[str, Any]:
    """
    Start an allowlisted CAD app if needed, wait until the process is running.

    For AutoCAD: also wait for COM and open drawing_path if given, else ensure
    a real drawing is open (start screen alone causes RPC / Documents.Count failures).

    force_restart: quit a zombie process first (COM/RPC dead but acad.exe still listed).
    Only call with force_restart=True after explicit user Confirm (test-ui
    /api/cad/force-restart). Never silent-kill from soft recover paths.

    Does not run arbitrary commands.
    Never uses COM Dispatch to auto-launch AutoCAD — only the allowlisted exe.
    """
    app = _normalize_app(app)
    label = "Inventor" if app == "inventor" else "AutoCAD"
    status = launch_status(app)

    if not status["installed"]:
        return {
            "ok": False,
            "app": app,
            "label": label,
            "error": f"{label} executable not found in allowlist (install or set path).",
            "running": False,
        }

    force_restarted = False
    if force_restart and status["running"]:
        _force_quit(app)
        force_restarted = True
        status = launch_status(app)

    already = bool(status["running"]) and not force_restarted
    started = False

    if not status["running"]:
        exe = Path(status["exe"])
        # Final allowlist check before spawn
        allowed = {p.resolve() for p in _allowlist(app) if p.is_file()}
        if exe.resolve() not in allowed:
            return {
                "ok": False,
                "app": app,
                "label": label,
                "error": "Refused to start — path is not allowlisted.",
                "running": False,
            }

        launch_cmd = [str(exe)]
        # Cold-start AutoCAD directly into an existing drawing when asked.
        if app == "autocad" and drawing_path:
            cand = Path(str(drawing_path).strip().strip('"')).expanduser()
            try:
                cand = cand.resolve()
            except OSError:
                cand = None  # type: ignore[assignment]
            if cand is not None and cand.is_file() and cand.suffix.lower() in {
                ".dwg",
                ".dxf",
            }:
                launch_cmd.append(str(cand))

        try:
            subprocess.Popen(  # noqa: S603 — path is allowlisted above
                launch_cmd,
                cwd=str(exe.parent),
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError as exc:
            return {
                "ok": False,
                "app": app,
                "label": label,
                "error": f"Failed to start {label}: {exc}",
                "running": False,
                "exe": str(exe),
            }

        started = True
        deadline = time.monotonic() + max(5.0, float(wait_s))
        while time.monotonic() < deadline:
            if is_running(app):
                break
            time.sleep(1.0)
        else:
            return {
                "ok": False,
                "app": app,
                "label": label,
                "error": f"Started {label} but process did not appear within {int(wait_s)}s.",
                "running": is_running(app),
                "exe": str(exe),
                "started": True,
            }

    # AutoCAD: process alone is not enough — need COM + a document.
    if app == "autocad":
        # After a fresh start, COM registration lags behind tasklist.
        remaining = max(30.0, float(wait_s) * 0.6)
        ready = _autocad_ensure_drawing(
            wait_s=remaining, drawing_path=drawing_path
        )
        # Do NOT auto taskkill here. Transient GetActiveObject failures are common
        # while AutoCAD is busy; killing the app made it look like constant
        # close/open. Callers that truly need a zombie kill pass force_restart=True.
        if not ready.get("ok"):
            return {
                "ok": False,
                "app": app,
                "label": label,
                "already_running": already,
                "started": started,
                "force_restarted": force_restarted,
                "running": is_running(app),
                "exe": status["exe"],
                "error": ready.get("error")
                or "AutoCAD started but a drawing could not be opened.",
                "hint": (
                    "AutoCAD process is running but COM could not attach. "
                    "Retry soft recover, or ask the user to Confirm a quit/restart "
                    'via recover_autocad with {"force_restart": true, "reason": "..."}.'
                ),
            }
        return {
            "ok": True,
            "app": app,
            "label": label,
            "already_running": already,
            "started": started,
            "force_restarted": force_restarted,
            "running": True,
            "exe": status["exe"],
            "drawing": ready.get("drawing"),
            "path": ready.get("path"),
            "created_drawing": ready.get("created_drawing"),
            "opened_existing": ready.get("opened_existing"),
            "message": (
                ("Restarted AutoCAD. " if force_restarted else "")
                + ("Started AutoCAD. " if started and not force_restarted else "")
                + (
                    "AutoCAD was already running. "
                    if already and not started and not force_restarted
                    else ""
                )
                + str(ready.get("message") or "Drawing ready.")
            ),
        }

    # Inventor: process up is enough for start_app — host ensure_inventor_ready
    # polls the Bimwright add-in target and opens a new part.
    note = ""
    if app == "inventor":
        note = (
            " Host will wait for the Bimwright MCP add-in target and open a new part."
        )
    return {
        "ok": True,
        "app": app,
        "label": label,
        "already_running": already,
        "started": started,
        "force_restarted": force_restarted,
        "running": True,
        "exe": status["exe"],
        "message": (
            (
                ("Restarted Inventor. " if force_restarted else "")
                + (
                    f"{'Started' if started and not force_restarted else 'Already running'} "
                    f"{label}.{note}"
                    if started or already or force_restarted
                    else f"{label} is ready.{note}"
                )
            )
        ),
    }
