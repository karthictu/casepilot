"""Tracking tools (read-only)."""

from __future__ import annotations

from typing import Any

from app.agents.tools import tool
from app.integrations.tracking_backend import get_tracking_backend


@tool(
    "tracking_get_milestones",
    "Get the event milestones and ETA for a shipment or booking reference.",
    agent_scopes=["tracking"],
    scope="tracking.read",
)
async def tracking_get_milestones(shipment_ref: str) -> dict[str, Any]:
    return await get_tracking_backend().milestones(shipment_ref)


@tool(
    "tracking_get_eta",
    "Get the current estimated time of arrival for a shipment.",
    agent_scopes=["tracking"],
    scope="tracking.read",
)
async def tracking_get_eta(shipment_ref: str) -> dict[str, Any]:
    return await get_tracking_backend().eta(shipment_ref)
