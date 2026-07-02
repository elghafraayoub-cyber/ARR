from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.db.models import Entity, Finding
from backend.db.session import get_session

router = APIRouter(prefix="/api/runs/{run_id}", tags=["graph"])


@router.get("/entities", response_model=list[Entity])
def list_entities(
    run_id: str,
    entity_type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    stmt = select(Entity).where(Entity.run_id == run_id)
    if entity_type:
        stmt = stmt.where(Entity.entity_type == entity_type)
    if q:
        stmt = stmt.where(Entity.name.contains(q))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return session.exec(stmt).all()


@router.get("/findings", response_model=list[Finding])
def list_findings(
    run_id: str,
    relation_type: str | None = None,
    flagged: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    stmt = select(Finding).where(Finding.run_id == run_id)
    if relation_type:
        stmt = stmt.where(Finding.relation_type == relation_type)
    if flagged is not None:
        stmt = stmt.where(Finding.has_flags == flagged)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return session.exec(stmt).all()
