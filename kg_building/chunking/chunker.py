from __future__ import annotations

import re
from dataclasses import dataclass, asdict

_SECTION_PATTERNS = [
    (r"^\s*abstract\b", "abstract"),
    (r"^\s*(introduction|background)\b", "introduction"),
    (r"^\s*(materials?\s+and\s+methods|methods|study\s+site|site\s+description)\b", "methods"),
    (r"^\s*results?\b", "results"),
    (r"^\s*(discussion|results\s+and\s+discussion)\b", "discussion"),
    (r"^\s*(conclusion|conclusions|summary)\b", "conclusion"),
    (r"^\s*(references|literature\s+cited|bibliography)\b", "references"),
]

CHUNK_MIN = 800
CHUNK_MAX = 6000
CHUNK_TARGET = 2500


@dataclass
class ChunkItem:
    chunk_id: str
    text: str
    char_start: int
    char_end: int
    section_hint: str

    def to_dict(self) -> dict:
        return asdict(self)


def _detect_section(line: str, current: str) -> str:
    stripped = line.strip().lower()
    if len(stripped) > 80:
        return current
    for pattern, label in _SECTION_PATTERNS:
        if re.match(pattern, stripped):
            return label
    return current


def chunk(text: str, paper_source: str) -> list[ChunkItem]:
    """
    Section-aware chunking: splits on paragraph breaks, tags each paragraph
    with the most recent detected section header, then packs paragraphs into
    chunks of CHUNK_MIN..CHUNK_MAX chars (target ~CHUNK_TARGET), never
    crossing a section boundary if avoidable.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    tagged: list[tuple[str, str]] = []
    current_section = "preamble"
    for para in paragraphs:
        if not para.strip():
            continue
        first_line = para.strip().splitlines()[0] if para.strip() else ""
        current_section = _detect_section(first_line, current_section)
        if current_section == "references":
            break  # stop at references — no extraction value, saves tokens
        tagged.append((para.strip(), current_section))

    chunks: list[ChunkItem] = []
    buf: list[str] = []
    buf_section = tagged[0][1] if tagged else "body"
    buf_len = 0
    char_cursor = 0
    n = 0

    def flush():
        nonlocal buf, buf_len, n, char_cursor
        if not buf:
            return
        joined = "\n\n".join(buf)
        chunks.append(ChunkItem(
            chunk_id=f"{paper_source}_chunk_{n:03d}",
            text=joined,
            char_start=char_cursor,
            char_end=char_cursor + len(joined),
            section_hint=buf_section,
        ))
        char_cursor += len(joined) + 2
        n += 1
        buf = []
        buf_len = 0

    for para, section in tagged:
        if section != buf_section and buf_len >= CHUNK_MIN:
            flush()
            buf_section = section
        elif section != buf_section and not buf:
            buf_section = section

        buf.append(para)
        buf_len += len(para)

        if buf_len >= CHUNK_TARGET:
            flush()
            buf_section = section

    flush()

    # merge any final tiny trailing chunk into the previous one
    if len(chunks) >= 2 and len(chunks[-1].text) < CHUNK_MIN // 2:
        last = chunks.pop()
        prev = chunks[-1]
        merged_text = prev.text + "\n\n" + last.text
        chunks[-1] = ChunkItem(
            chunk_id=prev.chunk_id, text=merged_text,
            char_start=prev.char_start, char_end=prev.char_start + len(merged_text),
            section_hint=prev.section_hint,
        )

    if not chunks and text.strip():
        chunks.append(ChunkItem(f"{paper_source}_chunk_000", text.strip(), 0, len(text), "body"))

    return chunks
