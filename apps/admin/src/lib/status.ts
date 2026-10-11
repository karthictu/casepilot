import type { CaseStatus, HitlStatus } from '../api/types'

export type BadgeTone = 'slate' | 'indigo' | 'sky' | 'amber' | 'emerald' | 'rose' | 'violet'

export interface StatusStyle {
  label: string
  tone: BadgeTone
}

/** Tailwind classes for each badge tone. Written out in full so Tailwind can see them. */
export const TONE_CLASSES: Record<BadgeTone, string> = {
  slate: 'bg-slate-100 text-slate-700 ring-slate-600/20',
  indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
  sky: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/30',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  rose: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  violet: 'bg-violet-50 text-violet-700 ring-violet-600/20',
}

export const CASE_STATUS_STYLES: Record<CaseStatus, StatusStyle> = {
  new: { label: 'New', tone: 'indigo' },
  skipped: { label: 'Skipped', tone: 'slate' },
  processing: { label: 'Processing', tone: 'sky' },
  hitl_required: { label: 'Needs review', tone: 'amber' },
  booked: { label: 'Booked', tone: 'emerald' },
  failed: { label: 'Failed', tone: 'rose' },
  rejected: { label: 'Rejected', tone: 'violet' },
}

export const HITL_STATUS_STYLES: Record<HitlStatus, StatusStyle> = {
  pending: { label: 'Pending', tone: 'amber' },
  // With Temporal the workflow executes an approved item asynchronously.
  approved: { label: 'Approved, executing…', tone: 'sky' },
  rejected: { label: 'Rejected', tone: 'violet' },
  executed: { label: 'Executed', tone: 'emerald' },
  failed: { label: 'Failed', tone: 'rose' },
}

const UNKNOWN: BadgeTone = 'slate'

function humanise(value: string): string {
  const spaced = value.replace(/[_-]+/g, ' ').trim()
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : 'Unknown'
}

/** Badge style for a case status. Unknown values (a newer API) degrade to a neutral badge. */
export function caseStatusStyle(status: string): StatusStyle {
  return CASE_STATUS_STYLES[status as CaseStatus] ?? { label: humanise(status), tone: UNKNOWN }
}

/** Badge style for a HITL item status. Unknown values degrade to a neutral badge. */
export function hitlStatusStyle(status: string): StatusStyle {
  return HITL_STATUS_STYLES[status as HitlStatus] ?? { label: humanise(status), tone: UNKNOWN }
}

export function toneClasses(tone: BadgeTone): string {
  return TONE_CLASSES[tone]
}
