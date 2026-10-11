from __future__ import annotations

from collections.abc import Awaitable

from fastapi import HTTPException

from app.services.errors import Conflict, Invalid, NotFound


async def translate[T](coro: Awaitable[T]) -> T:
    """Map service errors onto HTTP status codes."""
    try:
        return await coro
    except NotFound as e:
        raise HTTPException(404, str(e)) from e
    except Conflict as e:
        raise HTTPException(409, str(e)) from e
    except Invalid as e:
        raise HTTPException(422, str(e)) from e
