"""Caller identity and OAuth-scope checks.

`mock` mode treats every request as an operator holding every scope, so the platform runs locally with no identity
provider. `jwt` mode verifies a bearer token — HS256 with a shared secret, or RS256/ES256 against a JWKS URL (any
OIDC provider) — and reads scopes from the `scope` (space-separated) or `scp` (list) claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import settings

ALL_SCOPES = "*"
OPERATOR_SCOPE = "casepilot.operator"


@dataclass
class Principal:
    sub: str
    scopes: set[str] = field(default_factory=set)

    def has_scope(self, scope: str | None) -> bool:
        return scope is None or ALL_SCOPES in self.scopes or scope in self.scopes


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    assert settings.jwt_jwks_url
    return jwt.PyJWKClient(settings.jwt_jwks_url)


def decode_token(token: str) -> dict:
    options = {"verify_aud": settings.jwt_audience is not None}
    kwargs = {"audience": settings.jwt_audience, "issuer": settings.jwt_issuer, "options": options}
    if settings.jwt_jwks_url:
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256", "ES256"], **kwargs)
    if settings.jwt_secret:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], **kwargs)
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "jwt auth mode needs a secret or a JWKS URL")


def _scopes_from_claims(claims: dict) -> set[str]:
    raw = claims.get("scope") or claims.get("scp") or []
    return set(raw.split()) if isinstance(raw, str) else set(raw)


async def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    if settings.auth_mode == "mock":
        return Principal(sub="dev-operator", scopes={ALL_SCOPES})
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    return Principal(sub=str(claims.get("sub", "unknown")), scopes=_scopes_from_claims(claims))


def require_scope(scope: str):
    """Dependency factory: 403 unless the caller holds `scope`."""

    async def _check(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has_scope(scope):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing scope: {scope}")
        return principal

    return _check


require_operator = require_scope(OPERATOR_SCOPE)
