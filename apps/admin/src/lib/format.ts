const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

/** Locale date-time for an ISO-8601 string; falls back to the raw value if unparsable. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : dateTime.format(date)
}

const shortThisYear = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const shortOtherYear = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

/** Compact date-time for tables: "9 Oct, 14:05" this year, "9 Oct 2025" otherwise. */
export function formatShortDateTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return (date.getFullYear() === now.getFullYear() ? shortThisYear : shortOtherYear).format(date)
}

/** A 0..1 confidence as a percentage, e.g. 0.873 → "87%". */
export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
}

export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return '—'
  return id.length > length ? id.slice(0, length) : id
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? 'undefined'
  } catch {
    return String(value)
  }
}
