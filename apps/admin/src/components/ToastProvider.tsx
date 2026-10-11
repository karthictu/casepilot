import { CircleCheck, CircleX, Info, TriangleAlert, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type Toast, type ToastInput, type ToastTone } from './toast-context'

const TONE: Record<ToastTone, { classes: string; Icon: typeof Info }> = {
  info: { classes: 'border-slate-200', Icon: Info },
  success: { classes: 'border-emerald-200', Icon: CircleCheck },
  warning: { classes: 'border-amber-200', Icon: TriangleAlert },
  error: { classes: 'border-rose-200', Icon: CircleX },
}

const ICON_COLOUR: Record<ToastTone, string> = {
  info: 'text-indigo-600',
  success: 'text-emerald-600',
  warning: 'text-amber-600',
  error: 'text-rose-600',
}

const DISMISS_AFTER_MS = 6000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Map<number, number>())

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer !== undefined) window.clearTimeout(timer)
    timers.current.delete(id)
  }, [])

  const notify = useCallback(
    (input: ToastInput) => {
      const id = nextId.current++
      setToasts((list) => [...list.slice(-3), { id, tone: 'info', ...input }])
      timers.current.set(
        id,
        window.setTimeout(() => dismiss(id), DISMISS_AFTER_MS),
      )
    },
    [dismiss],
  )

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((timer) => window.clearTimeout(timer))
  }, [])

  const api = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((toast) => {
          const { classes, Icon } = TONE[toast.tone]
          return (
            <div
              key={toast.id}
              role="status"
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border bg-white p-3 shadow-lg ${classes}`}
            >
              <Icon className={`mt-0.5 size-4 shrink-0 ${ICON_COLOUR[toast.tone]}`} aria-hidden />
              <div className="min-w-0 flex-1 text-sm">
                <p className="font-medium text-slate-900">{toast.title}</p>
                {toast.description && <p className="mt-0.5 break-words text-slate-600">{toast.description}</p>}
              </div>
              <button
                type="button"
                aria-label="Dismiss notification"
                onClick={() => dismiss(toast.id)}
                className="rounded p-0.5 text-slate-400 hover:text-slate-700"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
