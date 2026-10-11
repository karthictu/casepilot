# Agent plugin contract
*how-to · last updated 2026-10-09*

## Purpose
How to add a specialist agent to casepilot without touching the pipeline, for teams who own a domain (documents,
customs, invoicing, ...) and want their agent reachable over A2A, chat and MCP.

## TL;DR
- An agent is an `AgentPlugin` (`app/agents/plugin.py`) registered at import time with `registry.register(...)`.
- List its module in `CASEPILOT_AGENT_MODULES`; `load_plugins()` imports it at startup.
- The registry drives everything else: the orchestrator's intent list and routing table, the pipeline's
  specialist nodes, the A2A agent card skills, `GET /api/agents` and the admin's Agents & Tools page.
- Give it tools with `@tool(agent_scopes=["<agent_id>"], scope="<oauth scope>")`, a `@mock_script("<agent_id>")`
  so it runs offline, and a test.
- The case-driven path is booking-only by design; a new agent is reachable over A2A, chat (via the orchestrator)
  and MCP (via its tools).

## The contract

```python
@dataclass
class AgentPlugin:
    agent_id: str                  # stable slug: route_to value, pipeline node name, A2A skill id
    display_name: str              # admin UI + agent card
    description: str               # one sentence; goes into the orchestrator prompt and the agent card
    version: str                   # semver
    owner_team: str                # escalation owner
    intents: list[str]             # intents it handles → registry.routing_table()
    scopes: list[str]              # OAuth scopes its tools use (descriptive; MCP enforces each tool's own `scope`)
    graph_factory: Callable[[], Any]  # returns anything with `async ainvoke(state) -> state`; called once, lazily
    write_capable: bool = False
    requires_hitl: bool = False
    hitl_confidence_threshold: float = 0.85  # pipeline escalates below this orchestrator confidence
    metadata: dict[str, Any] = {}
```

| What reads it | How |
|---|---|
| Orchestrator (`app/agents/orchestrator.py`) | `build_prompt()` lists every plugin's intents with its display name and description; the model picks an intent, the code maps it to `agent_id` via `registry.routing_table()`. An intent nobody owns becomes `unknown` → `hitl`. |
| Pipeline (`app/agents/graphs/pipeline.py`) | `specialists()` returns `{agent_id: plugin.graph.ainvoke}` per run, so a plugin registered after startup is still reachable. `classify_node` escalates when confidence is below the plugin's `hitl_confidence_threshold`. |
| A2A (`app/routers/a2a.py`) | One skill per plugin in `/.well-known/agent.json`, `tags` = intents |
| `GET /api/agents` | `[plugin.to_dict() for plugin in registry.list()]` (every field except `graph_factory` and `metadata`) |
| Routing conflicts | When two plugins claim an intent, the later registration wins and a warning is logged |

### The graph

`graph_factory` must return an object with `async ainvoke(state: dict) -> dict`. The bundled agents use the
shim in `app/agents/graphs/mini.py`: `guarded_single_node(loop_guard_node, node)` runs the loop guard, then
your node, and merges the returned keys into the state. A node reads `query`, `customer_id`, `history`,
`write_allowed` and `model_override` from the state (`app/agents/graphs/state.py:AgentState`) and returns:

| Key | Meaning |
|---|---|
| `agent_id` | Your `agent_id` (the chat shows it as a step) |
| `decision` | Your structured result (any JSON) |
| `response_text` | What A2A and chat show the caller |
| `hitl_required`, `hitl_reason` | Escalate to the operator queue |
| `proposed_call` | `{"tool", "arguments"}` an operator can approve (write-capable agents only) |
| `**accumulate(state, result)` | Cost, tokens, `tool_calls` (streamed to chat, audited) and `recent_tool_calls` (loop guard) |

You can swap the shim for LangGraph, an ADK workflow or plain code: anything with `ainvoke` works.

### Rules

1. **Call the model through `run_agent`** (`app/agents/runtime/engine.py`), never a provider SDK directly. That
   gives you the configured runtime (native or ADK), the gate, guardrails, loop guard, cost cap and tracing.
2. **Never seed `write_allowed` from model output.** Pass the state's `write_allowed` into `SessionContext`, or
   leave it `False` for a read-only agent.
3. **Scope every tool** with `agent_scopes=[AGENT_ID]`. An empty `agent_scopes` offers the tool to every agent.
4. **Decide in code what you can.** Like `booking.enforce_invariants` and `extraction.finalize`, don't trust a
   model's claim of success or completeness when the run's tool calls can prove it.
5. **New modules that open DB sessions** use `app.database` (`get_db` in routers, `session_scope()` elsewhere), so
   the test suite's SQLite engine applies to them.

## Worked example: a read-only documents agent

A hypothetical `documents` agent that answers "is the bill of lading for BK-100001 ready?". It is read-only, has
one tool, runs offline on the mock LLM, and is tested. The code below was run against the test suite before it
was written down.

### 1. The tool: `app/agents/documents_tools.py`

```python
"""Document tools (read-only)."""

from __future__ import annotations

from typing import Any

from app.agents.tools import tool

# Stand-in data. In a real deployment this calls a DocumentBackend adapter (see docs/integrations.md).
_DOCUMENTS: dict[str, dict[str, Any]] = {
    "BK-100001": {"bill_of_lading": "issued", "commercial_invoice": "received", "packing_list": "missing"},
}


@tool(
    "documents_get_status",
    "Get the status of the shipping documents (bill of lading, invoice, packing list) for a booking.",
    agent_scopes=["documents"],
    scope="documents.read",
)
async def documents_get_status(booking_ref: str) -> dict[str, Any]:
    docs = _DOCUMENTS.get(booking_ref.upper())
    return {"booking_ref": booking_ref.upper(), "documents": docs or {}, "found": docs is not None}
```

### 2. The agent, its mock script and its plugin: `app/agents/documents.py`

```python
"""Documents agent: read-only status of a booking's shipping documents."""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents import documents_tools  # noqa: F401 — registers the tool
from app.agents._json import coerce_to_dict
from app.agents.graphs.loop_guard import loop_guard_node
from app.agents.graphs.mini import guarded_single_node
from app.agents.graphs.nodes import accumulate, clamp_confidence
from app.agents.graphs.state import AgentState
from app.agents.llm.base import LLMResponse, LLMToolCall
from app.agents.llm.mock import mock_script
from app.agents.plugin import AgentPlugin, registry
from app.agents.runtime.engine import run_agent
from app.agents.types import AgentConfig, SessionContext
from app.config import settings

AGENT_ID = "documents"

SYSTEM_PROMPT = """You are the shipping-documents agent for a container shipping desk. Report which documents
(bill of lading, commercial invoice, packing list) exist for a booking, using only your tools.
Return exactly one JSON object and nothing else:
{"outcome": "<answered|not_found|hitl_required>", "booking_ref": "<ref or null>",
 "summary": "<one sentence for the customer>", "confidence": <0.0-1.0>}"""


# ── Mock script: what the offline mock LLM answers for this agent ────────────
_REF_RE = re.compile(r"\b(BK-\d{6})\b", re.I)


def _final(outcome: str, confidence: float, booking_ref: str | None, summary: str) -> LLMResponse:
    payload = {"outcome": outcome, "confidence": confidence, "booking_ref": booking_ref, "summary": summary}
    return LLMResponse(content=json.dumps(payload))


@mock_script(AGENT_ID)
def documents_mock(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
    user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    results = [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]
    if not (ref := _REF_RE.search(user or "")):
        return _final("hitl_required", 0.4, None, "I need a booking reference such as BK-100001.")
    if not results:  # first turn: call the tool
        args = {"booking_ref": ref.group(1).upper()}
        return LLMResponse(tool_calls=[LLMToolCall(id="call_docs", name="documents_get_status", arguments=args)])
    last = results[-1]
    if not last.get("found"):
        return _final("not_found", 0.9, last.get("booking_ref"), f"No documents on file for {last.get('booking_ref')}.")
    listed = ", ".join(f"{name.replace('_', ' ')}: {state}" for name, state in last["documents"].items())
    return _final("answered", 0.92, last["booking_ref"], f"{last['booking_ref']}: {listed}.")


# ── Graph node ───────────────────────────────────────────────────────────────
async def documents_node(state: AgentState) -> dict[str, Any]:
    config = AgentConfig(
        name=AGENT_ID, model=state.get("model_override") or settings.model_reasoning, system_prompt=SYSTEM_PROMPT
    )
    result = await run_agent(
        config,
        [*(state.get("history") or []), {"role": "user", "content": state["query"]}],
        SessionContext(customer_id=state.get("customer_id")),  # read-only: write_allowed stays False
    )
    decision = coerce_to_dict(result.output)
    decision["confidence"] = clamp_confidence(decision.get("confidence", 0.0))
    decision.setdefault("outcome", "hitl_required" if result.error else "answered")
    hitl_required = (
        decision["outcome"] == "hitl_required" or decision["confidence"] < settings.hitl_confidence_threshold
    )
    updates: dict[str, Any] = {
        "agent_id": AGENT_ID,
        "decision": decision,
        "hitl_required": hitl_required,
        "response_text": decision.get("summary") or result.error or "",
        **accumulate(state, result),
    }
    if hitl_required:
        updates["hitl_reason"] = decision.get("summary") or "Documents answer needs operator review"
    return updates


documents_graph = guarded_single_node(loop_guard_node, documents_node)

PLUGIN = AgentPlugin(
    agent_id=AGENT_ID,
    display_name="Documents Agent",
    description="Read-only status of a booking's shipping documents.",
    version="0.1.0",
    owner_team="documentation",
    intents=["get_document_status"],
    scopes=["documents.read"],
    graph_factory=lambda: documents_graph,
)
registry.register(PLUGIN)
```

The mock script is what `MockLLM` answers when `agent_name == "documents"`. It behaves like a well-behaved model:
calls the tool when it is offered, then answers from the result. Register it in your module (as here); the
built-in scripts live in `app/agents/llm/mock_scripts.py`.

### 3. Register the module

```bash
# .env (a JSON list; keep the bundled agents)
CASEPILOT_AGENT_MODULES=["app.agents.booking","app.agents.tracking","app.agents.documents"]
```

Or change the default `agent_modules` in `app/config.py` if the agent ships with your build. After a restart:

```bash
curl -s http://localhost:8000/api/agents | jq '.items[].agent_id'          # "booking" "tracking" "documents"
curl -s http://localhost:8000/.well-known/agent.json | jq '.skills[].id'
curl -s -X POST http://localhost:8000/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"documents_get_status","arguments":{"booking_ref":"BK-100001"}}}'
```

With a real model (`CASEPILOT_LLM_PROVIDER=litellm`) the orchestrator sees `get_document_status` in its prompt
and routes to the new agent. The **mock** orchestrator only knows the bundled intents (keyword patterns in
`_INTENT_PATTERNS`, `app/agents/llm/mock_scripts.py`), so offline routing needs a pattern there or a stub LLM, as
in the last test below.

### 4. The test: `tests/test_documents_agent.py`

```python
import pytest

from app.agents.plugin import load_plugins, registry
from app.agents.tools import ToolRegistry
from app.agents.types import OperationType


@pytest.fixture
def documents_agent():
    load_plugins(["app.agents.documents"])  # what CASEPILOT_AGENT_MODULES does at startup
    from app.agents.documents import PLUGIN

    registry.register(PLUGIN)  # re-register in case an earlier test unregistered it
    yield PLUGIN
    registry.unregister(PLUGIN.agent_id)  # keep the bundled-agent assertions in other tests exact


def test_intent_is_routed_to_the_new_agent(documents_agent):
    assert registry.routing_table()["get_document_status"] == "documents"


def test_tool_is_read_only_and_scoped():
    import app.agents.documents  # noqa: F401

    td = ToolRegistry.get("documents_get_status")
    assert td.operation_type == OperationType.READ
    assert td.agent_scopes == ["documents"] and td.scope == "documents.read"


async def test_agent_answers_from_its_tool(documents_agent):
    state = await documents_agent.graph.ainvoke({"query": "Is the B/L for BK-100001 ready?", "customer_id": "c1"})
    assert state["decision"]["outcome"] == "answered"
    assert [c["name"] for c in state["tool_calls"]] == ["documents_get_status"]
    assert "bill of lading: issued" in state["response_text"]
    assert not state["hitl_required"]


async def test_unknown_booking_is_not_found(documents_agent):
    state = await documents_agent.graph.ainvoke({"query": "Documents for BK-999999?"})
    assert state["decision"]["outcome"] == "not_found"


async def test_pipeline_routes_to_the_new_agent(documents_agent):
    import json

    from app.agents.graphs.pipeline import run_pipeline
    from app.agents.llm import LLMResponse, set_llm_client
    from app.agents.llm.mock import MockLLM

    class Router(MockLLM):  # the mock orchestrator only knows the bundled intents; stub it for this one
        async def complete(self, **kwargs):
            if kwargs.get("agent_name") == "orchestrator":
                return LLMResponse(content=json.dumps({"intent": "get_document_status", "confidence": 0.95}))
            return await super().complete(**kwargs)

    set_llm_client(Router())
    try:
        state = await run_pipeline("Is the bill of lading for BK-100001 ready?", customer_id="c1")
    finally:
        set_llm_client(None)
    assert state["route_to"] == "documents" and state["agent_id"] == "documents"
    assert "bill of lading: issued" in state["response_text"]
```

```bash
cd apps/api && uv run pytest -v tests/test_documents_agent.py
```

The fixture unregisters the plugin afterwards because two existing tests assert the exact bundled set
(`tests/test_api_cases_hitl.py::test_platform_endpoints` and
`tests/test_protocols.py::test_agent_card_lists_registered_agents`). If you add the module to the default
`agent_modules`, update those assertions instead.

### 5. Finish the job

- Add rate limits for the tool if it hits a real backend (`DEFAULT_LIMITS` in `app/agents/rate_limit.py`).
- Put the data behind an adapter (`Protocol` + factory) rather than a dict ([integrations.md](integrations.md#3-how-to-add-an-integration)).
- Add routing cases for the new intent to `apps/api/evals/routing.yaml` and `evals/promptfoo.routing.yaml`.
- A new agent changes agent behaviour and a protocol surface (the agent card, MCP tools), so it needs an ADR
  ([decisions/README.md](decisions/README.md)).

## A write-capable agent

The same contract, plus the booking agent's pattern (`app/agents/booking.py`):

- Register WRITE tools with `operation_type=OperationType.WRITE`. They are only offered when the session's
  `write_allowed` is true, and the gate refuses them otherwise.
- Tell the model to return a `proposed_call` when a write tool is not in its tool list, list the proposable tools
  in the prompt (`ToolRegistry.write_tools_for(AGENT_ID)`), and return `proposed_call` from the node.
  `services/pipeline_service.run_and_escalate` turns it into a HITL item whose approval runs that call.
- Enforce invariants in code: "executed" only if a WRITE tool call succeeded in this run; drop proposals that do
  not name one of your write tools.
- Set `write_capable=True` and `requires_hitl=True` on the plugin.

## Related
- [tools-and-gating.md](tools-and-gating.md): `@tool`, the gate, runtimes
- [hitl-and-shadow-mode.md](hitl-and-shadow-mode.md): proposals and approval
- [protocols.md](protocols.md): how the agent appears on A2A, MCP and AG-UI
- [ADR-001](decisions/001-pluggable-agent-runtime.md)
