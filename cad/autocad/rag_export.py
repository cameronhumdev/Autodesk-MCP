"""Export AutoCAD session summaries into a RagBackend (separate from Inventor)."""

from __future__ import annotations

from typing import Any


def export_autocad_to_rag(backend: Any, rag: Any) -> dict[str, Any]:
    summary = backend.export_summary()
    if summary.get("error"):
        return summary
    rag.ingest_text(
        summary["doc_id"],
        summary["text"],
        source=summary.get("source") or summary["doc_id"],
    )
    return {
        "ok": True,
        "track": "autocad",
        "doc_id": summary["doc_id"],
        "source": summary.get("source"),
        "ingested_chars": len(summary["text"]),
        "mode": summary.get("mode"),
    }
