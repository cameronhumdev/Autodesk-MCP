"""Runtime LLM settings for test-ui (saved locally, no restart needed)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_SETTINGS_PATH = _DATA_DIR / "llm-settings.json"
_LOCK = threading.RLock()

PRESETS: dict[str, dict[str, Any]] = {
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen3:8b",
        "models": [
            "qwen3:8b",
            "qwen3:14b",
            "llama3.2",
            "llama3.1:8b",
            "mistral",
            "gemma3:12b",
        ],
        "mode": "live",
        "max_tokens": 8192,
        "needs_key": False,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o4-mini",
        ],
        "mode": "live",
        "max_tokens": 8192,
        "needs_key": True,
    },
    "claude": {
        "label": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-6",
        "models": [
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
        ],
        "mode": "live",
        "max_tokens": 8192,
        "needs_key": True,
        "help_url": "https://platform.claude.com/docs/en/get-api-key",
        "keys_url": "https://platform.claude.com/settings/keys",
    },
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3.2",
        "models": [],
        "mode": "live",
        "max_tokens": 8192,
        "needs_key": False,
    },
}


def _env_defaults() -> dict[str, Any]:
    return {
        "provider": _detect_provider(
            os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            os.getenv("LLM_MODEL", "llama3.2"),
        ),
        "base_url": os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/"),
        "model": os.getenv("LLM_MODEL", "llama3.2"),
        "api_key": (os.getenv("LLM_API_KEY") or "").strip(),
        "mode": (os.getenv("LLM_MODE") or "live").strip() or "live",
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS") or "8192"),
    }


def _detect_provider(base_url: str, model: str) -> str:
    lower = (base_url or "").lower()
    m = (model or "").lower()
    if "anthropic.com" in lower or m.startswith("claude"):
        return "claude"
    if "api.openai.com" in lower or m.startswith("gpt-"):
        return "openai"
    if "11434" in lower or "ollama" in lower:
        return "ollama"
    return "custom"


def _mask_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 12:
        return "••••••••"
    return f"{key[:7]}…{key[-4:]}"


def _read_file() -> dict[str, Any] | None:
    if not _SETTINGS_PATH.is_file():
        return None
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _normalize(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = _env_defaults()
    if not raw:
        return base
    provider = str(raw.get("provider") or base["provider"]).lower().strip()
    if provider not in PRESETS:
        provider = "custom"
    try:
        max_tokens = int(raw.get("max_tokens") or base["max_tokens"])
    except (TypeError, ValueError):
        max_tokens = 8192
    max_tokens = max(256, min(max_tokens, 128000))
    mode = str(raw.get("mode") or base["mode"]).lower().strip()
    if mode not in {"auto", "live", "demo"}:
        mode = "live"
    api_key = raw.get("api_key")
    if api_key is None:
        api_key = base["api_key"]
    else:
        api_key = str(api_key).strip()
    return {
        "provider": provider,
        "base_url": str(raw.get("base_url") or base["base_url"]).rstrip("/"),
        "model": str(raw.get("model") or base["model"]).strip() or base["model"],
        "api_key": api_key,
        "mode": mode,
        "max_tokens": max_tokens,
    }


def load_settings() -> dict[str, Any]:
    with _LOCK:
        return _normalize(_read_file())


def apply_to_env(settings: dict[str, Any]) -> None:
    """Push settings into process env so existing getenv paths stay in sync."""
    os.environ["LLM_BASE_URL"] = settings["base_url"]
    os.environ["LLM_MODEL"] = settings["model"]
    os.environ["LLM_MODE"] = settings["mode"]
    os.environ["LLM_MAX_TOKENS"] = str(settings["max_tokens"])
    key = (settings.get("api_key") or "").strip()
    if key:
        os.environ["LLM_API_KEY"] = key
    elif "LLM_API_KEY" in os.environ and settings.get("provider") == "ollama":
        # Local Ollama usually needs no key
        os.environ["LLM_API_KEY"] = ""


def bootstrap() -> dict[str, Any]:
    """Load saved settings (or env defaults) and apply at process start."""
    settings = load_settings()
    apply_to_env(settings)
    return settings


def public_settings() -> dict[str, Any]:
    s = load_settings()
    key = s.get("api_key") or ""
    return {
        "provider": s["provider"],
        "base_url": s["base_url"],
        "model": s["model"],
        "mode": s["mode"],
        "max_tokens": s["max_tokens"],
        "api_key_set": bool(key),
        "api_key_hint": _mask_key(key),
        "presets": {
            name: {
                "label": p["label"],
                "base_url": p["base_url"],
                "model": p["model"],
                "models": list(p.get("models") or []),
                "mode": p["mode"],
                "max_tokens": p["max_tokens"],
                "needs_key": p["needs_key"],
                "help_url": p.get("help_url"),
                "keys_url": p.get("keys_url"),
            }
            for name, p in PRESETS.items()
        },
    }


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch into saved settings. Empty api_key keeps the previous key."""
    with _LOCK:
        current = _normalize(_read_file())
        provider = str(patch.get("provider") or current["provider"]).lower().strip()
        if provider not in PRESETS:
            provider = "custom"

        # Applying a named preset fills defaults unless explicitly overridden.
        if "provider" in patch and provider in PRESETS and provider != "custom":
            preset = PRESETS[provider]
            if "base_url" not in patch:
                patch = {**patch, "base_url": preset["base_url"]}
            if "model" not in patch:
                patch = {**patch, "model": preset["model"]}
            if "mode" not in patch:
                patch = {**patch, "mode": preset["mode"]}
            if "max_tokens" not in patch:
                patch = {**patch, "max_tokens": preset["max_tokens"]}

        merged = {
            "provider": provider,
            "base_url": str(patch.get("base_url") or current["base_url"]).rstrip("/"),
            "model": str(patch.get("model") or current["model"]).strip(),
            "mode": str(patch.get("mode") or current["mode"]).strip(),
            "max_tokens": patch.get("max_tokens", current["max_tokens"]),
            "api_key": current["api_key"],
        }

        if "api_key" in patch:
            incoming = str(patch.get("api_key") or "").strip()
            # Blank means "leave unchanged" so the UI can save without re-pasting.
            if incoming:
                merged["api_key"] = incoming
            elif patch.get("clear_api_key"):
                merged["api_key"] = ""

        normalized = _normalize(merged)
        if PRESETS.get(provider, {}).get("needs_key") and not normalized["api_key"]:
            raise ValueError(
                f"{PRESETS[provider]['label']} needs an API key. "
                "Paste one, then Save."
            )

        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": normalized["provider"],
            "base_url": normalized["base_url"],
            "model": normalized["model"],
            "mode": normalized["mode"],
            "max_tokens": normalized["max_tokens"],
            "api_key": normalized["api_key"],
        }
        _SETTINGS_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        apply_to_env(normalized)
        return public_settings()


def client_config() -> tuple[str, str, str, int]:
    """base_url, model, api_key, max_tokens for live LLM calls."""
    s = load_settings()
    key = (s.get("api_key") or "").strip() or "no-key"
    return s["base_url"], s["model"], key, int(s["max_tokens"])
