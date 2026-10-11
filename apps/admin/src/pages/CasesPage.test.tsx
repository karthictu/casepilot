import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeCase, makeResult } from '../test/fixtures'
import { fetchCalls, jsonResponse, mockFetch, renderRoute } from '../test/utils'
import { CasesPage } from './CasesPage'

const cases = [
  makeCase({ id: 'c-1', subject: 'Book 2x40HC to Singapore' }),
  makeCase({
    id: 'c-2',
    subject: 'Amend booking BK-100777',
    reason: 'booking_amend',
    status: 'hitl_required',
    intent: 'booking_amend',
    confidence: 0.61,
    hitl_item_id: 'h-9',
  }),
]

describe('CasesPage', () => {
  it('renders a row per case from the API', async () => {
    mockFetch({ 'GET /api/cases': { items: cases, total: 2 } })
    renderRoute(<CasesPage />, { path: '/cases' })

    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByRole('link', { name: 'Book 2x40HC to Singapore' })).toHaveAttribute('href', '/cases/c-1')
    expect(within(rows[1]).getByText('Needs review')).toBeInTheDocument()
    expect(within(rows[1]).getByText('61%')).toBeInTheDocument()
    expect(screen.getByText('2 of 2')).toBeInTheDocument()
  })

  it('passes the status filter to the API', async () => {
    const fetchMock = mockFetch({ 'GET /api/cases': { items: [], total: 0 } })
    renderRoute(<CasesPage />, { path: '/cases', url: '/cases?status=booked' })

    expect(await screen.findByText(/No cases with status/)).toBeInTheDocument()
    expect(fetchCalls(fetchMock)[0]).toEqual(['GET', '/api/cases?status=booked&limit=100', undefined])
  })

  it('calls the process endpoint for the clicked row and updates it', async () => {
    const processed = makeCase({ ...cases[0], status: 'booked', intent: 'booking_create', booking_ref: 'BK-100123' })
    const fetchMock = mockFetch({
      'GET /api/cases': { items: cases, total: 2 },
      'POST /api/cases/c-1/process': { case: processed, result: makeResult() },
    })
    renderRoute(<CasesPage />, { path: '/cases' })

    await userEvent.click(await screen.findByRole('button', { name: 'Process case Book 2x40HC to Singapore' }))

    await waitFor(() =>
      expect(fetchCalls(fetchMock).filter(([method]) => method === 'POST')).toEqual([
        ['POST', '/api/cases/c-1/process', undefined],
      ]),
    )
    expect(await screen.findByText('Booked BK-100123')).toBeInTheDocument()
    const row = screen.getByRole('link', { name: 'Book 2x40HC to Singapore' }).closest('tr')!
    expect(within(row).getByText('Booked')).toBeInTheDocument()
  })

  it('shows an unreachable-API error', async () => {
    mockFetch({ 'GET /api/cases': () => jsonResponse('Bad Gateway', 502) })
    renderRoute(<CasesPage />, { path: '/cases' })

    expect(await screen.findByRole('alert')).toHaveTextContent('API not reachable at')
  })

  it('renders null intent and confidence on a skipped case as a dash', async () => {
    mockFetch({
      'GET /api/cases': {
        items: [makeCase({ id: 'c-3', subject: 'Invoice question', status: 'skipped', intent: null, confidence: null })],
        total: 1,
      },
    })
    renderRoute(<CasesPage />, { path: '/cases' })

    const row = (await screen.findByRole('link', { name: 'Invoice question' })).closest('tr')!
    const cells = within(row).getAllByRole('cell')
    expect(within(row).getByText('Skipped')).toBeInTheDocument()
    expect(cells[3]).toHaveTextContent(/^—$/) // intent
    expect(cells[4]).toHaveTextContent(/^—$/) // confidence
    expect(cells[5]).toHaveTextContent(/^—$/) // booking
  })
})
