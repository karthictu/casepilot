import { ArrowLeft, LoaderCircle, Play, ShieldCheck } from 'lucide-react'
import { useCallback, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { describeError, getCase, processCase } from '../api/client'
import type { Case, CaseProcessingResult } from '../api/types'
import { Badge, CaseStatusBadge } from '../components/Badge'
import { buttonPrimary } from '../components/buttons'
import { JsonBlock } from '../components/JsonBlock'
import { Card, PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/toast-context'
import { usePolling } from '../hooks/usePolling'
import { formatConfidence, formatDateTime } from '../lib/format'
import { summariseProcessing } from '../lib/processing'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="mt-0.5 text-sm break-words text-slate-900">{children}</dd>
    </div>
  )
}

function ResultPanel({ result }: { result: CaseProcessingResult }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-900">Processing result</h2>
        <CaseStatusBadge status={result.status} />
        {result.shadow && (
          <Badge tone="amber" title="The run was not allowed to write">
            shadow
          </Badge>
        )}
        {result.booking_outcome && <Badge tone="indigo">outcome: {result.booking_outcome}</Badge>}
      </div>
      <dl className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Intent">
          <span className="font-mono text-xs">{result.intent || '—'}</span>
        </Field>
        <Field label="Confidence">{formatConfidence(result.confidence)}</Field>
        <Field label="Booking ref">
          <span className="font-mono text-xs">{result.booking_ref ?? '—'}</span>
        </Field>
        <Field label="Needs HITL">{result.needs_hitl ? 'Yes' : 'No'}</Field>
        {result.hitl_reason && (
          <div className="sm:col-span-2 lg:col-span-4">
            <Field label="HITL reason">{result.hitl_reason}</Field>
          </div>
        )}
      </dl>
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Extraction</h3>
          <JsonBlock value={result.extraction} label="Extraction" />
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Decision</h3>
          <JsonBlock value={result.decision} label="Decision" />
        </div>
      </div>
    </Card>
  )
}

export function CaseDetailPage() {
  const { id = '' } = useParams()
  const { notify } = useToast()
  const fetcher = useCallback((signal: AbortSignal) => getCase(id, signal), [id])
  const { data: caseItem, error, loading, refresh, setData } = usePolling<Case>(fetcher, 10_000)
  const [busy, setBusy] = useState(false)
  const [workflowId, setWorkflowId] = useState<string | null>(null)

  const onProcess = async () => {
    setBusy(true)
    try {
      const response = await processCase(id)
      setData(() => (response.result ? { ...response.case, result: response.result } : response.case))
      setWorkflowId(response.workflow_id ?? null)
      notify(summariseProcessing(response))
    } catch (err) {
      notify({ tone: 'error', title: 'Processing failed', description: describeError(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Link to="/cases" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft className="size-4" aria-hidden /> All cases
      </Link>

      {error !== undefined && !caseItem && <ErrorState error={error} onRetry={() => void refresh()} />}
      {loading && <LoadingState label="Loading case…" />}

      {caseItem && (
        <>
          <PageHeader
            title={caseItem.subject || '(no subject)'}
            description={
              <span className="flex flex-wrap items-center gap-2">
                <CaseStatusBadge status={caseItem.status} />
                <span className="font-mono text-xs text-slate-500">{caseItem.external_id}</span>
              </span>
            }
            actions={
              <button type="button" className={buttonPrimary} onClick={() => void onProcess()} disabled={busy}>
                {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
                Process
              </button>
            }
          />

          <div className="space-y-6">
            {caseItem.hitl_item_id && (
              <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <ShieldCheck className="size-4" aria-hidden />
                <span>This case has a review item in the HITL queue.</span>
                <Link
                  to={`/hitl?item=${encodeURIComponent(caseItem.hitl_item_id)}`}
                  className="font-medium text-amber-900 underline underline-offset-2 hover:text-amber-700"
                >
                  Open HITL item
                </Link>
              </div>
            )}
            {workflowId && (
              <p className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
                Processing runs as workflow <span className="font-mono">{workflowId}</span>. This page refreshes as the
                case changes.
              </p>
            )}

            <Card className="p-5">
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="From">{caseItem.from_address || '—'}</Field>
                <Field label="Reason">
                  <span className="font-mono text-xs">{caseItem.reason}</span>
                </Field>
                <Field label="Intent">
                  <span className="font-mono text-xs">{caseItem.intent ?? '—'}</span>
                </Field>
                <Field label="Confidence">{formatConfidence(caseItem.confidence)}</Field>
                <Field label="Booking ref">
                  <span className="font-mono text-xs">{caseItem.booking_ref ?? '—'}</span>
                </Field>
                <Field label="Created">{formatDateTime(caseItem.created_at)}</Field>
                <Field label="Updated">{formatDateTime(caseItem.updated_at)}</Field>
                <Field label="Case id">
                  <span className="font-mono text-xs">{caseItem.id}</span>
                </Field>
              </dl>
              <div className="mt-5 border-t border-slate-100 pt-4">
                <h2 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Description</h2>
                <p className="text-sm whitespace-pre-wrap text-slate-800">{caseItem.description || '(empty)'}</p>
              </div>
            </Card>

            {caseItem.result ? (
              <ResultPanel result={caseItem.result} />
            ) : (
              <p className="text-sm text-slate-500">Not processed yet. Use Process to run the pipeline on this case.</p>
            )}
          </div>
        </>
      )}
    </>
  )
}
