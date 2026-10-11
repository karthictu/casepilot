"""Booking tools. Writes are gated: offered to the agent only in write-permitted sessions, and refused by the gate
otherwise. `scope` is the OAuth scope an external caller needs to see/call the tool over MCP."""

from __future__ import annotations

from typing import Any

from app.agents.tools import tool
from app.agents.types import OperationType
from app.integrations.booking_backend import get_booking_backend


@tool(
    "booking_create",
    "Create a new container booking.",
    operation_type=OperationType.WRITE,
    agent_scopes=["booking"],
    scope="booking.create",
)
async def booking_create(
    origin: str,
    destination: str,
    container_type: str,
    container_count: int,
    cargo_ready_date: str,
    commodity: str = "general cargo",
) -> dict[str, Any]:
    return await get_booking_backend().create(
        {
            "origin": origin,
            "destination": destination,
            "container_type": container_type,
            "container_count": int(container_count),
            "cargo_ready_date": cargo_ready_date,
            "commodity": commodity,
        }
    )


@tool(
    "booking_amend",
    "Amend fields of an existing booking. `changes` maps field name to new value.",
    operation_type=OperationType.WRITE,
    agent_scopes=["booking"],
    scope="booking.amend",
)
async def booking_amend(booking_ref: str, changes: dict) -> dict[str, Any]:
    return await get_booking_backend().amend(booking_ref, changes)


@tool(
    "booking_cancel",
    "Cancel an existing booking.",
    operation_type=OperationType.WRITE,
    agent_scopes=["booking"],
    scope="booking.cancel",
)
async def booking_cancel(booking_ref: str, reason: str = "") -> dict[str, Any]:
    return await get_booking_backend().cancel(booking_ref, reason)


@tool(
    "booking_status",
    "Get the current details and status of a booking.",
    operation_type=OperationType.READ,
    agent_scopes=["booking"],
    scope="booking.read",
)
async def booking_status(booking_ref: str) -> dict[str, Any]:
    return await get_booking_backend().get(booking_ref)
