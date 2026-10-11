# casepilot admin

The operator console for casepilot. It talks to the casepilot API (`apps/api`) and lets an operator:

- watch cases arrive from the CRM, pull new ones and run them through the pipeline;
- inspect a case's extraction and booking decision;
- approve or reject actions waiting in the human-in-the-loop (HITL) queue;
- see which agents and tools are registered (and which tools can write);
- chat with the agents over AG-UI;
- browse the audit log.

The HTTP contract it is built against is [`docs/api-reference.md`](../../docs/api-reference.md). The types in
`src/api/types.ts` mirror it field for field.

## Stack

React 19, TypeScript (strict), Vite, Tailwind CSS 4, React Router, lucide icons. The chat page uses
[assistant-ui](https://www.assistant-ui.com) with its AG-UI runtime (`@assistant-ui/react-ag-ui`) driving an
`HttpAgent` from `@ag-ui/client`. Tests use Vitest, jsdom and Testing Library.

`@ag-ui/client` is pinned to the `0.0.x` line that `@assistant-ui/react-ag-ui` depends on. The `1.x` client
has incompatible message types, and installing it would put two copies of the client in the bundle. Move both
packages together when the adapter supports `1.x`.

TypeScript stays on `6.0.x` because typescript-eslint does not support TypeScript 7 yet.

## Getting started

```bash
npm install
cp .env.example .env.local   # optional
npm run dev                  # http://localhost:5173
```

Start the API on `http://localhost:8000` first (or point the proxy elsewhere, see below). If the API is not
running, each page shows "API not reachable at …" instead of data.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Vite dev server on port 5173, with the API proxy |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/` |
| `npm run preview` | Serve the built `dist/` locally (same proxy as `dev`) |
| `npm run lint` | ESLint (typescript-eslint, react-hooks, react-refresh) |
| `npm test` | Run the test suite once |
| `npm run test:watch` | Run tests in watch mode |

Type-check with `npx tsc -b`. The root `tsconfig.json` only holds project references, so
`tsc --noEmit` against it checks nothing.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | empty | Base URL of the API. Empty means same origin: the Vite proxy in development, nginx in the container. Set it to call an API on another origin directly (the API must allow CORS). |
| `VITE_API_TOKEN` | empty | Optional bearer token, sent as `Authorization: Bearer <token>` on every request, including the chat stream. Only needed when the API runs with `CASEPILOT_AUTH_MODE=jwt`. |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | Dev and preview only: where the proxy forwards requests. |

`VITE_*` values are compiled into the bundle, so anyone who can load the app can read them. Use short-lived
tokens and never put a production secret in `VITE_API_TOKEN`.

## How the proxy works

In development the browser only ever talks to `http://localhost:5173`. Vite forwards these paths to
`VITE_API_PROXY_TARGET`:

| Path | Used for |
|---|---|
| `/api` | REST endpoints used by every page |
| `/api/agui` | Chat (AG-UI over Server-Sent Events) |
| `/a2a`, `/.well-known` | A2A endpoint and agent card |
| `/mcp` | MCP JSON-RPC endpoint |
| `/health` | API health check |

`/api/agui` has its own proxy rule. It asks the upstream for an uncompressed response and marks it
`Cache-Control: no-transform` and `X-Accel-Buffering: no`, so each `data:` frame reaches the browser as soon as
the API writes it rather than when the run ends.

Because requests are same-origin, the API needs no CORS configuration in development.

## Container

```bash
docker build -t casepilot-admin .
docker run -p 8080:80 -e API_UPSTREAM=http://host.docker.internal:8000 casepilot-admin
```

The image builds with Node and serves `dist/` with nginx. `nginx.conf` is installed as a template, so
`API_UPSTREAM` (default `http://api:8000`) is filled in when the container starts. nginx proxies the same paths
as the dev server, turns off buffering for `/api/agui`, and falls back to `index.html` for client-side routes.

## Layout

```
src/
  api/          typed fetch client (one function per endpoint) and contract types
  components/   badges, JSON viewer, empty/error/loading states, toasts
  features/     chat (AG-UI agent factory, assistant-ui thread) and hitl (review card + call editor)
  hooks/        usePolling (Cases and HITL refresh every 5 s)
  layouts/      sidebar + top bar with runtime config badges
  lib/          status badge mapping, formatting helpers
  pages/        one component per route
  test/         test setup, fetch mock helpers, fixtures
```

## Reviewing HITL items

Each pending card shows the proposed call (`payload.tool` and `payload.arguments`). It also shows
`payload.context` (the case subject and extraction, or the chat query) read-only, so the operator has what
they need to decide.

- **Edit call** opens an editor with a tool picker, which lists the write tools from `GET /api/tools`, and a
  JSON textarea for the arguments. The JSON is checked in the browser, and Approve stays disabled until it
  parses to an object. Approving sends `{ decision, note?, tool, arguments }`. The API keeps the original call
  in `payload.original`, which the card shows after review.
- **`manual_review` items** (or any item without `payload.tool`) have nothing to execute. The editor opens by
  default, and Approve is enabled once a tool is chosen and the JSON parses. Choosing a tool fills the arguments
  with a skeleton built from that tool's JSON-schema properties, until you start typing.
- If the API rejects a review (for example a 422), its `detail` message appears on the card.
- `approved` shows as "Approved, executing…". With Temporal, the workflow runs the call asynchronously, and
  the item moves to `executed` or `failed` on a later refresh.

## Chat and HITL

The chat page creates one AG-UI `HttpAgent` per visit and hands it to `useAgUiRuntime`. When a run emits
`CUSTOM { name: "hitl", value: { hitl_item_id } }`, the assistant message shows an inline notice and the page
pins a banner that links to `/hitl?item=<id>`. The HITL page then loads that item with
`GET /api/hitl/queue/{id}` and shows it at the top.
