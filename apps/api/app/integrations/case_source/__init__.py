from __future__ import annotations

from app.config import settings
from app.integrations.case_source.base import CaseSource, InboundCase

_source: CaseSource | None = None


def get_case_source() -> CaseSource:
    global _source
    if _source is None:
        if settings.case_source == "salesforce":
            from app.integrations.case_source.salesforce import SalesforceCaseSource

            _source = SalesforceCaseSource()
        else:
            from app.integrations.case_source.mock import MockCaseSource

            _source = MockCaseSource()
    return _source


def set_case_source(source: CaseSource | None) -> None:
    global _source
    _source = source


__all__ = ["CaseSource", "InboundCase", "get_case_source", "set_case_source"]
