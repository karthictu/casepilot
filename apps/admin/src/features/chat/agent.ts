import { HttpAgent } from '@ag-ui/client'
import { aguiUrl, authHeaders } from '../../api/client'

/** Name of the AG-UI `CUSTOM` event the API emits when a chat turn is escalated. */
export const HITL_EVENT_NAME = 'hitl'

/** An AG-UI agent that streams runs from `POST /api/agui`. */
export function createChatAgent(): HttpAgent {
  return new HttpAgent({ url: aguiUrl(), headers: authHeaders() })
}

/** Pull `hitl_item_id` out of a `CUSTOM{name:"hitl"}` event value, if it is well formed. */
export function hitlItemIdFrom(value: unknown): string | null {
  if (!value || typeof value !== 'object') return null
  const id = (value as { hitl_item_id?: unknown }).hitl_item_id
  return typeof id === 'string' && id ? id : null
}

export const CHAT_SUGGESTIONS = [
  'Where is shipment BK-100001?',
  'Book 2x40HC from Rotterdam to Singapore, cargo ready 2026-11-15',
  'Cancel booking BK-100002',
] as const
