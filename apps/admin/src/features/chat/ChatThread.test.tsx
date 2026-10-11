import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useAgUiRuntime } from '@assistant-ui/react-ag-ui'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { renderRoute } from '../../test/utils'
import { createChatAgent } from './agent'
import { ChatThread } from './ChatThread'

// End-to-end through the real stack: HttpAgent → useAgUiRuntime → ChatThread,
// with only `fetch` replaced by a canned AG-UI SSE stream.

function sseResponse(events: Record<string, unknown>[]): Response {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
  return new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } })
}

function streamFor(input: { threadId: string; runId: string }) {
  const { threadId, runId } = input
  return [
    { type: 'RUN_STARTED', threadId, runId },
    { type: 'STEP_STARTED', stepName: 'orchestrator' },
    { type: 'STEP_FINISHED', stepName: 'orchestrator' },
    { type: 'TOOL_CALL_START', toolCallId: 'tc1', toolCallName: 'booking_cancel' },
    { type: 'TOOL_CALL_ARGS', toolCallId: 'tc1', delta: '{"booking_ref":"BK-100002"}' },
    { type: 'TOOL_CALL_END', toolCallId: 'tc1' },
    { type: 'TOOL_CALL_RESULT', messageId: 'tr1', toolCallId: 'tc1', content: '{"status":"pending_approval"}' },
    { type: 'TEXT_MESSAGE_START', messageId: 'a1', role: 'assistant' },
    { type: 'TEXT_MESSAGE_CONTENT', messageId: 'a1', delta: 'Cancellation of BK-100002 ' },
    { type: 'TEXT_MESSAGE_CONTENT', messageId: 'a1', delta: 'is waiting for approval.' },
    { type: 'TEXT_MESSAGE_END', messageId: 'a1' },
    { type: 'CUSTOM', name: 'hitl', value: { hitl_item_id: 'h-77' } },
    { type: 'RUN_FINISHED', threadId, runId },
  ]
}

function Harness() {
  const [agent] = useState(createChatAgent)
  const runtime = useAgUiRuntime({ agent })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatThread />
    </AssistantRuntimeProvider>
  )
}

beforeAll(() => {
  // Layout APIs the thread viewport touches; jsdom does not implement them.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
  Element.prototype.scrollTo ??= () => {}
})

describe('ChatThread over AG-UI', () => {
  it('posts a RunAgentInput to /api/agui and renders the streamed answer and HITL notice', async () => {
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => sseResponse(streamFor(JSON.parse(String(init.body)))))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute(<Harness />, { path: '/chat' })

    await userEvent.click(screen.getByRole('button', { name: 'Cancel booking BK-100002' }))

    expect(await screen.findByText('Cancellation of BK-100002 is waiting for approval.')).toBeInTheDocument()
    expect(screen.getByText('booking_cancel')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Review in HITL queue' })).toHaveAttribute('href', '/hitl?item=h-77'),
    )

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/agui')
    expect(init.headers).toMatchObject({ Accept: 'text/event-stream' })
    const input = JSON.parse(String(init.body))
    expect(input).toMatchObject({ threadId: expect.any(String), runId: expect.any(String), tools: [], context: [] })
    expect(input.messages.at(-1)).toMatchObject({ role: 'user', content: 'Cancel booking BK-100002' })
  })
})
