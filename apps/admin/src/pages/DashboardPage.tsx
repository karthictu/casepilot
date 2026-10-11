import { ArrowRight, ShieldCheck } from 'lucide-react'
import { useCallback } from 'react'
import { Link } from 'react-router'
import { getRuntimeConfig, listAudit, listCases, listHitl } from '../api/client'
import { CASE_STATUSES, type AuditEvent, type CaseStatus, type RuntimeConfig } from '../api/types'
import { Badge, CaseStatusBadge } from '../components/Badge'
import { Card, PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { usePolling } from '../hooks/usePolling'
import { formatDateTime } from '../lib/format'

interface DashboardData {
  counts: Record<CaseStatus, number>
  totalCases: number
  pendingHitl: number
  audit: AuditEvent[]
  config: RuntimeConfig
}

async function loadDashboard(signal: AbortSignal): Promise<DashboardData> {
  // `total` on a one-row page gives an exact count per status without paging.
  const [all, perStatus, hitl, audit, config] = await Promise.all([
    listCases({ limit: 1 }, signal),
    Promise.all(CASE_STATUSES.map((status) => listCases({ status, limit: 1 }, signal))),
    listHitl({ status: 'pending' }, signal),
    listAudit({ limit: 10 }, signal),
    getRuntimeConfig(signal),
  ])
  const counts = Object.fromEntries(CASE_STATUSES.map((status, i) => [status, perStatus[i].total])) as Record<
    CaseStatus,
    number
  >
  return { counts, totalCases: all.total, pendingHitl: hitl.items.length, audit: audit.items.slice(0, 10), config }
}

function WriteModeExplainer({ mode }: { mode: RuntimeConfig['write_mode'] }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-900">Write mode</h2>
        <Badge tone={mode === 'live' ? 'rose' : 'amber'}>{mode}</Badge>
      </div>
      <dl className="mt-3 space-y-3 text-sm text-slate-600">
        <div className={mode === 'shadow' ? '' : 'opacity-60'}>
          <dt className="font-medium text-slate-800">Shadow</dt>
          <dd>
            Cases are classified, extracted and decided end to end, but no booking is created, amended or cancelled.
            Each result is marked <code className="rounded bg-slate-100 px-1">shadow: true</code> so you can compare
            what the pipeline would have done with what operators actually did.
          </dd>
        </div>
        <div className={mode === 'live' ? '' : 'opacity-60'}>
          <dt className="font-medium text-slate-800">Live</dt>
          <dd>
            High-confidence actions execute against the booking backend. Low-confidence results and gated writes still
            land in the HITL queue and only run once an operator approves them.
          </dd>
        </div>
      </dl>
    </Card>
  )
}

export function DashboardPage() {
  const fetcher = useCallback((signal: AbortSignal) => loadDashboard(signal), [])
  const { data, error, loading, refresh } = usePolling(fetcher, 15_000)

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Cases arrive from the CRM, are classified and extracted, and either book directly or wait for an operator."
      />
      {error !== undefined && !data && <ErrorState error={error} onRetry={() => void refresh()} />}
      {loading && <LoadingState />}
      {data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-5">
              <p className="text-sm text-slate-500">Total cases</p>
              <p className="mt-1 text-3xl font-semibold text-slate-900">{data.totalCases}</p>
            </Card>
            <Link
              to="/hitl"
              className="group rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm transition-colors hover:bg-amber-100"
            >
              <p className="flex items-center gap-1.5 text-sm text-amber-800">
                <ShieldCheck className="size-4" aria-hidden /> Pending HITL reviews
              </p>
              <p className="mt-1 flex items-center justify-between text-3xl font-semibold text-amber-900">
                {data.pendingHitl}
                <ArrowRight className="size-5 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
              </p>
            </Link>
            <div className="sm:col-span-2">
              <WriteModeExplainer mode={data.config.write_mode} />
            </div>
          </div>

          <Card>
            <h2 className="border-b border-slate-200 px-5 py-3 text-sm font-semibold text-slate-900">Cases by status</h2>
            <ul className="grid grid-cols-2 divide-slate-100 sm:grid-cols-4 lg:grid-cols-7">
              {CASE_STATUSES.map((status) => (
                <li key={status}>
                  <Link
                    to={`/cases?status=${status}`}
                    className="flex flex-col gap-2 px-5 py-4 hover:bg-slate-50"
                    aria-label={`${data.counts[status]} cases with status ${status}`}
                  >
                    <CaseStatusBadge status={status} />
                    <span className="text-2xl font-semibold text-slate-900">{data.counts[status]}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <h2 className="text-sm font-semibold text-slate-900">Recent activity</h2>
              <Link to="/audit" className="text-sm font-medium text-indigo-700 hover:text-indigo-900">
                Full audit log
              </Link>
            </div>
            {data.audit.length === 0 ? (
              <div className="p-5">
                <EmptyState title="No audit events yet">Process a case or send a chat message to see activity.</EmptyState>
              </div>
            ) : (
              <ol className="divide-y divide-slate-100">
                {data.audit.map((event) => (
                  <li key={event.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-2.5 text-sm">
                    <span className="font-mono text-xs font-medium text-slate-800">{event.event_type}</span>
                    <Badge>{event.surface}</Badge>
                    <span className="text-slate-500">{event.actor}</span>
                    <time className="ml-auto text-xs text-slate-400" dateTime={event.created_at}>
                      {formatDateTime(event.created_at)}
                    </time>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      )}
    </>
  )
}
