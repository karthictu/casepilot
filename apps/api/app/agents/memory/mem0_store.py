"""Mem0-backed memory (`CASEPILOT_MEMORY_BACKEND=mem0`, extra: `mem0`).

`CASEPILOT_MEM0_CONFIG_JSON` is passed to `AsyncMemory.from_config`, e.g. a pgvector vector store and your own
embedding/LLM provider. Empty uses Mem0's defaults (which call OpenAI).
"""

from __future__ import annotations

import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class Mem0Store:
    def __init__(self) -> None:
        from mem0 import AsyncMemory

        config = json.loads(settings.mem0_config_json) if settings.mem0_config_json else None
        self._memory = AsyncMemory.from_config(config) if config else AsyncMemory()

    async def add(self, text: str, *, user_id: str) -> None:
        await self._memory.add(text, user_id=user_id)

    async def search(self, query: str, *, user_id: str, limit: int = 5) -> list[str]:
        try:
            found = await self._memory.search(query, filters={"user_id": user_id}, top_k=limit)
        except Exception:  # memory is best-effort; never fail a request on it
            logger.exception("mem0 search failed")
            return []
        results = found.get("results", found) if isinstance(found, dict) else found
        return [r.get("memory", "") for r in results if isinstance(r, dict) and r.get("memory")]
