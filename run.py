from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from kg_building.agents.orchestrator import process_paper
from kg_building.graph.storage import KGStorage
from kg_building.ingestion.loader import load_papers
from kg_building.llm.client import LLMClient
from kg_building.utils.logging_config import setup_logging

log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Agentic soil-health knowledge graph builder")
    p.add_argument("--papers", default=os.getenv("PAPERS_DIR", "data/papers"))
    p.add_argument("--provider", default=os.getenv("PROVIDER", "vllm"), choices=["ollama", "vllm"])
    p.add_argument("--model", default=os.getenv("MODEL", ""))
    p.add_argument("--kg", default=os.getenv("KG_PATH", "data/output/soil_kg.json"))
    p.add_argument("--max-critic-rounds", type=int, default=int(os.getenv("MAX_CRITIC_ROUNDS", "3")))
    p.add_argument("--visualize", action="store_true")
    p.add_argument("--eval", action="store_true")
    p.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    p.add_argument("--log-dir", default=os.getenv("OUTPUT_DIR", "data/output"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    log_path = setup_logging(args.log_level, args.log_dir)
    log.info("Logging to %s", log_path)

    if not args.model:
        log.error("No --model / MODEL env set. Aborting.")
        return

    papers = load_papers(args.papers)
    if not papers:
        log.error("No papers found in %s (.pdf or .txt). Add files and re-run.", args.papers)
        return
    log.info("Loaded %d paper(s): %s", len(papers), list(papers.keys()))

    client = LLMClient(provider=args.provider, model=args.model)
    storage = KGStorage(kg_path=args.kg, provider=args.provider, model=args.model)

    t0 = time.perf_counter()
    trace_dir = Path(args.log_dir) / "traces"
    for paper_source, text in papers.items():
        process_paper(client, storage, paper_source, text,
                       max_critic_rounds=args.max_critic_rounds, trace_dir=trace_dir)

    stats = storage.stats()
    elapsed = time.perf_counter() - t0
    log.info("=" * 60)
    log.info("Knowledge graph complete")
    log.info("  Entities  : %d", stats["entities"])
    log.info("  Findings  : %d", stats["findings"])
    log.info("  Papers    : %d", stats["papers"])
    log.info("  Missing conditions: %d", stats["findings_missing_conditions"])
    log.info("  Saved to  : %s", args.kg)
    log.info("  Traces in : %s", trace_dir)
    log.info("  Total time: %.1fs", elapsed)
    log.info("=" * 60)

    if args.visualize and stats["entities"] > 0:
        from kg_building.visualization.visualizer import build_html
        viz_path = Path(args.kg).parent / "soil_kg.html"
        build_html(args.kg, viz_path)

    if args.eval:
        from kg_building.eval.check import run as run_eval
        run_eval(args.kg)

    log.info("Done.")


if __name__ == "__main__":
    main()
