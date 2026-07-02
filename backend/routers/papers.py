from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, UploadFile

from backend.config import settings

router = APIRouter(prefix="/api/papers", tags=["papers"])

_ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


@router.get("")
def list_papers() -> list[str]:
    papers_dir = Path(settings.papers_dir)
    if not papers_dir.exists():
        return []
    return sorted(p.name for p in papers_dir.iterdir() if p.suffix.lower() in _ALLOWED_SUFFIXES)


@router.post("/upload")
async def upload_paper(file: UploadFile) -> dict:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        return {"error": f"Unsupported file type '{suffix}'. Use .pdf, .txt, or .md."}

    papers_dir = Path(settings.papers_dir)
    papers_dir.mkdir(parents=True, exist_ok=True)
    dest = papers_dir / file.filename
    dest.write_bytes(await file.read())
    return {"paper_source": file.filename}
