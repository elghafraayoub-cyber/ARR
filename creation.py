from __future__ import annotations

import sys
from pathlib import Path


def create_project_structure(target_dir: Path) -> None:
    """Create the soil_kg_agentic project structure with the listed folders and files."""
    if target_dir.exists():
        raise FileExistsError(f"Target directory already exists: {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)

    folders = [
        "src",
        "src/agents",
        "src/chunking",
        "src/eval",
        "src/extraction",
        "src/graph",
        "src/ingestion",
        "src/llm",
        "src/utils",
        "src/visualization",
        "data",
        "data/papers",
        "data/output",
        "docs",
        "prompts",
        "output",
    ]

    files = [
        "README.md",
        "GUIDE.md",
        "pyproject.toml",
        "run.py",
        "src/__init__.py",
        "src/agents/__init__.py",
        "src/agents/critic.py",
        "src/agents/orchestrator.py",
        "src/agents/planner.py",
        "src/agents/session.py",
        "src/agents/tools.py",
        "src/agents/worker.py",
        "src/chunking/__init__.py",
        "src/chunking/chunker.py",
        "src/eval/__init__.py",
        "src/eval/check.py",
        "src/extraction/__init__.py",
        "src/extraction/types.py",
        "src/graph/__init__.py",
        "src/graph/dedup.py",
        "src/graph/storage.py",
        "src/ingestion/__init__.py",
        "src/ingestion/loader.py",
        "src/llm/__init__.py",
        "src/llm/client.py",
        "src/utils/__init__.py",
        "src/utils/logging_config.py",
        "src/utils/replay_trace.py",
        "src/utils/trace.py",
        "src/visualization/__init__.py",
        "src/visualization/visualizer.py",
    ]

    for folder in folders:
        (target_dir / folder).mkdir(parents=True, exist_ok=True)

    for file in files:
        (target_dir / file).parent.mkdir(parents=True, exist_ok=True)
        (target_dir / file).touch()


if __name__ == "__main__":
    requested_name = sys.argv[1] if len(sys.argv) > 1 else "soil_kg_agentic"
    target_path = Path(requested_name).expanduser()

    if not target_path.is_absolute():
        target_path = (Path.cwd() / target_path).resolve()

    create_project_structure(target_path)
    print(f"Created project structure at: {target_path}")
