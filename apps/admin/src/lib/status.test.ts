import { describe, expect, it } from 'vitest'
import { CASE_STATUSES, HITL_STATUSES } from '../api/types'
import { CASE_STATUS_STYLES, caseStatusStyle, HITL_STATUS_STYLES, hitlStatusStyle, TONE_CLASSES } from './status'

describe('case status badges', () => {
  it('has a style for every status in the contract', () => {
    expect(Object.keys(CASE_STATUS_STYLES).sort()).toEqual([...CASE_STATUSES].sort())
  })

  it.each([
    ['new', 'New', 'indigo'],
    ['hitl_required', 'Needs review', 'amber'],
    ['booked', 'Booked', 'emerald'],
    ['failed', 'Failed', 'rose'],
    ['rejected', 'Rejected', 'violet'],
    ['skipped', 'Skipped', 'slate'],
  ])('maps %s to "%s" (%s)', (status, label, tone) => {
    expect(caseStatusStyle(status)).toEqual({ label, tone })
  })

  it('degrades an unknown status to a neutral, humanised badge', () => {
    expect(caseStatusStyle('waiting_on_customer')).toEqual({ label: 'Waiting on customer', tone: 'slate' })
  })
})

describe('HITL status badges', () => {
  it('has a style for every status in the contract', () => {
    expect(Object.keys(HITL_STATUS_STYLES).sort()).toEqual([...HITL_STATUSES].sort())
  })

  it('renders approved as still executing (async workflow)', () => {
    expect(hitlStatusStyle('approved').label).toBe('Approved, executing…')
  })

  it('distinguishes pending, executed and failed', () => {
    expect(hitlStatusStyle('pending').tone).toBe('amber')
    expect(hitlStatusStyle('executed').tone).toBe('emerald')
    expect(hitlStatusStyle('failed').tone).toBe('rose')
  })

  it('every tone resolves to Tailwind classes', () => {
    for (const style of [...Object.values(CASE_STATUS_STYLES), ...Object.values(HITL_STATUS_STYLES)]) {
      expect(TONE_CLASSES[style.tone]).toMatch(/^bg-\S+ text-\S+/)
    }
  })
})
