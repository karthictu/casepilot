// Types mirroring the casepilot HTTP contract (docs/api-reference.md).
// Keep these in lock-step with the API: field names and unions are verbatim.

export type CaseStatus = 'new' | 'skipped' | 'processing' | 'hitl_required' | 'booked' | 'failed' | 'rejected'

export const CASE_STATUSES: readonly CaseStatus[] = [
  'new',
  'processing',
  'hitl_required',
  'booked',
  'skipped',
  'failed',
  'rejected',
]

export interface Case {
  id: string
  external_id: string
  subject: string
  description: string
  from_address: string
  reason: string
  status: CaseStatus
  intent: string | null
  confidence: number | null
  booking_ref: string | null
  hitl_item_id: string | null
  result: CaseProcessingResult | null
  created_at: string
  updated_at: string
}

export type BookingOutcome = 'executed' | 'hitl_required' | 'failed'

export interface CaseProcessingResult {
  case_id: string
  status: CaseStatus
  intent: string
  reason: string
  confidence: number
  needs_hitl: boolean
  hitl_reason: string
  booking_ref: string | null
  booking_outcome: BookingOutcome | null
  shadow: boolean
  extraction: Record<string, unknown>
  decision: Record<string, unknown>
}

export type HitlStatus = 'pending' | 'approved' | 'rejected' | 'executed' | 'failed'

export const HITL_STATUSES: readonly HitlStatus[] = ['pending', 'approved', 'rejected', 'executed', 'failed']

export type HitlSource = 'case' | 'a2a' | 'mcp' | 'chat'

export interface HitlItem {
  id: string
  source: HitlSource
  source_ref: string
  agent_id: string
  action: string
  payload: Record<string, unknown>
  confidence: number
  reason: string
  status: HitlStatus
  reviewer: string | null
  reviewer_note: string | null
  result: Record<string, unknown> | null
  workflow_id: string | null
  created_at: string
  reviewed_at: string | null
}

export interface AgentInfo {
  agent_id: string
  display_name: string
  description: string
  version: string
  owner_team: string
  intents: string[]
  scopes: string[]
  write_capable: boolean
  requires_hitl: boolean
  hitl_confidence_threshold: number
}

export type OperationType = 'read' | 'write'

export interface ToolInfo {
  name: string
  description: string
  operation_type: OperationType
  agent_scopes: string[]
  scope: string | null
  parameters: Record<string, unknown>
}

export type AuditSurface = 'case_driven' | 'a2a' | 'mcp' | 'chat' | 'admin'

export interface AuditEvent {
  id: string
  event_type: string
  actor: string
  surface: AuditSurface
  request_id: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface RuntimeConfig {
  version: string
  auth_mode: 'mock' | 'jwt'
  write_mode: 'shadow' | 'live'
  agent_runtime: 'native' | 'adk'
  llm_provider: 'mock' | 'litellm'
  case_source: 'mock' | 'salesforce'
  memory_backend: 'inmemory' | 'mem0'
  temporal_enabled: boolean
  langfuse_enabled: boolean
}

// ---- Response envelopes ------------------------------------------------------

export interface ItemsResponse<T> {
  items: T[]
}

export interface CaseListResponse {
  items: Case[]
  total: number
}

export interface HealthResponse {
  status: 'ok'
  version: string
}

export interface ClassifyRequest {
  query: string
}

export interface ClassifyResponse {
  intent: string
  confidence: number
  route_to: string
  reasoning: string
}

export interface PullCasesResponse {
  pulled: number
  created: number
}

/** `POST /api/cases/{id}/process`: synchronous result, or a Temporal workflow id. */
export type ProcessCaseResponse =
  | { case: Case; result: CaseProcessingResult; workflow_id?: undefined }
  | { case: Case; workflow_id: string; result?: undefined }

export type ReviewDecision = 'approve' | 'reject'

export interface ReviewRequest {
  decision: ReviewDecision
  note?: string
  /** Tool to run instead of the proposed one. Required to approve a `manual_review` item. */
  tool?: string
  /** Replaces the proposed arguments; the API keeps the original in `payload.original`. */
  arguments?: Record<string, unknown>
}

/** HITL action used when the pipeline could not propose an executable call. */
export const MANUAL_REVIEW_ACTION = 'manual_review'

// ---- A2A ---------------------------------------------------------------------

export interface AgentCardSkill {
  id: string
  name: string
  description?: string
  [key: string]: unknown
}

export interface AgentCard {
  name: string
  description?: string
  url?: string
  version?: string
  skills: AgentCardSkill[]
  authentication?: unknown
  [key: string]: unknown
}

export interface A2aTextPart {
  type: 'text'
  text: string
}

export interface A2aMessage {
  role: 'user' | 'agent'
  parts: A2aTextPart[]
}

export interface A2aSendTaskRequest {
  id?: string
  message: { role: 'user'; parts: A2aTextPart[] }
  metadata?: Record<string, unknown>
}

export type A2aTaskState = 'completed' | 'input-required' | 'failed'

export interface A2aTask {
  id: string
  status: { state: A2aTaskState; message?: A2aMessage; timestamp?: string }
  artifacts?: { parts: A2aTextPart[]; [key: string]: unknown }[]
  metadata?: { hitl_item_id?: string; [key: string]: unknown }
  [key: string]: unknown
}

// ---- MCP (JSON-RPC 2.0) -------------------------------------------------------

export type McpMethod = 'initialize' | 'ping' | 'tools/list' | 'tools/call'

export interface JsonRpcRequest {
  jsonrpc: '2.0'
  id: number | string
  method: McpMethod
  params?: Record<string, unknown>
}

export interface JsonRpcError {
  code: number
  message: string
  data?: unknown
}

export interface JsonRpcResponse<T = unknown> {
  jsonrpc: '2.0'
  id: number | string | null
  result?: T
  error?: JsonRpcError
}

// ---- Chat (AG-UI) -------------------------------------------------------------

/** Value of the AG-UI `CUSTOM` event named `hitl`. */
export interface HitlCustomEventValue {
  hitl_item_id: string
}
