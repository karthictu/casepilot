# casepilot documentation
*reference · last updated 2026-10-09*

## Purpose
The index of every casepilot doc, for anyone deciding where to start reading.

## TL;DR
- New here: read [architecture.md](architecture.md), then [case-pipeline.md](case-pipeline.md).
- Building an agent: [agent-plugin-contract.md](agent-plugin-contract.md) and [tools-and-gating.md](tools-and-gating.md).
- Wiring a real provider or system: [integrations.md](integrations.md) and [configuration.md](configuration.md).
- Calling the API: [api-reference.md](api-reference.md) and [protocols.md](protocols.md).
- Changing behaviour: write an ADR first ([decisions/](decisions/README.md)).

## Explanation

| Doc | Read it to understand |
|---|---|
| [architecture.md](architecture.md) | Components, per-surface request lifecycles, the data model, the safety layers |
| [case-pipeline.md](case-pipeline.md) | How an inbound case becomes a booking or a proposal; case statuses; what the sample cases produce |
| [hitl-and-shadow-mode.md](hitl-and-shadow-mode.md) | Why writes are shadow-first, how propose-then-approve works, the go-live ramp |
| [temporal.md](temporal.md) | The optional durable workflow: design, signal, timeout, retries, local and cloud setup |

## How-to

| Doc | Task |
|---|---|
| [agent-plugin-contract.md](agent-plugin-contract.md) | Add a specialist agent, with a complete worked example and test |
| [integrations.md](integrations.md) §3 | Add a new integration behind an adapter interface |
| [evals-and-ci.md](evals-and-ci.md) | Run the evals and understand each CI workflow |

## Reference

| Doc | Contents |
|---|---|
| [api-reference.md](api-reference.md) | HTTP endpoints and response shapes |
| [protocols.md](protocols.md) | A2A, MCP and AG-UI wire details with curl examples |
| [tools-and-gating.md](tools-and-gating.md) | The `@tool` decorator, the gate, rate limits, the loop-guard rules, runtimes |
| [integrations.md](integrations.md) | Every open-source product and managed service, with licences and enable switches |
| [configuration.md](configuration.md) | Every `CASEPILOT_*` setting with type and default |

## Decisions

| Doc | Contents |
|---|---|
| [decisions/README.md](decisions/README.md) | The ADR / RFD process, numbering, statuses |
| [ADR-001](decisions/001-pluggable-agent-runtime.md) | Pluggable agent runtime |
| [ADR-002](decisions/002-confidence-gated-hitl.md) | Confidence-gated HITL |
| [ADR-003](decisions/003-shadow-first-write-gating.md) | Shadow-first write gating |
| [ADR-004](decisions/004-durable-workflows-with-temporal.md) | Durable workflows with Temporal |
| [ADR-005](decisions/005-adapter-interfaces-for-integrations.md) | Adapter interfaces for integrations |

## Doc conventions
Every doc opens with a title, a tag line (`reference`, `explanation`, `how-to` or `tutorial`, after
[Diátaxis](https://diataxis.fr)), a one-sentence **Purpose** and a **TL;DR**, and ends with **Related** links.
Lead with the answer, use Mermaid for flows, and name real paths, env vars, commands and endpoints.

## Related
- [Root README](../README.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [SECURITY.md](../SECURITY.md)
