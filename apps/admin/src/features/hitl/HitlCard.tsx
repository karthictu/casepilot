import { Check, LoaderCircle, Pencil, TriangleAlert, X } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router'
import { errorDetail, reviewHitl } from '../../api/client'
import type { HitlItem, ReviewDecision, ReviewRequest, ToolInfo } from '../../api/types'
import { Badge, HitlStatusBadge } from '../../components/Badge'
import { buttonDanger, buttonSecondary, buttonSmall, buttonSuccess, inputClass } from '../../components/buttons'
import { CollapsibleJson, JsonBlock } from '../../components/JsonBlock'
import { Card } from '../../components/PageHeader'
import { useToast } from '../../components/toast-context'
import { formatConfidence, formatDateTime, prettyJson, shortId } from '../../lib/format'
import {
  callContext,
  needsCall,
  originalCall,
  parseArguments,
  proposedArguments,
  proposedTool,
  skeletonForTool,
} from '../../lib/hitlCall'
import { hitlStatusStyle } from '../../lib/status'

export interface HitlCardProps {
  item: HitlItem
  /** Write tools from `GET /api/tools`, offered in the call editor. */
  writeTools: ToolInfo[]
  /** Set when the tool list could not be loaded. */
  toolsError?: string
  highlighted?: boolean
  onReviewed: (item: HitlItem) => void
}

function initialArgumentsText(item: HitlItem, tools: ToolInfo[]): string {
  const args = proposedArguments(item)
  if (args) return prettyJson(args)
  const tool = proposedTool(item)
  return prettyJson(tool ? skeletonForTool(tools, tool) : {})
}

function ContextPanel({ context }: { context: Record<string, unknown> }) {
  const subject = typeof context.subject === 'string' ? context.subject : null
  const query = typeof context.query === 'string' ? context.query : null
  return (
    <section aria-label="Context" className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Context</h3>
      {subject && (
        <p className="mb-1 text-sm text-slate-800">
          <span className="font-medium">Case subject:</span> {subject}
        </p>
      )}
      {query && (
        <p className="mb-1 text-sm text-slate-800">
          <span className="font-medium">Query:</span> {query}
        </p>
      )}
      <JsonBlock value={context} label="Context details" className="mt-2 max-h-64" />
    </section>
  )
}

export function HitlCard({ item, writeTools, toolsError, highlighted = false, onReviewed }: HitlCardProps) {
  const { notify } = useToast()
  const noteId = useId()
  const toolId = useId()
  const argsId = useId()
  const argsErrorId = useId()

  const mustProvideCall = needsCall(item)
  const [note, setNote] = useState('')
  const [editing, setEditing] = useState(mustProvideCall)
  const [tool, setTool] = useState(proposedTool(item) ?? '')
  const [argsText, setArgsText] = useState(() => initialArgumentsText(item, writeTools))
  const [argsEdited, setArgsEdited] = useState(false)
  const [submitting, setSubmitting] = useState<ReviewDecision | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)

  const parsed = parseArguments(argsText)
  const callReady = tool !== '' && parsed.ok
  // Without corrections the proposed call runs as is; a manual_review item has none.
  const approveBlocked = (editing || mustProvideCall) && !callReady

  const toolOptions = writeTools.map((t) => t.name)
  if (tool && !toolOptions.includes(tool)) toolOptions.unshift(tool)

  const onToolChange = (next: string) => {
    setTool(next)
    if (argsEdited) return
    // Until the operator types, keep the arguments in step with the chosen tool.
    const proposed = proposedArguments(item)
    setArgsText(prettyJson(proposed && next === proposedTool(item) ? proposed : skeletonForTool(writeTools, next)))
  }

  const submit = async (decision: ReviewDecision) => {
    setSubmitting(decision)
    setReviewError(null)
    const review: ReviewRequest = { decision, note }
    if (decision === 'approve' && editing && parsed.ok) {
      review.tool = tool
      review.arguments = parsed.value
    }
    try {
      const updated = await reviewHitl(item.id, review)
      onReviewed(updated)
      notify({
        tone: updated.status === 'failed' ? 'error' : decision === 'approve' ? 'success' : 'info',
        title: `${decision === 'approve' ? 'Approved' : 'Rejected'}: ${item.action}`,
        description: `Item is now ${hitlStatusStyle(updated.status).label.toLowerCase()}.`,
      })
    } catch (err) {
      setReviewError(errorDetail(err))
    } finally {
      setSubmitting(null)
    }
  }

  const pending = item.status === 'pending'
  const caseLink = item.source === 'case' && item.source_ref
  const context = callContext(item)
  const original = originalCall(item)

  return (
    <Card className={`p-5 ${highlighted ? 'ring-2 ring-indigo-400' : ''}`}>
      <article aria-label={`HITL item ${item.action}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-900">
              <span className="font-mono">{item.action}</span>
              <HitlStatusBadge status={item.status} />
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              {formatDateTime(item.created_at)} · id <span className="font-mono">{shortId(item.id)}</span>
              {item.workflow_id && (
                <>
                  {' '}
                  · workflow <span className="font-mono">{item.workflow_id}</span>
                </>
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="indigo" title="Where the request came from">
              source: {item.source}
            </Badge>
            <Badge title="Agent that proposed the action">agent: {item.agent_id}</Badge>
            <Badge title="Confidence of the proposed action">confidence: {formatConfidence(item.confidence)}</Badge>
          </div>
        </div>

        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">Reason</dt>
            <dd className="mt-0.5 text-slate-800">{item.reason || '—'}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">Source ref</dt>
            <dd className="mt-0.5 font-mono text-xs text-slate-800">
              {caseLink ? (
                <Link to={`/cases/${item.source_ref}`} className="text-indigo-700 hover:text-indigo-900">
                  {item.source_ref}
                </Link>
              ) : (
                item.source_ref || '—'
              )}
            </dd>
          </div>
        </dl>

        {context && (
          <div className="mt-4">
            <ContextPanel context={context} />
          </div>
        )}

        <div className="mt-4">
          {context ? (
            // The context panel already shows what matters; keep the raw payload one click away.
            <CollapsibleJson value={item.payload} summary="Full payload" />
          ) : (
            <>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Payload</h3>
              <JsonBlock value={item.payload} label={`Payload for ${item.action}`} />
            </>
          )}
        </div>

        {!pending && (
          <div className="mt-4 space-y-2 border-t border-slate-100 pt-4 text-sm">
            <p className="text-slate-700">
              Reviewed {item.reviewer ? <>by <strong>{item.reviewer}</strong> </> : ''}
              {item.reviewed_at && <>on {formatDateTime(item.reviewed_at)}</>}
            </p>
            {item.status === 'approved' && (
              <p className="text-slate-600">The workflow is executing the approved call; the status updates when it finishes.</p>
            )}
            {item.reviewer_note && <p className="text-slate-600 italic">“{item.reviewer_note}”</p>}
            {original !== null && <CollapsibleJson value={original} summary="Originally proposed call" />}
            {item.result && <CollapsibleJson value={item.result} summary="Execution result" defaultOpen />}
          </div>
        )}

        {pending && (
          <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
            {mustProvideCall ? (
              <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                No executable call was proposed. Choose a tool and its arguments to approve, or reject the item.
              </p>
            ) : (
              <button
                type="button"
                aria-expanded={editing}
                onClick={() => setEditing((v) => !v)}
                className={`${buttonSecondary} ${buttonSmall}`}
              >
                <Pencil className="size-3.5" aria-hidden />
                {editing ? 'Cancel edit' : 'Edit call'}
              </button>
            )}

            {editing && (
              <fieldset className="space-y-3 rounded-lg border border-slate-200 p-3">
                <legend className="px-1 text-xs font-semibold text-slate-600">Call to execute on approval</legend>
                <div>
                  <label htmlFor={toolId} className="mb-1 block text-xs font-medium text-slate-600">
                    Tool
                  </label>
                  <select
                    id={toolId}
                    value={tool}
                    onChange={(e) => onToolChange(e.target.value)}
                    className={`${inputClass} w-full font-mono`}
                  >
                    <option value="">Choose a write tool…</option>
                    {toolOptions.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  {toolsError && <p className="mt-1 text-xs text-rose-700">Could not load tools: {toolsError}</p>}
                </div>
                <div>
                  <label htmlFor={argsId} className="mb-1 block text-xs font-medium text-slate-600">
                    Arguments (JSON)
                  </label>
                  <textarea
                    id={argsId}
                    rows={8}
                    spellCheck={false}
                    value={argsText}
                    onChange={(e) => {
                      setArgsText(e.target.value)
                      setArgsEdited(true)
                    }}
                    aria-invalid={!parsed.ok}
                    aria-describedby={parsed.ok ? undefined : argsErrorId}
                    className={`${inputClass} w-full font-mono text-xs ${parsed.ok ? '' : 'ring-rose-400'}`}
                  />
                  {!parsed.ok && (
                    <p id={argsErrorId} className="mt-1 text-xs text-rose-700">
                      {parsed.error}
                    </p>
                  )}
                  {!mustProvideCall && (
                    <p className="mt-1 text-xs text-slate-500">These arguments replace the proposed ones.</p>
                  )}
                </div>
              </fieldset>
            )}

            <div>
              <label htmlFor={noteId} className="mb-1 block text-xs font-medium text-slate-600">
                Note (optional)
              </label>
              <textarea
                id={noteId}
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Why are you approving or rejecting?"
                className={`${inputClass} w-full`}
              />
            </div>

            {reviewError && (
              <p role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                {reviewError}
              </p>
            )}

            <div className="flex gap-2">
              <button
                type="button"
                className={buttonSuccess}
                disabled={submitting !== null || approveBlocked}
                title={approveBlocked ? 'Choose a tool and enter valid JSON arguments first' : undefined}
                onClick={() => void submit('approve')}
              >
                {submitting === 'approve' ? (
                  <LoaderCircle className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Check className="size-4" aria-hidden />
                )}
                Approve
              </button>
              <button
                type="button"
                className={buttonDanger}
                disabled={submitting !== null}
                onClick={() => void submit('reject')}
              >
                {submitting === 'reject' ? (
                  <LoaderCircle className="size-4 animate-spin" aria-hidden />
                ) : (
                  <X className="size-4" aria-hidden />
                )}
                Reject
              </button>
            </div>
          </div>
        )}
      </article>
    </Card>
  )
}
