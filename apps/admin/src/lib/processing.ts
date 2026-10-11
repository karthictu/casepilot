import type { ProcessCaseResponse } from '../api/types'
import type { ToastInput } from '../components/toast-context'
import { caseStatusStyle } from './status'

/** Turn a `POST /api/cases/{id}/process` response into a one-line notification. */
export function summariseProcessing(response: ProcessCaseResponse): ToastInput {
  if (response.workflow_id) {
    return {
      tone: 'info',
      title: 'Processing started as a workflow',
      description: `Workflow ${response.workflow_id}. The case status updates when it finishes.`,
    }
  }

  const result = response.result
  if (!result) {
    return { tone: 'info', title: `Case is ${caseStatusStyle(response.case.status).label.toLowerCase()}` }
  }

  const shadow = result.shadow ? ' (shadow run, nothing was written)' : ''
  if (result.needs_hitl || result.status === 'hitl_required') {
    return {
      tone: 'warning',
      title: 'Sent to the HITL queue',
      description: `${result.hitl_reason || 'Needs operator review'}${shadow}`,
    }
  }
  if (result.status === 'booked') {
    return {
      tone: 'success',
      title: result.booking_ref ? `Booked ${result.booking_ref}` : 'Booked',
      description: `Intent ${result.intent}${shadow}`,
    }
  }
  if (result.status === 'failed') {
    return { tone: 'error', title: 'Processing failed', description: result.hitl_reason || undefined }
  }
  return {
    tone: 'info',
    title: `Case is ${caseStatusStyle(result.status).label.toLowerCase()}`,
    description: `Intent ${result.intent || 'unknown'}${shadow}`,
  }
}
