import { MANUAL_REVIEW_ACTION, type HitlItem, type ToolInfo } from '../api/types'

// Helpers for the executable call a HITL item proposes: `payload.tool` plus
// `payload.arguments`, with `payload.context` as read-only background.

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function proposedTool(item: HitlItem): string | null {
  const tool = item.payload.tool
  return typeof tool === 'string' && tool ? tool : null
}

export function proposedArguments(item: HitlItem): Record<string, unknown> | null {
  const args = item.payload.arguments
  return isRecord(args) ? args : null
}

export function callContext(item: HitlItem): Record<string, unknown> | null {
  const context = item.payload.context
  return isRecord(context) ? context : null
}

export function originalCall(item: HitlItem): unknown {
  return item.payload.original ?? null
}

/** True when the item carries no executable call, so approving needs a tool and arguments. */
export function needsCall(item: HitlItem): boolean {
  return item.action === MANUAL_REVIEW_ACTION || item.payload.tool == null
}

function placeholderFor(schema: unknown): unknown {
  if (!isRecord(schema)) return null
  if ('default' in schema) return schema.default
  if (Array.isArray(schema.enum) && schema.enum.length) return schema.enum[0]
  const type = Array.isArray(schema.type) ? schema.type.find((t) => t !== 'null') : schema.type
  switch (type) {
    case 'string':
      return ''
    case 'integer':
    case 'number':
      return 0
    case 'boolean':
      return false
    case 'array':
      return []
    case 'object':
      return skeletonFromSchema(schema)
    default:
      return null
  }
}

/** An arguments object with one placeholder per property in a JSON Schema. */
export function skeletonFromSchema(schema: Record<string, unknown> | undefined): Record<string, unknown> {
  const properties = schema && isRecord(schema.properties) ? schema.properties : {}
  return Object.fromEntries(Object.entries(properties).map(([key, sub]) => [key, placeholderFor(sub)]))
}

export function skeletonForTool(tools: ToolInfo[], name: string): Record<string, unknown> {
  return skeletonFromSchema(tools.find((t) => t.name === name)?.parameters)
}

export type ParsedArguments = { ok: true; value: Record<string, unknown> } | { ok: false; error: string }

/** Parse the arguments textarea: it must be a JSON object. */
export function parseArguments(text: string): ParsedArguments {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (error) {
    return { ok: false, error: `Invalid JSON: ${error instanceof Error ? error.message : String(error)}` }
  }
  if (!isRecord(value)) return { ok: false, error: 'Arguments must be a JSON object, e.g. {"booking_ref": "BK-1"}' }
  return { ok: true, value }
}
