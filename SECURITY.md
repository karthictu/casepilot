# Security policy

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub's
[private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" on the repository's Security tab). Do not open a public issue or PR.

Include what you found, how to reproduce it, the affected version or commit, and the `X-Request-ID` of an
example request if you have one. We aim to acknowledge reports within a few working days and will agree a
disclosure date with you. casepilot is a reference implementation maintained on a best-effort basis; only the
latest release receives fixes.

## Security model

| Area | How casepilot handles it |
|---|---|
| Authentication | `CASEPILOT_AUTH_MODE=mock` (default) treats **every request as an operator holding every scope**. It exists for local development and demos only; never expose a mock-mode API on a network. `jwt` mode verifies bearer tokens (HS256 shared secret, or RS256/ES256 via a JWKS URL; optional audience and issuer checks). |
| Authorisation | Scopes come from the token's `scope` or `scp` claim. `/api/cases/*`, `/api/hitl/*` and `/api/audit` require `casepilot.operator`. MCP shows and runs only the tools whose `scope` the caller holds. |
| Write boundary | Every tool call passes through one gate (`app/agents/runtime/gate.py`). WRITE tools run only with platform-seeded permission (live case processing above the confidence threshold, or an operator's approval); A2A, chat and MCP are always read-only, and their writes become HITL items. The model cannot grant itself permission. |
| Approval integrity | An approved HITL item runs exactly its stored `{tool, arguments}`; the model is not re-run. Corrections are recorded in `payload.original`. |
| Shadow mode | `CASEPILOT_WRITE_MODE=shadow` (default): case processing never writes. |
| Abuse limits | Per-tool, per-caller rate limits; a loop guard; a per-run LLM cost cap; max turns per run. |
| Prompt and content safety | Regex guardrails redact emails, international phone numbers, Luhn-valid card numbers and IBANs in user input and final answers, and block a short list of denied topics. They are a baseline, not a complete content-safety system. |
| Audit | `audit_events` is append-only (a Postgres trigger rejects `UPDATE` and `DELETE`); payloads are PII-redacted; each event carries the request id. |
| Secrets | All credentials come from environment variables or a git-ignored `.env`; `secrets/`, `*.pem` and `*.key` are git-ignored. |

## Known limitations

Plan around these when you deploy beyond a laptop:

- **Unauthenticated read endpoints.** `/health`, `/api/config`, `/api/agents`, `/api/tools` and
  `/.well-known/agent.json` are public by design. `GET /a2a/tasks/{id}` returns a task only to the principal that
  created it (404 otherwise).
- **PII at rest.** Case descriptions, sender addresses and HITL `payload.context` are stored as received; only
  audit payloads are redacted. Protect the database accordingly.
- **Traces.** With LangFuse enabled, every span's input, output and metadata pass through the same PII redaction
  as the audit trail (the LangFuse client's `mask` hook in `app/observability/langfuse_tracer.py`).
- **Admin token.** `VITE_API_TOKEN` is compiled into the admin bundle; use only short-lived tokens.
- **In-process state.** Rate-limit windows and A2A tasks live in process memory and are per replica.
- **CORS.** `CASEPILOT_CORS_ORIGINS` allows credentials; list only origins you control.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |
