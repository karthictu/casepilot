import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useAgUiRuntime } from '@assistant-ui/react-ag-ui'
import { ShieldCheck, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { apiLocationLabel } from '../api/client'
import { Card, PageHeader } from '../components/PageHeader'
import { useToast } from '../components/toast-context'
import { ChatThread } from '../features/chat/ChatThread'
import { createChatAgent, HITL_EVENT_NAME, hitlItemIdFrom } from '../features/chat/agent'
import { shortId } from '../lib/format'

export function ChatPage() {
  // One agent per page visit: it owns the thread id and message history.
  const [agent] = useState(createChatAgent)
  const [hitlItems, setHitlItems] = useState<string[]>([])
  const { notify } = useToast()

  // The runtime renders CUSTOM events inline; subscribing on the agent as well
  // lets the page keep a persistent notice above the thread.
  useEffect(() => {
    const subscription = agent.subscribe({
      onCustomEvent: ({ event }) => {
        if (event.name !== HITL_EVENT_NAME) return
        const id = hitlItemIdFrom(event.value)
        if (id) setHitlItems((current) => (current.includes(id) ? current : [...current, id]))
      },
    })
    return () => subscription.unsubscribe()
  }, [agent])

  const runtime = useAgUiRuntime({
    agent,
    onError: (error) =>
      notify({
        tone: 'error',
        title: 'Chat run failed',
        description: /fetch|network/i.test(error.message)
          ? `API not reachable at ${apiLocationLabel()}`
          : error.message,
      }),
  })

  return (
    <div className="flex h-[calc(100vh-7.5rem)] flex-col">
      <PageHeader
        title="Chat"
        description="A chat front end over the same core, streamed with AG-UI from /api/agui."
      />

      {hitlItems.length > 0 && (
        <ul aria-label="Pending approvals from this chat" className="mb-3 space-y-2">
          {hitlItems.map((id) => (
            <li
              key={id}
              role="status"
              className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900"
            >
              <ShieldCheck className="size-4" aria-hidden />
              <span>
                A request from this chat is waiting for operator approval (item{' '}
                <span className="font-mono">{shortId(id)}</span>).
              </span>
              <Link
                to={`/hitl?item=${encodeURIComponent(id)}`}
                className="font-medium underline underline-offset-2 hover:text-amber-700"
              >
                Open HITL queue
              </Link>
              <button
                type="button"
                aria-label="Dismiss notice"
                onClick={() => setHitlItems((current) => current.filter((x) => x !== id))}
                className="ml-auto rounded p-0.5 text-amber-700 hover:bg-amber-100"
              >
                <X className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Card className="min-h-0 flex-1 overflow-hidden bg-slate-50">
        <AssistantRuntimeProvider runtime={runtime}>
          <ChatThread />
        </AssistantRuntimeProvider>
      </Card>
    </div>
  )
}
