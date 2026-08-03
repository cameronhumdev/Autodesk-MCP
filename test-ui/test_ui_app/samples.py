from __future__ import annotations

import re
from pathlib import Path

SAMPLES_PATH = Path(__file__).resolve().parent.parent / "SAMPLES.md"


def load_samples() -> list[dict]:
    """Parse SAMPLES.md into {id, title, prompt} for the UI."""
    if not SAMPLES_PATH.exists():
        return []
    text = SAMPLES_PATH.read_text(encoding="utf-8")
    samples: list[dict] = []
    # ## N. Title  then fenced ``` prompt ```
    pattern = re.compile(
        r"^##\s+(\d+)\.\s+(.+?)\s*$\n+```\s*\n(.*?)```",
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        samples.append(
            {
                "id": match.group(1),
                "title": match.group(2).strip(),
                "prompt": match.group(3).strip(),
            }
        )
    return samples


def raw_markdown() -> str:
    if not SAMPLES_PATH.exists():
        return "# No samples"
    return SAMPLES_PATH.read_text(encoding="utf-8")
