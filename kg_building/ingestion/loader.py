from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _load_pdf(path: Path) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    text = "\n\n".join(page.get_text("text") for page in doc)
    doc.close()
    return text


def load_papers(papers_dir: str | Path) -> dict[str, str]:
    papers_dir = Path(papers_dir)
    out: dict[str, str] = {}
    if not papers_dir.exists():
        log.warning("Papers directory does not exist: %s", papers_dir)
        return out
    for path in sorted(papers_dir.iterdir()):
        if path.suffix.lower() == ".pdf":
            try:
                out[path.name] = _load_pdf(path)
            except Exception as exc:
                log.error("Failed to load PDF %s: %s", path.name, exc)
        elif path.suffix.lower() in (".txt", ".md"):
            out[path.name] = path.read_text(encoding="utf-8", errors="ignore")
    return out
