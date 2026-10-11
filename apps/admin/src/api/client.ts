import type {
  A2aSendTaskRequest,
  A2aTask,
  AgentCard,
  AgentInfo,
  AuditEvent,
  Case,
  CaseListResponse,
  CaseStatus,
  ClassifyResponse,
  HealthResponse,
  HitlItem,
  HitlStatus,
  ItemsResponse,
  JsonRpcResponse,
  McpMethod,
  ProcessCaseResponse,
  PullCasesResponse,
  ReviewRequest,
  RuntimeConfig,
  ToolInfo,
} from './types'

// ---- Configuration -----------------------------------------------------------

export interface ClientConfig {
  /** Origin (and optional path prefix) of the API. Empty string = same origin. */
  baseUrl: string
  /** Optional bearer token sent as `Authorization: Bearer <token>`. */
  token?: string
}

function configFromEnv(): ClientConfig {
  return {
    baseUrl: (import.meta.env.VITE_API_BASE_URL ?? '').trim(),
    token: (import.meta.env.VITE_API_TOKEN ?? '').trim() || undefined,
  }
}

let config: ClientConfig = configFromEnv()

/** Override the client configuration (used by tests; also handy for embedding). */
export function configureClient(next: Partial<ClientConfig>): void {
  config = { ...config, ...next }
}

/** Reset the configuration to what the build-time environment provides. */
export function resetClientConfig(): void {
  config = configFromEnv()
}

export function getClientConfig(): Readonly<ClientConfig> {
  return config
}

/** Human-readable label for where the API lives, used in error messages. */
export function apiLocationLabel(): string {
  if (config.baseUrl) return config.baseUrl
  if (typeof window !== 'undefined') return `${window.location.origin} (proxied)`
  return 'the same origin'
}

// ---- Errors ------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? ApiError.describe(status, body))
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /**
   * True when the request never got an answer from the API itself: a network
   * failure, or a 5xx without a JSON body (the API always answers in JSON, so
   * a bare 502/503/504 came from the dev proxy or nginx in front of it).
   */
  get unreachable(): boolean {
    if (this.status === 0) return true
    return this.status >= 500 && (this.body === null || typeof this.body !== 'object')
  }

  private static describe(status: number, body: unknown): string {
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return `${status}: ${detail}`
      return `${status}: ${JSON.stringify(detail)}`
    }
    if (typeof body === 'string' && body.trim()) return `${status}: ${body.trim().slice(0, 200)}`
    return `Request failed with status ${status}`
  }
}

/** The API's own `detail` message when it sent one, otherwise a generic description. */
export function errorDetail(error: unknown): string {
  if (error instanceof ApiError && !error.unreachable && error.body && typeof error.body === 'object') {
    const detail = (error.body as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail) return detail
  }
  return describeError(error)
}

/** Turn any thrown value into a sentence suitable for an error banner. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.unreachable) return `API not reachable at ${apiLocationLabel()}`
    return error.message
  }
  if (error instanceof Error) return error.message
  return String(error)
}

// ---- Core request ------------------------------------------------------------

export type QueryValue = string | number | boolean | null | undefined

/** Build an absolute or same-origin URL, dropping empty query values. */
export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const base = config.baseUrl.replace(/\/+$/, '')
  const normalisedPath = path.startsWith('/') ? path : `/${path}`
  let url = `${base}${normalisedPath}`
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue
      params.set(key, String(value))
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }
  return url
}

/** Headers every call carries: JSON accept plus the bearer token when configured. */
export function authHeaders(): Record<string, string> {
  return config.token ? { Authorization: `Bearer ${config.token}` } : {}
}

export interface RequestOptions {
  query?: Record<string, QueryValue>
  body?: unknown
  signal?: AbortSignal
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('json')) {
    try {
      return JSON.parse(text)
    } catch {
      return text
    }
  }
  return text
}

export async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...authHeaders() }
  let body: string | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), { method, headers, body, signal: options.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, null, `API not reachable at ${apiLocationLabel()}`)
  }

  const parsed = await readBody(response)
  if (!response.ok) throw new ApiError(response.status, parsed)
  return parsed as T
}

// ---- Platform ----------------------------------------------------------------

export const getHealth = (signal?: AbortSignal) => request<HealthResponse>('GET', '/health', { signal })

export const getRuntimeConfig = (signal?: AbortSignal) => request<RuntimeConfig>('GET', '/api/config', { signal })

export const listAgents = (signal?: AbortSignal) => request<ItemsResponse<AgentInfo>>('GET', '/api/agents', { signal })

export const listTools = (signal?: AbortSignal) => request<ItemsResponse<ToolInfo>>('GET', '/api/tools', { signal })

export const classifyQuery = (query: string, signal?: AbortSignal) =>
  request<ClassifyResponse>('POST', '/api/agents/orchestrator/classify', { body: { query }, signal })

export interface AuditQuery {
  limit?: number
  event_type?: string
}

export const listAudit = (query: AuditQuery = {}, signal?: AbortSignal) =>
  request<ItemsResponse<AuditEvent>>('GET', '/api/audit', {
    query: { limit: query.limit ?? 100, event_type: query.event_type },
    signal,
  })

// ---- Case-driven ingress -------------------------------------------------------

export const pullCases = () => request<PullCasesResponse>('POST', '/api/cases/pull')

export interface CaseQuery {
  status?: CaseStatus
  limit?: number
}

export const listCases = (query: CaseQuery = {}, signal?: AbortSignal) =>
  request<CaseListResponse>('GET', '/api/cases', {
    query: { status: query.status, limit: query.limit ?? 100 },
    signal,
  })

export const getCase = (id: string, signal?: AbortSignal) =>
  request<Case>('GET', `/api/cases/${encodeURIComponent(id)}`, { signal })

export const processCase = (id: string) =>
  request<ProcessCaseResponse>('POST', `/api/cases/${encodeURIComponent(id)}/process`)

// ---- Human in the loop ---------------------------------------------------------

export const listHitl = (query: { status?: HitlStatus } = {}, signal?: AbortSignal) =>
  request<ItemsResponse<HitlItem>>('GET', '/api/hitl/queue', { query: { status: query.status }, signal })

export const getHitl = (id: string, signal?: AbortSignal) =>
  request<HitlItem>('GET', `/api/hitl/queue/${encodeURIComponent(id)}`, { signal })

export const reviewHitl = (id: string, review: ReviewRequest) => {
  const body: ReviewRequest = { decision: review.decision }
  const note = review.note?.trim()
  if (note) body.note = note
  if (review.tool) body.tool = review.tool
  if (review.arguments !== undefined) body.arguments = review.arguments
  return request<HitlItem>('POST', `/api/hitl/queue/${encodeURIComponent(id)}/review`, { body })
}

// ---- A2A -----------------------------------------------------------------------

export const getAgentCard = (signal?: AbortSignal) => request<AgentCard>('GET', '/.well-known/agent.json', { signal })

export const sendA2aTask = (task: A2aSendTaskRequest) => request<A2aTask>('POST', '/a2a/tasks/send', { body: task })

export const getA2aTask = (id: string, signal?: AbortSignal) =>
  request<A2aTask>('GET', `/a2a/tasks/${encodeURIComponent(id)}`, { signal })

// ---- MCP -----------------------------------------------------------------------

let rpcId = 0

/** One JSON-RPC 2.0 call against `POST /mcp`. */
export const mcpCall = <T = unknown>(method: McpMethod, params?: Record<string, unknown>) =>
  request<JsonRpcResponse<T>>('POST', '/mcp', { body: { jsonrpc: '2.0', id: ++rpcId, method, params } })

// ---- Chat (AG-UI) --------------------------------------------------------------

/** URL of the AG-UI endpoint; the stream itself is driven by `@ag-ui/client`. */
export const aguiUrl = () => buildUrl('/api/agui')
