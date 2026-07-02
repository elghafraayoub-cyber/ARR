from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlmodel import Session

from backend.config import settings
from backend.db.models import Run
from backend.db.session import get_engine
from backend.db.sync import sync_run
from backend.runs import manager
from kg_building.agents.orchestrator import process_paper
from kg_building.graph.storage import KGStorage
from kg_building.ingestion.loader import load_papers
from kg_building.llm.client import LLMClient

log = logging.getLogger(__name__)


def create_run(
    paper_source: str,
    provider: str | None = None,
    model: str | None = None,
    max_critic_rounds: int | None = None,
) -> Run:
    """Creates the Run row (status=queued) and its dedicated output paths.
    Each run gets its own kg_path/trace_dir so entity/finding stats stay
    scoped to this one run rather than accumulating across runs."""
    run_id = uuid.uuid4().hex[:12]
    run_dir = Path(settings.output_dir) / "runs" / run_id
    kg_path = run_dir / "soil_kg.json"
    trace_dir = run_dir / "traces"

    run = Run(
        id=run_id,
        paper_source=paper_source,
        status="queued",
        provider=provider or settings.provider,
        model=model or settings.model,
        max_critic_rounds=max_critic_rounds or settings.max_critic_rounds,
        kg_path=str(kg_path),
        trace_path=str(trace_dir / f"{paper_source}.jsonl"),
    )
    with Session(get_engine()) as session:
        session.add(run)
        session.commit()
        session.refresh(run)
    return run


def execute_run(run_id: str) -> None:
    """Runs the extraction pipeline for one paper. Meant to be invoked via
    FastAPI BackgroundTasks — a single local user and minutes-long jobs don't
    justify a broker/worker fleet (Celery/Redis)."""
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            log.error("execute_run: no such run_id %s", run_id)
            return
        paper_source, provider, model = run.paper_source, run.provider, run.model
        max_critic_rounds, kg_path = run.max_critic_rounds, run.kg_path
        trace_dir = Path(run.trace_path).parent

    manager.mark_running(run_id)
    try:
        papers = load_papers(settings.papers_dir)
        if paper_source not in papers:
            raise FileNotFoundError(f"'{paper_source}' not found in {settings.papers_dir}")
        text = papers[paper_source]

        client = LLMClient(provider=provider, model=model)
        storage = KGStorage(kg_path=kg_path, provider=provider, model=model)

        def on_checkpoint(storage: KGStorage, stage: str) -> None:
            with Session(get_engine()) as sync_session:
                sync_run(sync_session, run_id, storage)
            manager.mark_checkpoint(run_id, stage)

        process_paper(
            client, storage, paper_source, text,
            max_critic_rounds=max_critic_rounds, trace_dir=trace_dir,
            on_checkpoint=on_checkpoint,
        )

        with Session(get_engine()) as session:
            sync_run(session, run_id, storage)
        manager.mark_done(run_id)

    except Exception as exc:
        log.exception("Run %s failed", run_id)
        manager.mark_failed(run_id, str(exc))
