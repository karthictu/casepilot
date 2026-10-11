import { Inbox, LoaderCircle, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { describeError } from '../api/client'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 px-4 py-10 text-sm text-slate-500">
      <LoaderCircle className="size-4 animate-spin" aria-hidden />
      {label}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300 px-6 py-12 text-center">
      <Inbox className="size-6 text-slate-400" aria-hidden />
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {children && <div className="max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="flex-1">
        <p className="font-medium">{describeError(error)}</p>
        <p className="mt-0.5 text-rose-700/80">Check that the casepilot API is running and the proxy target is correct.</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md bg-white px-2.5 py-1 text-xs font-medium text-rose-800 ring-1 ring-rose-300 hover:bg-rose-100"
        >
          Retry
        </button>
      )}
    </div>
  )
}
