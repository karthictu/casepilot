import type { Case, CaseProcessingResult, HitlItem, RuntimeConfig, ToolInfo } from '../api/types'

export function makeCase(overrides: Partial<Case> = {}): Case {
  return {
    id: 'c-1',
    external_id: 'CRM-0001',
    subject: 'New booking request',
    description: 'Please book 2x40HC from Rotterdam to Singapore.',
    from_address: 'ops@example.com',
    reason: 'booking_create',
    status: 'new',
    intent: null,
    confidence: null,
    booking_ref: null,
    hitl_item_id: null,
    result: null,
    created_at: '2026-10-01T09:00:00Z',
    updated_at: '2026-10-01T09:00:00Z',
    ...overrides,
  }
}

export function makeResult(overrides: Partial<CaseProcessingResult> = {}): CaseProcessingResult {
  return {
    case_id: 'c-1',
    status: 'booked',
    intent: 'booking_create',
    reason: 'booking_create',
    confidence: 0.93,
    needs_hitl: false,
    hitl_reason: '',
    booking_ref: 'BK-100123',
    booking_outcome: 'executed',
    shadow: false,
    extraction: { origin: 'Rotterdam', destination: 'Singapore' },
    decision: { action: 'booking_create' },
    ...overrides,
  }
}

export function makeHitlItem(overrides: Partial<HitlItem> = {}): HitlItem {
  return {
    id: 'h-1',
    source: 'case',
    source_ref: 'c-1',
    agent_id: 'booking',
    action: 'booking_create',
    payload: {
      tool: 'booking_create',
      arguments: { origin: 'Rotterdam', destination: 'Singapore', equipment: '2x40HC' },
    },
    confidence: 0.62,
    reason: 'Confidence below threshold',
    status: 'pending',
    reviewer: null,
    reviewer_note: null,
    result: null,
    workflow_id: null,
    created_at: '2026-10-01T09:05:00Z',
    reviewed_at: null,
    ...overrides,
  }
}

export const runtimeConfig: RuntimeConfig = {
  version: '0.1.0',
  auth_mode: 'mock',
  write_mode: 'shadow',
  agent_runtime: 'native',
  llm_provider: 'mock',
  case_source: 'mock',
  memory_backend: 'inmemory',
  temporal_enabled: false,
  langfuse_enabled: false,
}

export const tools: ToolInfo[] = [
  {
    name: 'booking_status',
    description: 'Read a booking',
    operation_type: 'read',
    agent_scopes: ['booking'],
    scope: 'booking:read',
    parameters: { type: 'object', properties: { booking_ref: { type: 'string' } } },
  },
  {
    name: 'booking_cancel',
    description: 'Cancel a booking',
    operation_type: 'write',
    agent_scopes: ['booking'],
    scope: 'booking:write',
    parameters: {
      type: 'object',
      properties: { booking_ref: { type: 'string' }, notify_customer: { type: 'boolean' } },
      required: ['booking_ref'],
    },
  },
  {
    name: 'booking_create',
    description: 'Create a booking',
    operation_type: 'write',
    agent_scopes: ['booking'],
    scope: 'booking:write',
    parameters: { type: 'object', properties: { origin: { type: 'string' }, containers: { type: 'integer' } } },
  },
]
