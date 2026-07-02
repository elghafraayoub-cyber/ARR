from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

_COLORS = {
    "DEBUG": "\033[90m", "INFO": "\033[36m", "WARNING": "\033[33m",
    "ERROR": "\033[31m", "CRITICAL": "\033[41m",
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        msg = super().format(record)
        return f"{color}{msg}{_RESET}" if color else msg


def setup_logging(level: str = "INFO", log_dir: str | Path = "data/output") -> Path:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(_ColorFormatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%H:%M:%S"))
    root.addHandler(console)

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fileh = logging.FileHandler(log_path, encoding="utf-8")
    fileh.setLevel(logging.DEBUG)
    fileh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    root.addHandler(fileh)

    return log_path
