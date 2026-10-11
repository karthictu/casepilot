"""Salesforce case source: OAuth 2.0 JWT bearer flow + a SOQL query over the standard `Case` object.

Configure a connected app with a certificate, then set `CASEPILOT_CASE_SOURCE=salesforce` and the
`CASEPILOT_SALESFORCE_*` variables. Only standard fields are read; map your org's custom fields in `_to_case`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.config import settings
from app.integrations.case_source.base import InboundCase

_FIELDS = "Id, Subject, Description, SuppliedEmail, Reason, CreatedDate"


class SalesforceCaseSource:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport  # injectable for tests
        self._token: dict[str, Any] | None = None

    def _assertion(self) -> str:
        if not (
            settings.salesforce_client_id and settings.salesforce_username and settings.salesforce_private_key_path
        ):
            raise RuntimeError("Salesforce case source needs client id, username and private key path")
        key = Path(settings.salesforce_private_key_path).read_text()
        claims = {
            "iss": settings.salesforce_client_id,
            "sub": settings.salesforce_username,
            "aud": settings.salesforce_login_url,
            "exp": int(time.time()) + 180,
        }
        return jwt.encode(claims, key, algorithm="RS256")

    async def _authenticate(self, client: httpx.AsyncClient) -> dict[str, Any]:
        if self._token is None:
            resp = await client.post(
                f"{settings.salesforce_login_url}/services/oauth2/token",
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": self._assertion()},
            )
            resp.raise_for_status()
            self._token = resp.json()
        return self._token

    def _soql(self, since: datetime | None, limit: int) -> str:
        where = []
        if since:
            # >= plus the caller's dedupe on external_id: a case created in the same second is never missed.
            where.append(f"CreatedDate >= {since.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}")
        if settings.salesforce_case_filter:
            where.append(f"({settings.salesforce_case_filter})")
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        return f"SELECT {_FIELDS} FROM Case{clause} ORDER BY CreatedDate ASC LIMIT {int(limit)}"

    @staticmethod
    def _to_case(record: dict[str, Any]) -> InboundCase:
        created = record.get("CreatedDate")
        return InboundCase(
            external_id=record["Id"],
            subject=record.get("Subject") or "",
            description=record.get("Description") or "",
            from_address=record.get("SuppliedEmail") or "",
            reason=(record.get("Reason") or "").strip().lower().replace(" ", "_"),
            created_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
        )

    async def fetch_new(self, *, since: datetime | None = None, limit: int = 100) -> list[InboundCase]:
        async with httpx.AsyncClient(transport=self._transport, timeout=30) as client:
            token = await self._authenticate(client)
            url = f"{token['instance_url']}/services/data/{settings.salesforce_api_version}/query"
            headers = {"Authorization": f"Bearer {token['access_token']}"}
            resp = await client.get(url, params={"q": self._soql(since, limit)}, headers=headers)
            resp.raise_for_status()
            return [self._to_case(r) for r in resp.json().get("records", [])]
