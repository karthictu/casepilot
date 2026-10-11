"""Agent plugin contract: the shared interface for every domain (specialist) agent.

Each agent module builds an `AgentPlugin` and calls `registry.register(plugin)` at import time. The pipeline and
the orchestrator discover agents through the registry, so adding an agent never touches `graphs/pipeline.py`.
List the module in `CASEPILOT_AGENT_MODULES` and it is loaded at startup (`load_plugins`).

See docs/agent-plugin-contract.md for the full guide.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentPlugin:
    """Self-contained description of a domain agent. Teams own this object; the framework owns routing.

    agent_id         Stable lowercase slug. The orchestrator's `route_to` value and the pipeline node name.
    display_name     Label for the admin UI and the A2A agent card.
    description      One sentence, surfaced in `/.well-known/agent.json`.
    version          Semver, logged with every audit event so decisions are replayable against a version.
    owner_team       Owning team slug, for escalations.
    intents          Intents this agent handles. The orchestrator's routing table is built from these.
    scopes           OAuth scopes its tools require; advertised on the agent card. (MCP filters `tools/list` by each
                     tool's own `scope`.)
    graph_factory    Returns the compiled agent graph (anything with `async ainvoke(state) -> state`). Called once.
    write_capable    True if the agent can mutate external state.
    requires_hitl    True if its writes are HITL-gated.
    hitl_confidence_threshold
                     Confidence below which the request is escalated to the operator queue.
    """

    agent_id: str
    display_name: str
    description: str
    version: str
    owner_team: str
    intents: list[str]
    scopes: list[str]
    graph_factory: Callable[[], Any]
    write_capable: bool = False
    requires_hitl: bool = False
    hitl_confidence_threshold: float = 0.85
    metadata: dict[str, Any] = field(default_factory=dict)
    _graph: Any = field(default=None, init=False, repr=False)

    @property
    def graph(self) -> Any:
        if self._graph is None:
            self._graph = self.graph_factory()
        return self._graph

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "owner_team": self.owner_team,
            "intents": self.intents,
            "scopes": self.scopes,
            "write_capable": self.write_capable,
            "requires_hitl": self.requires_hitl,
            "hitl_confidence_threshold": self.hitl_confidence_threshold,
        }


class AgentRegistry:
    """In-process registry of AgentPlugins. Registrations happen at import time, before the first request."""

    def __init__(self) -> None:
        self._plugins: dict[str, AgentPlugin] = {}

    def register(self, plugin: AgentPlugin) -> None:
        if plugin.agent_id in self._plugins:
            logger.warning(
                "AgentRegistry: '%s' already registered; replacing with v%s", plugin.agent_id, plugin.version
            )
        self._plugins[plugin.agent_id] = plugin
        logger.info("AgentRegistry: registered '%s' v%s, intents=%s", plugin.agent_id, plugin.version, plugin.intents)

    def unregister(self, agent_id: str) -> None:
        self._plugins.pop(agent_id, None)

    def get(self, agent_id: str) -> AgentPlugin | None:
        return self._plugins.get(agent_id)

    def list(self) -> list[AgentPlugin]:
        return list(self._plugins.values())

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self._plugins

    def routing_table(self) -> dict[str, str]:
        """{intent: agent_id}. When two agents claim an intent, the later registration wins (and is logged)."""
        table: dict[str, str] = {}
        for plugin in self._plugins.values():
            for intent in plugin.intents:
                if intent in table:
                    logger.warning("Intent '%s' claimed by '%s' and '%s'", intent, table[intent], plugin.agent_id)
                table[intent] = plugin.agent_id
        return table

    def __repr__(self) -> str:
        return f"AgentRegistry({list(self._plugins)})"


registry = AgentRegistry()


def load_plugins(modules: list[str] | None = None) -> AgentRegistry:
    """Import each agent module so it self-registers. Idempotent."""
    from app.config import settings

    for module in modules or settings.agent_modules:
        importlib.import_module(module)
    return registry
