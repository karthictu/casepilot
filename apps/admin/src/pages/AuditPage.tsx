import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react'
import { Fragment, useCallback, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { listAudit } from '../api/client'
import type { AuditEvent } from '../api/types'
import { Badge } from '../components/Badge'
import { buttonPrimary, buttonSecondary, inputClass } from '../components/buttons'
import { JsonBlock } from '../components/JsonBlock'
import { Card, PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { usePolling } from '../hooks/usePolling'
import { formatDateTime, shortId } from '../lib/format'

const LIMITS = [50, 100, 250, 500] as const

export function AuditPage() {
  const [params, setParams] = useSearchParams()
  const eventType = params.get('event_type') ?? ''
  const limit = Number(params.get('limit')) || 100
  const [draft, setDraft] = useState(eventType)
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())

  const fetcher = useCallback(
    (signal: AbortSignal) => listAudit({ limit, event_type: eventType || undefined }, signal),
    [limit, eventType],
  )
  const { data, error, loading, refresh } = usePolling(fetcher, 10_000)

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    update('event_type', draft.trim())
  }

  const toggle = (id: string) =>
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const knownTypes = Array.from(new Set((data?.items ?? []).map((e: AuditEvent) => e.event_type))).sort()

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every case run, protocol call, approval and admin action, newest first."
        actions={
          <button type="button" className={buttonSecondary} onClick={() => void refresh()} aria-label="Refresh audit log">
            <RefreshCw className="size-4" aria-hidden />
          </button>
        }
      />

      <form onSubmit={onSubmit} className="mb-4 flex flex-wrap items-end gap-3" role="search">
        <div>
          <label htmlFor="audit-event-type" className="mb-1 block text-sm font-medium text-slate-700">
            Event type
          </label>
          <input
            id="audit-event-type"
            list="audit-event-types"
            className={`${inputClass} w-64`}
            placeholder="e.g. case.processed"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <datalist id="audit-event-types">
            {knownTypes.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </div>
        <div>
          <label htmlFor="audit-limit" className="mb-1 block text-sm font-medium text-slate-700">
            Limit
          </label>
          <select id="audit-limit" className={inputClass} value={limit} onChange={(e) => update('limit', e.target.value)}>
            {LIMITS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className={buttonPrimary}>
          Apply
        </button>
        {eventType && (
          <button
            type="button"
            className={buttonSecondary}
            onClick={() => {
              setDraft('')
              update('event_type', '')
            }}
          >
            Clear filter
          </button>
        )}
      </form>

      {error !== undefined && <div className="mb-4"><ErrorState error={error} onRetry={() => void refresh()} /></div>}
      {loading && <LoadingState label="Loading audit log…" />}
      {data && data.items.length === 0 && (
        <EmptyState title={eventType ? `No “${eventType}” events` : 'No audit events yet'} />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Audit events</caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
              <tr>
                <th scope="col" className="w-8 px-3 py-2.5"><span className="sr-only">Payload</span></th>
                <th scope="col" className="px-3 py-2.5">Time</th>
                <th scope="col" className="px-3 py-2.5">Event</th>
                <th scope="col" className="px-3 py-2.5">Surface</th>
                <th scope="col" className="px-3 py-2.5">Actor</th>
                <th scope="col" className="px-3 py-2.5">Request</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((event) => {
                const expanded = open.has(event.id)
                return (
                  <Fragment key={event.id}>
                    <tr className="hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          aria-expanded={expanded}
                          aria-label={`${expanded ? 'Hide' : 'Show'} payload for ${event.event_type}`}
                          onClick={() => toggle(event.id)}
                          className="rounded p-0.5 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
                        >
                          {expanded ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
                        </button>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-slate-500">{formatDateTime(event.created_at)}</td>
                      <td className="px-3 py-2 font-mono text-xs font-medium text-slate-900">{event.event_type}</td>
                      <td className="px-3 py-2">
                        <Badge>{event.surface}</Badge>
                      </td>
                      <td className="px-3 py-2 text-slate-700">{event.actor}</td>
                      <td className="px-3 py-2 font-mono text-xs text-slate-500" title={event.request_id ?? undefined}>
                        {shortId(event.request_id)}
                      </td>
                    </tr>
                    {expanded && (
                      <tr>
                        <td />
                        <td colSpan={5} className="px-3 pb-4">
                          <JsonBlock value={event.payload} label={`Payload for ${event.event_type}`} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
