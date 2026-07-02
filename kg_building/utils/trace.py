from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class TraceWriter:
    """
    Writes one JSON object per line to a trace file — every prompt sent to
    the LLM, every raw response, every tool call and its result, tagged with
    agent name / task id / paper source / step number.

    This is the file to open when something looks wrong in the graph: filter
    by task_id to replay exactly what that Worker/Critic call saw and did.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")
        log.info("Agent trace -> %s", self.path)

    def write(self, event: dict) -> None:
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        self._fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
