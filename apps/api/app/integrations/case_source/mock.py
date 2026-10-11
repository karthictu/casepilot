"""Mock case source: serves the synthetic cases in `app/seeds/sample_cases.json`."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.integrations.case_source.base import InboundCase

SEED_FILE = Path(__file__).resolve().parents[2] / "seeds" / "sample_cases.json"


class MockCaseSource:
    def __init__(self, path: Path = SEED_FILE) -> None:
        self._path = path

    async def fetch_new(self, *, since: datetime | None = None, limit: int = 100) -> list[InboundCase]:
        rows = json.loads(self._path.read_text())
        cases = [InboundCase(**row) for row in rows]
        return cases[:limit]
