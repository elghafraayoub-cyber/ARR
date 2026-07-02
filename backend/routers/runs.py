from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db.models import Run
from backend.db.session import get_session
from backend.runs import service
from backend.runs.trace_view import tail_trace_lines

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    paper_source: str
    provider: str | None = None
    model: str | None = None
    max_critic_rounds: int | None = None


@router.post("", response_model=Run)
def start_run(req: CreateRunRequest, background_tasks: BackgroundTasks):
    run = service.create_run(
        paper_source=req.paper_source,
        provider=req.provider,
        model=req.model,
        max_critic_rounds=req.max_critic_rounds,
    )
    background_tasks.add_task(service.execute_run, run.id)
    return run


@router.get("", response_model=list[Run])
def list_runs(session: Session = Depends(get_session)):
    return session.exec(select(Run).order_by(Run.created_at.desc())).all()


@router.get("/{run_id}", response_model=Run)
def get_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/status")
def get_run_status(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    # Small file, negligible cost at a 1.5s poll interval — this is the
    # "Explainability Panel" analog: live agent reasoning/tool-call lines,
    # via polling the existing trace JSONL instead of a websocket/event bus.
    return {**run.model_dump(), "log_lines": tail_trace_lines(run.trace_path)}
