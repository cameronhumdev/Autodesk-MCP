"""Persist chat sessions. Storage key is always a unique id; title is display-only."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "chats"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(chat_id: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"{chat_id}.json"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write(data: dict[str, Any]) -> dict[str, Any]:
    """Write by unique id filename only — title never affects storage path."""
    chat_id = data["id"]
    _path(chat_id).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _is_empty(data: dict[str, Any]) -> bool:
    return len(data.get("messages") or []) == 0


def purge_empty_chats(*, keep_id: str | None = None) -> None:
    """Remove blank chats except an optional id (e.g. one just created for first send)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in DATA_DIR.glob("*.json"):
        data = _read(path)
        if data is None or not _is_empty(data):
            continue
        if keep_id and (data.get("id") or path.stem) == keep_id:
            continue
        path.unlink(missing_ok=True)


def list_chats(track: str | None = None) -> list[dict[str, Any]]:
    # Do not purge here — a chat may be empty for a moment between create and first save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in DATA_DIR.glob("*.json"):
        data = _read(path)
        if data is None or _is_empty(data):
            continue
        chat_id = data.get("id") or path.stem
        chat_track = data.get("track")
        if chat_track not in {"inventor", "autocad"}:
            chat_track = "inventor"
        if track in {"inventor", "autocad"} and chat_track != track:
            continue
        items.append(
            {
                "id": chat_id,
                "track": chat_track,
                "title": data.get("title") or "Untitled",
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "message_count": len(data.get("messages") or []),
                "modeless": False,
            }
        )
    items.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
    return items


def get_chat(chat_id: str) -> dict[str, Any] | None:
    path = _path(chat_id)
    if not path.exists():
        return None
    data = _read(path)
    if data is None:
        return None
    empty = _is_empty(data)
    # Always prefer path stem as canonical id
    data["id"] = data.get("id") or chat_id
    data["modeless"] = empty
    if empty:
        data["track"] = None
    return data


def create_chat(track: str | None = None, title: str = "New chat") -> dict[str, Any]:
    """Create a new chat with a unique id. Title is display-only and may duplicate."""
    title = (title or "New chat").strip() or "New chat"
    normalized = track if track in {"inventor", "autocad"} else None
    chat_id = uuid.uuid4().hex  # full uuid — never keyed by title
    now = _now()
    # Do not purge other empties here — a sibling chat may still be between
    # create and first message save (concurrent sends / rapid New).
    return _write(
        {
            "id": chat_id,
            "track": normalized,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
    )


def save_chat(
    chat_id: str,
    *,
    messages: list[dict[str, Any]] | None = None,
    title: str | None = None,
    track: str | None = None,
) -> dict[str, Any] | None:
    path = _path(chat_id)
    if not path.exists():
        return None
    data = _read(path)
    if data is None:
        return None

    data["id"] = data.get("id") or chat_id
    if messages is not None:
        data["messages"] = messages
    # Title is display-only; never used as a storage key
    if title is not None and title.strip():
        data["title"] = title.strip()

    if _is_empty(data):
        data["track"] = None
        data["title"] = data.get("title") or "New chat"
    elif track is not None:
        data["track"] = _normalize_track(track)
    elif data.get("track") not in {"inventor", "autocad"}:
        data["track"] = "inventor"

    data["updated_at"] = _now()
    return _write(data)


def delete_chat(chat_id: str) -> bool:
    if not chat_id:
        return False
    path = _path(chat_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def title_from_messages(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "user" and (m.get("content") or "").strip():
            text = m["content"].strip().replace("\n", " ")
            return text[:56] + ("…" if len(text) > 56 else "")
    return "New chat"


def _normalize_track(track: str) -> str:
    t = (track or "").lower().strip()
    if t not in {"inventor", "autocad"}:
        raise ValueError("track must be inventor or autocad")
    return t
