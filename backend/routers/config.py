from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigResponse(BaseModel):
    provider: str
    model: str
    vllm_base_url: str
    ollama_base_url: str
    max_critic_rounds: int


class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    vllm_base_url: str | None = None
    ollama_base_url: str | None = None
    max_critic_rounds: int | None = None


@router.get("", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    return ConfigResponse(
        provider=settings.provider,
        model=settings.model,
        vllm_base_url=settings.vllm_base_url,
        ollama_base_url=settings.ollama_base_url,
        max_critic_rounds=settings.max_critic_rounds,
    )


@router.put("", response_model=ConfigResponse)
def update_config(update: ConfigUpdate) -> ConfigResponse:
    """Updates in-memory defaults for this backend process. Per-run overrides
    (POST /api/runs body) always take precedence over these regardless."""
    if update.provider is not None:
        settings.provider = update.provider
    if update.model is not None:
        settings.model = update.model
    if update.vllm_base_url is not None:
        settings.vllm_base_url = update.vllm_base_url
        os.environ["VLLM_BASE_URL"] = update.vllm_base_url  # LLMClient reads this env var directly
    if update.ollama_base_url is not None:
        settings.ollama_base_url = update.ollama_base_url
        os.environ["OLLAMA_BASE_URL"] = update.ollama_base_url
    if update.max_critic_rounds is not None:
        settings.max_critic_rounds = update.max_critic_rounds
    return get_config()
