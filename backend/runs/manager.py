from __future__ import annotations

from sqlmodel import Session

from backend.db.models import Run
from backend.db.session import get_engine


def mark_checkpoint(run_id: str, stage: str) -> None:
    """Parses a stage label like 'round_2_extract' / 'round_2_critic' (see
    orchestrator.process_paper's on_checkpoint calls) to bump round_no and
    flip status to running."""
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = "running"
        try:
            run.round_no = int(stage.split("_")[1])
        except (IndexError, ValueError):
            pass
        session.add(run)
        session.commit()


def mark_running(run_id: str) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = "running"
        session.add(run)
        session.commit()


def mark_done(run_id: str) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = "done"
        session.add(run)
        session.commit()


def mark_failed(run_id: str, error: str) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = "failed"
        run.error = error[:2000]
        session.add(run)
        session.commit()
