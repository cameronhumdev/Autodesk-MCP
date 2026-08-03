"""Swappable RAG backend contract.

Any folder under rag/ that you wire in via RAG_BACKEND should expose a
backend class matching this interface (duck-typed is fine).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RagHit:
    source: str
    text: str
    score: float = 0.0


class RagBackend(Protocol):
    name: str

    def ingest_text(self, doc_id: str, text: str, source: str = "") -> None:
        """Store or update a text document."""

    def search(self, query: str, top_k: int = 4) -> list[RagHit]:
        """Return relevant chunks for a query."""

    def status(self) -> dict:
        """Health / backend metadata for the UI."""
