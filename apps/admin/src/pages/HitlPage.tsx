import { RefreshCw } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router'
import { describeError, getHitl, listHitl, listTools } from '../api/client'
import type { HitlItem, ItemsResponse } from '../api/types'
import { buttonSecondary } from '../components/buttons'
import { PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { HitlCard } from '../features/hitl/HitlCard'
import { usePolling } from '../hooks/usePolling'

type Tab = 'pending' | 'all'

export function HitlPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'all' ? 'all' : 'pending'
  const focusId = params.get('item')

  const fetcher = useCallback(
    (signal: AbortSignal) => listHitl(tab === 'pending' ? { status: 'pending' } : {}, signal),
    [tab],
  )
  const { data, error, loading, refresh } = usePolling<ItemsResponse<HitlItem>>(fetcher)

  const focusFetcher = useCallback(
    (signal: AbortSignal) => (focusId ? getHitl(focusId, signal) : Promise.resolve(null)),
    [focusId],
  )
  const focus = usePolling<HitlItem | null>(focusFetcher)

  // Write tools for the "Edit call" editor; loaded once.
  const toolsFetcher = useCallback(
    async (signal: AbortSignal) => (await listTools(signal)).items.filter((t) => t.operation_type === 'write'),
    [],
  )
  const tools = usePolling(toolsFetcher, null)
  const writeTools = tools.data ?? []
  const toolsError = tools.error !== undefined ? describeError(tools.error) : undefined

  // Items reviewed in this session stay visible (with their new status and
  // result) even after they drop out of the Pending list.
  const [reviewed, setReviewed] = useState<Record<string, HitlItem>>({})

  const onReviewed = (item: HitlItem) => {
    setReviewed((current) => ({ ...current, [item.id]: item }))
    focus.setData((current) => (current && current.id === item.id ? item : current))
    void refresh()
  }

  const setTab = (next: Tab) => {
    const search = new URLSearchParams(params)
    if (next === 'all') search.set('tab', 'all')
    else search.delete('tab')
    setParams(search, { replace: true })
  }

  // A polled copy that is still `pending` may predate the review we just made;
  // anything else from the server is at least as fresh as our local copy.
  const freshest = (item: HitlItem) => (item.status === 'pending' ? (reviewed[item.id] ?? item) : item)

  const listed = data?.items ?? []
  const listedIds = new Set(listed.map((i) => i.id))
  const focusItem = focus.data ? freshest(focus.data) : null
  const recentlyReviewed = Object.values(reviewed).filter((i) => !listedIds.has(i.id) && i.id !== focusItem?.id)
  const visible = listed.map(freshest).filter((i) => i.id !== focusItem?.id)

  return (
    <>
      <PageHeader
        title="HITL queue"
        description="Actions that need an operator: low-confidence results and writes requested without permission. Approving runs the action with write permission."
        actions={
          <button type="button" className={buttonSecondary} onClick={() => void refresh()} aria-label="Refresh queue">
            <RefreshCw className="size-4" aria-hidden />
          </button>
        }
      />

      <div role="tablist" aria-label="Queue filter" className="mb-5 inline-flex rounded-lg bg-slate-100 p-1">
        {(['pending', 'all'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`rounded-md px-3 py-1 text-sm font-medium ${
              tab === value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {value === 'pending' ? 'Pending' : 'All'}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {focusId && focus.error !== undefined && <ErrorState error={focus.error} />}
        {focusItem && (
          <section aria-label="Linked item" className="space-y-2">
            <p className="text-xs font-semibold tracking-wide text-indigo-700 uppercase">Linked item</p>
            <HitlCard item={focusItem} highlighted onReviewed={onReviewed} writeTools={writeTools} toolsError={toolsError} />
          </section>
        )}

        {recentlyReviewed.length > 0 && (
          <section aria-label="Reviewed in this session" className="space-y-2">
            <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Reviewed just now</p>
            {recentlyReviewed.map((item) => (
              <HitlCard key={item.id} item={item} onReviewed={onReviewed} writeTools={writeTools} toolsError={toolsError} />
            ))}
          </section>
        )}

        {error !== undefined && <ErrorState error={error} onRetry={() => void refresh()} />}
        {loading && <LoadingState label="Loading queue…" />}
        {data && visible.length === 0 && !focusItem && (
          <EmptyState title={tab === 'pending' ? 'Nothing waiting for review' : 'The queue is empty'}>
            Items appear here when a case, an A2A task, an MCP write tool or a chat turn needs approval.
          </EmptyState>
        )}
        {visible.map((item) => (
          <HitlCard key={item.id} item={item} onReviewed={onReviewed} writeTools={writeTools} toolsError={toolsError} />
        ))}
      </div>
    </>
  )
}
