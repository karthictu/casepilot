"""Minimal stateless graph shim.

Agent graphs are stateless pure functions: input state in, merged output state out, no checkpointer. Durability
(waiting days for an approval, run-once writes) is Temporal's job, not the graph's. The topologies are tiny:

- a specialist is `loop_guard → node`;
- the pipeline is `loop_guard → classify → route → specialist`.

Nodes are `async def node(state) -> dict` returning only the keys they changed; the shim merges them. Anything
exposing `async ainvoke(state)` can stand in for a compiled graph, so a team can swap in LangGraph, an ADK
workflow, or plain code behind the same plugin contract.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class CompiledGraph:
    def __init__(self, run: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]):
        self._run = run

    async def ainvoke(self, state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._run(dict(state))


def guarded_single_node(loop_guard: NodeFn, node: NodeFn) -> CompiledGraph:
    """`loop_guard → node`: stop on a detected loop, else run the node."""

    async def _run(state: dict[str, Any]) -> dict[str, Any]:
        state.update(await loop_guard(state))
        if state.get("loop_detected"):
            return state
        state.update(await node(state))
        return state

    return CompiledGraph(_run)


def guarded_routed_pipeline(
    loop_guard: NodeFn,
    classify: NodeFn,
    route: Callable[[dict[str, Any]], str | None],
    specialists: Callable[[], dict[str, NodeFn]],
) -> CompiledGraph:
    """`loop_guard → classify → route → specialist`.

    `route(state)` returns a key of `specialists()`, or None to stop (HITL / nothing actionable). `specialists`
    is resolved per run so agents registered after the pipeline was built are still reachable.
    """

    async def _run(state: dict[str, Any]) -> dict[str, Any]:
        state.update(await loop_guard(state))
        if state.get("loop_detected"):
            return state
        state.update(await classify(state))
        target = route(state)
        nodes = specialists()
        if target and target in nodes:
            state.update(await nodes[target](state))
        return state

    return CompiledGraph(_run)
