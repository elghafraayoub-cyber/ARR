from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    papers_dir: str = os.getenv("PAPERS_DIR", "data/papers")
    output_dir: str = os.getenv("OUTPUT_DIR", "data/output")
    provider: str = os.getenv("PROVIDER", "vllm")
    model: str = os.getenv("MODEL", "")
    vllm_base_url: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    max_critic_rounds: int = int(os.getenv("MAX_CRITIC_ROUNDS", "3"))


settings = Settings()
