from __future__ import annotations

import os


def get_rag_backend():
    """Factory — swap backends with RAG_BACKEND env."""
    name = os.getenv("RAG_BACKEND", "local").lower().strip()
    if name == "local":
        from rag.local.backend import LocalRagBackend

        return LocalRagBackend()
    if name == "anythingllm":
        raise NotImplementedError(
            "AnythingLLM adapter not wired yet — use RAG_BACKEND=local for tests."
        )
    raise ValueError(f"Unknown RAG_BACKEND={name!r}")
