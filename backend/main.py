from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.routers import config, graph, papers, runs


def create_app() -> FastAPI:
    app = FastAPI(title="Soil KG Builder")

    app.include_router(runs.router)
    app.include_router(graph.router)
    app.include_router(papers.router)
    app.include_router(config.router)

    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
