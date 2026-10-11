"""Customer memory: facts learned from past interactions, recalled into the orchestrator's prompt.

`inmemory` (default) is a keyword-overlap store for demos and tests; `mem0` uses Mem0 for semantic memory.
"""

from __future__ import annotations

from typing import Protocol

from app.config import settings


class MemoryStore(Protocol):
    async def add(self, text: str, *, user_id: str) -> None: ...

    async def search(self, query: str, *, user_id: str, limit: int = 5) -> list[str]: ...


_store: MemoryStore | None = None


def get_memory() -> MemoryStore:
    global _store
    if _store is None:
        if settings.memory_backend == "mem0":
            from app.agents.memory.mem0_store import Mem0Store

            _store = Mem0Store()
        else:
            from app.agents.memory.inmemory import InMemoryStore

            _store = InMemoryStore()
    return _store


def set_memory(store: MemoryStore | None) -> None:
    global _store
    _store = store


def format_for_prompt(memories: list[str]) -> str:
    if not memories:
        return ""
    return "Known facts about this customer (from earlier interactions):\n" + "\n".join(f"- {m}" for m in memories)
