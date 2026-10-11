import {
  AuiIf,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type DataMessagePartComponent,
  type TextMessagePartComponent,
  type ToolCallMessagePartComponent,
} from '@assistant-ui/react'
import { ArrowDown, Bot, Send, ShieldCheck, Square, Wrench } from 'lucide-react'
import { Link } from 'react-router'
import { prettyJson } from '../../lib/format'
import { CHAT_SUGGESTIONS, HITL_EVENT_NAME, hitlItemIdFrom } from './agent'

const Text: TextMessagePartComponent = ({ text }) => <p className="whitespace-pre-wrap">{text}</p>

const ToolCall: ToolCallMessagePartComponent = ({ toolName, argsText, result, status }) => {
  const running = status.type === 'running'
  return (
    <details className="my-2 rounded-lg border border-slate-200 bg-slate-50 text-xs">
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 font-medium text-slate-700">
        <Wrench className="size-3.5" aria-hidden />
        <span className="font-mono">{toolName}</span>
        <span className="text-slate-400">{running ? 'running…' : 'done'}</span>
      </summary>
      <div className="space-y-2 border-t border-slate-200 px-3 py-2">
        <div>
          <p className="mb-1 font-semibold text-slate-500">Arguments</p>
          <pre className="overflow-auto rounded bg-white p-2 font-mono text-slate-800">{argsText || '{}'}</pre>
        </div>
        {result !== undefined && (
          <div>
            <p className="mb-1 font-semibold text-slate-500">Result</p>
            <pre className="max-h-60 overflow-auto rounded bg-white p-2 font-mono text-slate-800">
              {typeof result === 'string' ? result : prettyJson(result)}
            </pre>
          </div>
        )}
      </div>
    </details>
  )
}

/** Inline rendering of the `CUSTOM{name:"hitl"}` event inside the assistant turn. */
const HitlNotice: DataMessagePartComponent = ({ data }) => {
  const id = hitlItemIdFrom(data)
  if (!id) return null
  return (
    <div className="my-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <ShieldCheck className="size-4" aria-hidden />
      <span>This request needs operator approval.</span>
      <Link to={`/hitl?item=${encodeURIComponent(id)}`} className="font-medium underline underline-offset-2">
        Review in HITL queue
      </Link>
    </div>
  )
}

const assistantParts = {
  Text,
  tools: { Fallback: ToolCall },
  data: { by_name: { [HITL_EVENT_NAME]: HitlNotice } },
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end py-2">
      <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-sm text-white">
        <MessagePrimitive.Parts components={{ Text }} />
      </div>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="flex gap-3 py-2">
      <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
        <Bot className="size-4" aria-hidden />
      </span>
      <div className="max-w-[80%] min-w-0 rounded-2xl rounded-bl-sm bg-white px-4 py-2 text-sm text-slate-800 shadow-sm ring-1 ring-slate-200">
        <MessagePrimitive.Parts components={assistantParts} />
        <MessagePrimitive.Error>
          <ErrorPrimitive.Root className="mt-2 rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-700" role="alert">
            <ErrorPrimitive.Message />
          </ErrorPrimitive.Root>
        </MessagePrimitive.Error>
      </div>
    </MessagePrimitive.Root>
  )
}

function Welcome() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-12 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
        <Bot className="size-5" aria-hidden />
      </span>
      <h2 className="mt-3 text-base font-semibold text-slate-900">Ask the booking and tracking agents</h2>
      <p className="mt-1 text-sm text-slate-600">
        The orchestrator routes each message to a specialist. Writes are gated and appear in the HITL queue.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2" aria-label="Suggestions">
        {CHAT_SUGGESTIONS.map((prompt) => (
          <ThreadPrimitive.Suggestion
            key={prompt}
            prompt={prompt}
            send
            className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-800"
          >
            {prompt}
          </ThreadPrimitive.Suggestion>
        ))}
      </div>
    </div>
  )
}

export function ChatThread() {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
      <ThreadPrimitive.Viewport className="relative flex-1 overflow-y-auto px-4">
        <AuiIf condition={(s) => s.thread.isEmpty}>
          <Welcome />
        </AuiIf>
        <ThreadPrimitive.Messages>
          {({ message }) => (message.role === 'user' ? <UserMessage /> : <AssistantMessage />)}
        </ThreadPrimitive.Messages>
        <ThreadPrimitive.ScrollToBottom
          aria-label="Scroll to latest message"
          className="sticky bottom-2 left-full flex size-8 items-center justify-center rounded-full bg-white text-slate-600 shadow ring-1 ring-slate-200 disabled:invisible"
        >
          <ArrowDown className="size-4" aria-hidden />
        </ThreadPrimitive.ScrollToBottom>
      </ThreadPrimitive.Viewport>

      <ComposerPrimitive.Root className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
        <ComposerPrimitive.Input
          aria-label="Message"
          placeholder="Ask about a shipment, or request a booking…"
          rows={1}
          className="max-h-40 min-h-9 flex-1 resize-none rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 ring-inset focus:ring-2 focus:ring-indigo-500 focus:outline-none"
        />
        <AuiIf condition={(s) => !s.thread.isRunning}>
          <ComposerPrimitive.Send
            aria-label="Send message"
            className="flex size-9 items-center justify-center rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            <Send className="size-4" aria-hidden />
          </ComposerPrimitive.Send>
        </AuiIf>
        <AuiIf condition={(s) => s.thread.isRunning}>
          <ComposerPrimitive.Cancel
            aria-label="Stop"
            className="flex size-9 items-center justify-center rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300"
          >
            <Square className="size-4" aria-hidden />
          </ComposerPrimitive.Cancel>
        </AuiIf>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  )
}
