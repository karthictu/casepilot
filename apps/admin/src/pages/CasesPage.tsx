import { Download, LoaderCircle, Play, RefreshCw } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { describeError, listCases, processCase, pullCases } from '../api/client'
import { CASE_STATUSES, type CaseListResponse, type CaseStatus } from '../api/types'
import { CaseStatusBadge } from '../components/Badge'
import { buttonPrimary, buttonSecondary, buttonSmall, inputClass } from '../components/buttons'
import { Card, PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/toast-context'
import { usePolling } from '../hooks/usePolling'
import { formatConfidence, formatDateTime, formatShortDateTime } from '../lib/format'
import { summariseProcessing } from '../lib/processing'
import { caseStatusStyle } from '../lib/status'

function isCaseStatus(value: string | null): value is CaseStatus {
  return value !== null && (CASE_STATUSES as readonly string[]).includes(value)
}

export function CasesPage() {
  const [params, setParams] = useSearchParams()
  const rawStatus = params.get('status')
  const status = isCaseStatus(rawStatus) ? rawStatus : undefined
  const { notify } = useToast()

  const fetcher = useCallback((signal: AbortSignal) => listCases({ status, limit: 100 }, signal), [status])
  const { data, error, loading, refresh, setData } = usePolling<CaseListResponse>(fetcher)

  const [pulling, setPulling] = useState(false)
  const [processing, setProcessing] = useState<ReadonlySet<string>>(new Set())

  const onStatusChange = (value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set('status', value)
    else next.delete('status')
    setParams(next, { replace: true })
  }

  const onPull = async () => {
    setPulling(true)
    try {
      const result = await pullCases()
      notify({
        tone: 'success',
        title: `Pulled ${result.pulled} case${result.pulled === 1 ? '' : 's'}`,
        description: `${result.created} new`,
      })
      await refresh()
    } catch (err) {
      notify({ tone: 'error', title: 'Pull failed', description: describeError(err) })
    } finally {
      setPulling(false)
    }
  }

  const onProcess = async (id: string) => {
    setProcessing((current) => new Set(current).add(id))
    try {
      const response = await processCase(id)
      setData((current) =>
        current && { ...current, items: current.items.map((c) => (c.id === id ? response.case : c)) },
      )
      notify(summariseProcessing(response))
    } catch (err) {
      notify({ tone: 'error', title: 'Processing failed', description: describeError(err) })
    } finally {
      setProcessing((current) => {
        const next = new Set(current)
        next.delete(id)
        return next
      })
    }
  }

  return (
    <>
      <PageHeader
        title="Cases"
        description="Cases ingested from the CRM. Processing classifies the case, extracts booking details and decides whether to book or ask an operator."
        actions={
          <>
            <button type="button" className={buttonSecondary} onClick={() => void refresh()} aria-label="Refresh cases">
              <RefreshCw className="size-4" aria-hidden />
            </button>
            <button type="button" className={buttonPrimary} onClick={() => void onPull()} disabled={pulling}>
              {pulling ? (
                <LoaderCircle className="size-4 animate-spin" aria-hidden />
              ) : (
                <Download className="size-4" aria-hidden />
              )}
              Pull cases
            </button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label htmlFor="case-status-filter" className="text-sm font-medium text-slate-700">
          Status
        </label>
        <select
          id="case-status-filter"
          className={inputClass}
          value={status ?? ''}
          onChange={(e) => onStatusChange(e.target.value)}
        >
          <option value="">All statuses</option>
          {CASE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {caseStatusStyle(s).label}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-sm text-slate-500">
            {data.items.length} of {data.total}
          </span>
        )}
      </div>

      {error !== undefined && <div className="mb-4"><ErrorState error={error} onRetry={() => void refresh()} /></div>}
      {loading && <LoadingState label="Loading cases…" />}

      {data && data.items.length === 0 && (
        <EmptyState title={status ? `No cases with status “${caseStatusStyle(status).label}”` : 'No cases yet'}>
          Use <strong>Pull cases</strong> to fetch new cases from the configured case source.
        </EmptyState>
      )}

      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          {/* Narrow screens scroll the table instead of clipping the action column. */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <caption className="sr-only">Cases</caption>
              <thead className="bg-slate-50 text-left text-xs font-semibold tracking-wide whitespace-nowrap text-slate-500 uppercase">
                <tr>
                  <th scope="col" className="px-3 py-2.5">Subject</th>
                  <th scope="col" className="px-3 py-2.5">Reason</th>
                  <th scope="col" className="px-3 py-2.5">Status</th>
                  <th scope="col" className="px-3 py-2.5">Intent</th>
                  <th scope="col" className="px-3 py-2.5 text-right">Conf.</th>
                  <th scope="col" className="px-3 py-2.5">Booking</th>
                  <th scope="col" className="px-3 py-2.5">Created</th>
                  <th scope="col" className="w-px px-3 py-2.5"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((c) => {
                  const busy = processing.has(c.id)
                  return (
                    <tr key={c.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2.5">
                        {/* max-width on the content, not the cell: auto-layout tables ignore cell max-width. */}
                        <Link
                          to={`/cases/${c.id}`}
                          title={c.subject}
                          className="block max-w-72 truncate font-medium text-indigo-700 hover:text-indigo-900"
                        >
                          {c.subject || '(no subject)'}
                        </Link>
                        <span className="block max-w-72 truncate text-xs text-slate-500">{c.from_address}</span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span title={c.reason} className="block max-w-40 truncate font-mono text-xs text-slate-700">
                          {c.reason}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <CaseStatusBadge status={c.status} />
                      </td>
                      <td className="px-3 py-2.5">
                        <span title={c.intent ?? undefined} className="block max-w-40 truncate font-mono text-xs text-slate-700">
                          {c.intent ?? '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right whitespace-nowrap tabular-nums text-slate-700">
                        {formatConfidence(c.confidence)}
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs whitespace-nowrap text-slate-700">{c.booking_ref ?? '—'}</td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-slate-500">
                        <time dateTime={c.created_at} title={formatDateTime(c.created_at)}>
                          {formatShortDateTime(c.created_at)}
                        </time>
                      </td>
                      <td className="w-px px-3 py-2.5 text-right whitespace-nowrap">
                        <button
                          type="button"
                          className={`${buttonSecondary} ${buttonSmall}`}
                          onClick={() => void onProcess(c.id)}
                          disabled={busy}
                          aria-label={`Process case ${c.subject || c.external_id}`}
                        >
                          {busy ? (
                            <LoaderCircle className="size-3.5 animate-spin" aria-hidden />
                          ) : (
                            <Play className="size-3.5" aria-hidden />
                          )}
                          Process
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  )
}
