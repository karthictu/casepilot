# ADR-005: Adapter interfaces for integrations; offline by default

- **Status:** Accepted
- **Date:** 2026-10-09
- **Related:** [ADR-001](001-pluggable-agent-runtime.md), [ADR-004](004-durable-workflows-with-temporal.md)

## Context
casepilot touches many external systems: a CRM for cases, a booking system, a tracking system, LLM providers,
a memory store, a tracing backend, a workflow engine. Each deployment has a different mix, and a reference
implementation is only useful if it runs end to end without any of them: on a laptop, in CI and in a demo.
Vendor SDKs are large and change often; importing them unconditionally would make every install pay for every
integration.

## Decision
Every integration follows one pattern:

1. **A `Protocol`** that describes what the platform needs, in platform terms (`CaseSource.fetch_new`,
   `BookingBackend.create/amend/cancel/get`, `TrackingBackend`, `LLMClient.complete`, `MemoryStore`, `Tracer`).
2. **Adapters** implementing it: an offline default (mock, in-memory or no-op) plus real ones. A vendor SDK is
   imported lazily inside the adapter or its factory branch, never at module top level of shared code.
3. **A factory** `get_<kind>()` choosing the adapter from a `Literal` setting in `app/config.py`, cached per
   process, and **`set_<kind>(obj | None)`** to inject a fake or reset.
4. **An optional extra** per SDK in `apps/api/pyproject.toml` (`adk`, `litellm`, `langfuse`, `mem0`, `temporal`,
   plus `all`). The base install has none.
5. **An offline test**: inject an `httpx.MockTransport` (adapters take an optional `transport`) or
   `pytest.importorskip("<sdk>")` so the `core` CI leg skips it.

## Consequences
- `make demo` and the whole test suite run with no network and no keys.
- Swapping a provider is a setting, not a code change; adding one is an adapter, a factory branch, an extra and
  a test.
- Tests never patch SDK internals; they inject a fake through `set_<kind>()`.
- The Protocols are the contract to keep stable; adapter internals can change freely.
- Factories cache per process, so in-memory adapters are not shared between the API and a Temporal worker.
- Some factories have only the offline adapter today (booking and tracking backends); a real one needs a new
  setting and factory branch ([integrations.md](../integrations.md#worked-example-a-real-booking-backend-over-http)).

## Alternatives considered
| Option | Why not |
|---|---|
| Depend on vendor SDKs directly | Every install pays for every SDK; tests need network or heavy mocking. |
| A dependency-injection framework | More machinery than five small factories need. |
| Entry-point plugins for adapters | Useful for third-party distribution; premature for a reference implementation. |

## Implementation notes
- Case source: `apps/api/app/integrations/case_source/` (`base.py`, `mock.py`, `salesforce.py`, factory in `__init__.py`).
- Booking / tracking: `apps/api/app/integrations/booking_backend/`, `apps/api/app/integrations/tracking_backend/`.
- LLM: `apps/api/app/agents/llm/` (`base.py`, `mock.py`, `litellm_client.py`, `factory.py`).
- Memory: `apps/api/app/agents/memory/` (`__init__.py`, `inmemory.py`, `mem0_store.py`).
- Tracing: `apps/api/app/observability/` (`tracer.py`, `langfuse_tracer.py`).
- Extras: `[project.optional-dependencies]` in `apps/api/pyproject.toml`.
- Tests: `apps/api/tests/test_integrations.py`.
