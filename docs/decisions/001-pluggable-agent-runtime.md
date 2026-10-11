# ADR-001: Pluggable agent runtime behind one `run_agent` contract

- **Status:** Accepted
- **Date:** 2026-10-09
- **Related:** [ADR-003](003-shadow-first-write-gating.md), [ADR-005](005-adapter-interfaces-for-integrations.md)

## Context
Every casepilot agent (orchestrator, extraction, booking, tracking, and any plugin) runs the same loop: call a
model with the agent's tools, run the tool calls, feed the results back, stop on an answer. Agent frameworks
such as Google ADK provide this loop with sessions, callbacks and tool wrappers, and some teams standardise on
one. Others want no framework dependency at all, or need the whole platform to run offline in CI and demos.

The safety rules must not depend on that choice: write gating, rate limits, loop detection, the cost cap and
guardrails have to behave identically whichever loop runs, or a framework switch silently changes what the
agents are allowed to do.

## Decision
Agents call one function, `run_agent(config, messages, ctx, budget) -> AgentResult`
(`app/agents/runtime/engine.py`), and never a framework or provider directly. `CASEPILOT_AGENT_RUNTIME` selects
the implementation:

- `native` (default): a small owned tool loop (`app/agents/runtime/native.py`) with no extra dependencies.
- `adk`: Google ADK (`app/agents/runtime/adk_engine.py`, extra `adk`): a fresh `LlmAgent` on an
  `InMemoryRunner` per run, so agents stay stateless.

Both implementations must:

1. Offer only `ToolRegistry.get_scoped_tools(agent, READ|WRITE)` according to `SessionContext.write_allowed`.
2. Execute every tool call through `runtime/gate.py:execute_gated` (the ADK side via `GatedFunctionTool`).
3. Apply `check_loop` (`graphs/loop_guard.py`), the `TokenBudget` cost cap and `max_turns`.
4. Run `guard_inbound` on user turns and `check_output` on the final answer.
5. Use the configured `LLMClient` (the ADK side via `BridgeLlm`), so the mock LLM and LiteLLM work under both.
6. Return the same `AgentResult` (`status`, `output`, `tool_calls`, tokens, cost, `error`).

## Consequences
- Agents, the pipeline, HITL and the surfaces are runtime-agnostic; switching is one environment variable.
- The default install needs no agent framework, and tests run deterministically on the mock LLM.
- Safety rules are single-sourced (`check_loop`, `execute_gated`, `guardrails`) and reused by both runtimes,
  so a rule change applies everywhere.
- Two implementations must be kept in step. The ADK runtime is covered by the same behavioural tests
  (`tests/test_integrations.py::test_adk_runtime_runs_the_same_flow`, `::test_adk_runtime_still_gates_writes`),
  which run when the `adk` extra is installed (the `all` CI leg).
- Framework features beyond the contract (ADK multi-agent workflows, persistent sessions, streaming events) are
  not used; a team that wants them can put them behind a plugin's `graph_factory` instead.

## Alternatives considered
| Option | Why not |
|---|---|
| Google ADK only | Makes a framework a hard dependency of the offline demo and CI; ties the safety layer to one framework's callback API. |
| Native loop only | Teams standardising on ADK would have to fork; the contract costs little to keep open. |
| Let each agent pick its own loop | Safety rules would drift per agent; the gate could be bypassed by accident. |

## Implementation notes
- Dispatcher: `apps/api/app/agents/runtime/engine.py` (also opens the `agent:<name>` trace span).
- Native: `apps/api/app/agents/runtime/native.py` (`run_native`, `guard_inbound`).
- ADK: `apps/api/app/agents/runtime/adk_engine.py` (`BridgeLlm`, `GatedFunctionTool`, `loop_guard_before_tool`,
  `loop_guard_before_model`, `cost_after_model`, session-state keys `cp:*`).
- Types: `apps/api/app/agents/types.py` (`AgentConfig`, `SessionContext`, `TokenBudget`, `AgentResult`).
- Setting: `CASEPILOT_AGENT_RUNTIME` in `apps/api/app/config.py`; extra `adk` in `apps/api/pyproject.toml`.
