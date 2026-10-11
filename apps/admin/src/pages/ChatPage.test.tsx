import { act, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderRoute } from '../test/utils'
import { ChatPage } from './ChatPage'

// The real runtime needs a streaming backend; these tests cover the page's own
// behaviour: wiring the agent into the runtime and surfacing HITL escalations.
type Subscriber = { onCustomEvent?: (params: { event: { name: string; value: unknown } }) => void }

const fake = vi.hoisted(() => ({
  subscribers: [] as Subscriber[],
  useAgUiRuntime: vi.fn(() => ({})),
}))

vi.mock('../features/chat/agent', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../features/chat/agent')>()
  return {
    ...actual,
    createChatAgent: () => ({
      subscribe: (subscriber: Subscriber) => {
        fake.subscribers.push(subscriber)
        return { unsubscribe: () => fake.subscribers.splice(fake.subscribers.indexOf(subscriber), 1) }
      },
    }),
  }
})

vi.mock('@assistant-ui/react-ag-ui', () => ({ useAgUiRuntime: fake.useAgUiRuntime }))
vi.mock('@assistant-ui/react', () => ({
  AssistantRuntimeProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}))
vi.mock('../features/chat/ChatThread', () => ({ ChatThread: () => <div>thread</div> }))

function emit(name: string, value: unknown) {
  act(() => fake.subscribers.forEach((s) => s.onCustomEvent?.({ event: { name, value } })))
}

describe('ChatPage', () => {
  beforeEach(() => {
    fake.subscribers.length = 0
    fake.useAgUiRuntime.mockClear()
  })

  it('drives the assistant-ui runtime with the AG-UI agent', () => {
    renderRoute(<ChatPage />, { path: '/chat' })

    expect(screen.getByText('thread')).toBeInTheDocument()
    expect(fake.useAgUiRuntime).toHaveBeenCalledWith(expect.objectContaining({ agent: expect.any(Object) }))
  })

  it('shows a notice linking to the HITL queue on a CUSTOM "hitl" event', () => {
    renderRoute(<ChatPage />, { path: '/chat' })
    expect(screen.queryByRole('link', { name: 'Open HITL queue' })).not.toBeInTheDocument()

    emit('hitl', { hitl_item_id: 'h-42' })

    expect(screen.getByRole('link', { name: 'Open HITL queue' })).toHaveAttribute('href', '/hitl?item=h-42')
  })

  it('ignores other custom events and malformed values', () => {
    renderRoute(<ChatPage />, { path: '/chat' })

    emit('progress', { hitl_item_id: 'h-1' })
    emit('hitl', { item: 'h-2' })

    expect(screen.queryByRole('link', { name: 'Open HITL queue' })).not.toBeInTheDocument()
  })
})
