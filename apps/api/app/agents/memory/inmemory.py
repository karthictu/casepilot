from __future__ import annotations

import re
from collections import defaultdict


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


class InMemoryStore:
    """Process-local memory ranked by keyword overlap. Not persistent; for demos and tests."""

    def __init__(self) -> None:
        self._items: dict[str, list[str]] = defaultdict(list)

    async def add(self, text: str, *, user_id: str) -> None:
        if text not in self._items[user_id]:
            self._items[user_id].append(text)

    async def search(self, query: str, *, user_id: str, limit: int = 5) -> list[str]:
        q = _words(query)
        scored = sorted(self._items.get(user_id, []), key=lambda m: len(q & _words(m)), reverse=True)
        return scored[:limit]
