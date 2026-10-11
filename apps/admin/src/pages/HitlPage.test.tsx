import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { HitlItem } from '../api/types'
import { makeHitlItem, tools } from '../test/fixtures'
import { fetchCalls, jsonResponse, mockFetch, renderRoute } from '../test/utils'
import { HitlPage } from './HitlPage'

describe('HitlPage', () => {
  it('lists pending items with their details', async () => {
    const fetchMock = mockFetch({ 'GET /api/hitl/queue': { items: [makeHitlItem()] } })
    renderRoute(<HitlPage />, { path: '/hitl' })

    const card = await screen.findByRole('article', { name: 'HITL item booking_create' })
    expect(within(card).getByText('source: case')).toBeInTheDocument()
    expect(within(card).getByText('agent: booking')).toBeInTheDocument()
    expect(within(card).getByText('confidence: 62%')).toBeInTheDocument()
    expect(within(card).getByText('Confidence below threshold')).toBeInTheDocument()
    expect(within(card).getByLabelText('Payload for booking_create')).toHaveTextContent('"equipment": "2x40HC"')
    expect(fetchCalls(fetchMock)).toContainEqual(['GET', '/api/hitl/queue?status=pending', undefined])
  })

  it('approve calls the review endpoint and shows the updated status and result', async () => {
    let queue: HitlItem[] = [makeHitlItem()]
    const executed = makeHitlItem({
      status: 'executed',
      reviewer: 'ops@example.com',
      reviewer_note: 'Looks right',
      reviewed_at: '2026-10-01T09:10:00Z',
      result: { booking_ref: 'BK-100555' },
    })
    const fetchMock = mockFetch({
      'GET /api/hitl/queue': () => ({ items: queue }),
      'POST /api/hitl/queue/h-1/review': () => {
        queue = []
        return executed
      },
    })
    renderRoute(<HitlPage />, { path: '/hitl' })

    await userEvent.type(await screen.findByLabelText('Note (optional)'), 'Looks right')
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() =>
      expect(fetchCalls(fetchMock).filter(([method]) => method === 'POST')).toEqual([
        ['POST', '/api/hitl/queue/h-1/review', { decision: 'approve', note: 'Looks right' }],
      ]),
    )
    const card = await screen.findByRole('article', { name: 'HITL item booking_create' })
    expect(within(card).getByText('Executed')).toBeInTheDocument()
    expect(within(card).getByLabelText('Execution result')).toHaveTextContent('BK-100555')
    expect(within(card).queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  })

  it('approve without a note sends only the decision', async () => {
    const fetchMock = mockFetch({
      'GET /api/hitl/queue': { items: [makeHitlItem()] },
      'POST /api/hitl/queue/h-1/review': makeHitlItem({ status: 'executed' }),
    })
    renderRoute(<HitlPage />, { path: '/hitl' })

    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    await waitFor(() =>
      expect(fetchCalls(fetchMock).find(([method]) => method === 'POST')).toEqual([
        'POST',
        '/api/hitl/queue/h-1/review',
        { decision: 'approve' },
      ]),
    )
  })

  it('the All tab omits the status filter', async () => {
    const fetchMock = mockFetch({ 'GET /api/hitl/queue': { items: [] } })
    renderRoute(<HitlPage />, { path: '/hitl' })

    await userEvent.click(await screen.findByRole('tab', { name: 'All' }))

    await waitFor(() => expect(fetchCalls(fetchMock).map(([, path]) => path)).toContain('/api/hitl/queue'))
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true')
  })

  describe('call editor', () => {
    const manual = makeHitlItem({
      id: 'h-7',
      action: 'manual_review',
      reason: 'Could not map the request to a tool',
      payload: {
        tool: null,
        arguments: null,
        context: { subject: 'Please cancel BK-100002', extraction: { booking_ref: 'BK-100002' } },
      },
    })

    it('approving a manual_review item sends the chosen tool and arguments', async () => {
      const fetchMock = mockFetch({
        'GET /api/hitl/queue': { items: [manual] },
        'GET /api/tools': { items: tools },
        'POST /api/hitl/queue/h-7/review': makeHitlItem({ ...manual, status: 'executed' }),
      })
      renderRoute(<HitlPage />, { path: '/hitl' })
      const user = userEvent.setup()

      const card = await screen.findByRole('article', { name: 'HITL item manual_review' })
      // Context is shown read-only so the operator can decide.
      expect(within(card).getByRole('region', { name: 'Context' })).toHaveTextContent('Case subject: Please cancel BK-100002')
      // The editor is open by default and Approve waits for a tool.
      const approve = within(card).getByRole('button', { name: 'Approve' })
      expect(approve).toBeDisabled()

      const select = within(card).getByLabelText('Tool')
      await waitFor(() => expect(within(select).getByRole('option', { name: 'booking_cancel' })).toBeInTheDocument())
      expect(within(select).queryByRole('option', { name: 'booking_status' })).not.toBeInTheDocument()
      await user.selectOptions(select, 'booking_cancel')

      // Arguments start as a skeleton of the tool's JSON-schema properties.
      const args = within(card).getByLabelText('Arguments (JSON)')
      expect(JSON.parse((args as HTMLTextAreaElement).value)).toEqual({ booking_ref: '', notify_customer: false })

      await user.clear(args)
      await user.click(args)
      await user.paste('{"booking_ref": "BK-100002", "notify_customer": true}')
      expect(approve).toBeEnabled()
      await user.click(approve)

      await waitFor(() =>
        expect(fetchCalls(fetchMock).find(([method]) => method === 'POST')).toEqual([
          'POST',
          '/api/hitl/queue/h-7/review',
          { decision: 'approve', tool: 'booking_cancel', arguments: { booking_ref: 'BK-100002', notify_customer: true } },
        ]),
      )
    })

    it('invalid JSON disables Approve until it parses', async () => {
      mockFetch({ 'GET /api/hitl/queue': { items: [makeHitlItem()] }, 'GET /api/tools': { items: tools } })
      renderRoute(<HitlPage />, { path: '/hitl' })
      const user = userEvent.setup()

      const card = await screen.findByRole('article', { name: 'HITL item booking_create' })
      const approve = within(card).getByRole('button', { name: 'Approve' })
      expect(approve).toBeEnabled()

      await user.click(within(card).getByRole('button', { name: 'Edit call' }))
      const args = within(card).getByLabelText('Arguments (JSON)')
      // Prefilled with the proposed arguments.
      expect(JSON.parse((args as HTMLTextAreaElement).value)).toMatchObject({ origin: 'Rotterdam' })

      await user.clear(args)
      await user.click(args)
      await user.paste('{"origin": "Rotterdam",')
      expect(approve).toBeDisabled()
      expect(args).toHaveAttribute('aria-invalid', 'true')
      expect(within(card).getByText(/Invalid JSON/)).toBeInTheDocument()

      await user.paste(' "containers": 2}')
      expect(approve).toBeEnabled()
    })

    it('edited arguments replace the proposed ones', async () => {
      const fetchMock = mockFetch({
        'GET /api/hitl/queue': { items: [makeHitlItem()] },
        'GET /api/tools': { items: tools },
        'POST /api/hitl/queue/h-1/review': makeHitlItem({ status: 'executed' }),
      })
      renderRoute(<HitlPage />, { path: '/hitl' })
      const user = userEvent.setup()

      const card = await screen.findByRole('article', { name: 'HITL item booking_create' })
      await user.click(within(card).getByRole('button', { name: 'Edit call' }))
      const args = within(card).getByLabelText('Arguments (JSON)')
      await user.clear(args)
      await user.click(args)
      await user.paste('{"origin": "Antwerp"}')
      await user.click(within(card).getByRole('button', { name: 'Approve' }))

      await waitFor(() =>
        expect(fetchCalls(fetchMock).find(([method]) => method === 'POST')?.[2]).toEqual({
          decision: 'approve',
          tool: 'booking_create',
          arguments: { origin: 'Antwerp' },
        }),
      )
    })

    it('shows a 422 detail inline on the card', async () => {
      const detail = 'Nothing to execute: approve with a valid `tool` and `arguments`, or reject the item'
      mockFetch({
        'GET /api/hitl/queue': { items: [makeHitlItem()] },
        'GET /api/tools': { items: tools },
        'POST /api/hitl/queue/h-1/review': () => jsonResponse({ detail }, 422),
      })
      renderRoute(<HitlPage />, { path: '/hitl' })

      const card = await screen.findByRole('article', { name: 'HITL item booking_create' })
      await userEvent.click(within(card).getByRole('button', { name: 'Approve' }))

      expect(await within(card).findByRole('alert')).toHaveTextContent(detail)
      expect(within(card).getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    })
  })
})
