from __future__ import annotations

import json
import re
from pathlib import Path

from rag.adapter import RagHit

DATA_DIR = Path(__file__).resolve().parent / "data"


class LocalRagBackend:
    name = "local"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "index.json"
        self._docs: dict[str, dict] = {}
        self._load()
        self._ensure_product_docs()

    def _load(self) -> None:
        if self.index_path.exists():
            self._docs = json.loads(self.index_path.read_text(encoding="utf-8"))
        else:
            self._seed()

    def _save(self) -> None:
        self.index_path.write_text(json.dumps(self._docs, indent=2), encoding="utf-8")

    def _seed(self) -> None:
        self.ingest_text(
            "flange-standard",
            "Company flange standard: minimum thickness is 8 mm for DN50. "
            "Use stainless 316 for corrosive duty. Always add M16 tapped holes "
            "on a 100 mm PCD unless the drawing note says otherwise.",
            source="seed/flange-standard.txt",
        )
        self.ingest_text(
            "layer-standard",
            "AutoCAD layer standard: WALLS=red, DOORS=yellow, DIMS=cyan, "
            "TEXT=white. Title block lives on layer TITLE. Do not draw "
            "dimensions on WALLS.",
            source="seed/layer-standard.txt",
        )
        self._save()

    def _ensure_product_docs(self) -> None:
        """Docs that should exist even on older local indexes."""
        if "cad-tracks" in self._docs:
            return
        self.ingest_text(
            "cad-tracks",
            "Autodesk-MCP supports two separate CAD modes: Inventor and AutoCAD. "
            "They are not one combined CAD tool. The UI has an Inventor / AutoCAD toggle. "
            "The assistant may call request_track_switch to ask permission to change mode; "
            "the user must Confirm or Cancel. Never claim the product only supports Inventor "
            "or only AutoCAD.",
            source="seed/cad-tracks.txt",
        )

    def ingest_text(self, doc_id: str, text: str, source: str = "") -> None:
        self._docs[doc_id] = {"text": text.strip(), "source": source or doc_id}
        self._save()

    def search(self, query: str, top_k: int = 4) -> list[RagHit]:
        tokens = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
        scored: list[RagHit] = []
        for doc_id, doc in self._docs.items():
            text = doc["text"]
            lower = text.lower()
            score = sum(1.0 for t in tokens if t in lower)
            if score > 0:
                scored.append(
                    RagHit(source=doc.get("source", doc_id), text=text, score=score)
                )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def status(self) -> dict:
        return {
            "backend": self.name,
            "documents": len(self._docs),
            "data_dir": str(self.data_dir),
        }
