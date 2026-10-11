import { ChevronDown, ChevronRight } from 'lucide-react'
import { useId, useState } from 'react'
import { prettyJson } from '../lib/format'

interface JsonBlockProps {
  value: unknown
  /** Screen-reader label for the code region. */
  label?: string
  className?: string
}

export function JsonBlock({ value, label, className = '' }: JsonBlockProps) {
  return (
    <pre
      aria-label={label}
      className={`max-h-96 overflow-auto rounded-lg bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100 ${className}`}
    >
      <code>{prettyJson(value)}</code>
    </pre>
  )
}

interface CollapsibleJsonProps {
  value: unknown
  summary: string
  defaultOpen?: boolean
}

/** A disclosure button that reveals a JSON block. */
export function CollapsibleJson({ value, summary, defaultOpen = false }: CollapsibleJsonProps) {
  const [open, setOpen] = useState(defaultOpen)
  const regionId = useId()
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded text-xs font-medium text-indigo-700 hover:text-indigo-900 focus-visible:outline-2 focus-visible:outline-indigo-500"
      >
        {open ? <ChevronDown className="size-3.5" aria-hidden /> : <ChevronRight className="size-3.5" aria-hidden />}
        {summary}
      </button>
      {open && (
        <div id={regionId} className="mt-2">
          <JsonBlock value={value} label={summary} />
        </div>
      )}
    </div>
  )
}
