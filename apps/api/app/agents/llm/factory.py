from __future__ import annotations

from app.agents.llm.base import LLMClient
from app.config import settings

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        if settings.llm_provider == "litellm":
            from app.agents.llm.litellm_client import LiteLLMClient

            _client = LiteLLMClient()
        else:
            from app.agents.llm.mock import MockLLM

            _client = MockLLM()
    return _client


def set_llm_client(client: LLMClient | None) -> None:
    """Override the client (tests, or wiring a custom provider). None resets to the configured one."""
    global _client
    _client = client
