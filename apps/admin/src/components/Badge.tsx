import type { ReactNode } from 'react'
import { caseStatusStyle, hitlStatusStyle, toneClasses, type BadgeTone } from '../lib/status'

interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  title?: string
}

export function Badge({ tone = 'slate', children, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${toneClasses(tone)}`}
    >
      {children}
    </span>
  )
}

export function CaseStatusBadge({ status }: { status: string }) {
  const style = caseStatusStyle(status)
  return (
    <Badge tone={style.tone} title={`Case status: ${status}`}>
      {style.label}
    </Badge>
  )
}

export function HitlStatusBadge({ status }: { status: string }) {
  const style = hitlStatusStyle(status)
  return (
    <Badge tone={style.tone} title={`Review status: ${status}`}>
      {style.label}
    </Badge>
  )
}

export function OperationBadge({ operation }: { operation: 'read' | 'write' }) {
  return <Badge tone={operation === 'write' ? 'amber' : 'sky'}>{operation === 'write' ? 'Write' : 'Read'}</Badge>
}
