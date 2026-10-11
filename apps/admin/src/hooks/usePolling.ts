import { useCallback, useEffect, useRef, useState } from 'react'

export interface PollingState<T> {
  data: T | undefined
  error: unknown
  /** True until the first response (or error) arrives. */
  loading: boolean
  /** Fetch now, outside the interval. Resolves once state is updated. */
  refresh: () => Promise<void>
  /** Replace the data locally, e.g. after a mutation returns the updated record. */
  setData: (update: (current: T | undefined) => T | undefined) => void
}

interface Snapshot<T> {
  data: T | undefined
  error: unknown
}

/**
 * Load data with `fetcher` and refresh it every `intervalMs` milliseconds.
 * Pass `null` as the interval to fetch once (plus manual `refresh()` calls).
 *
 * `fetcher` should be memoised (`useCallback`): a new identity means "the query
 * changed", which triggers an immediate refetch and drops out-of-date responses.
 * Ticks are skipped while the tab is hidden.
 */
export function usePolling<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number | null = 5000,
): PollingState<T> {
  const [snapshot, setSnapshot] = useState<Snapshot<T>>({ data: undefined, error: undefined })
  const fetcherRef = useRef(fetcher)
  const sequence = useRef(0)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    fetcherRef.current = fetcher
  }, [fetcher])

  const run = useCallback(async (current: (signal: AbortSignal) => Promise<T>) => {
    const ticket = ++sequence.current
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    try {
      const data = await current(abort.signal)
      if (ticket === sequence.current) setSnapshot({ data, error: undefined })
    } catch (error) {
      if (abort.signal.aborted) return
      if (ticket === sequence.current) setSnapshot((prev) => ({ data: prev.data, error }))
    }
  }, [])

  useEffect(() => {
    void run(fetcher)
    if (intervalMs === null) return
    const id = window.setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return
      void run(fetcherRef.current)
    }, intervalMs)
    return () => window.clearInterval(id)
  }, [fetcher, intervalMs, run])

  useEffect(
    () => () => {
      sequence.current++
      controller.current?.abort()
    },
    [],
  )

  const refresh = useCallback(() => run(fetcherRef.current), [run])

  const setData = useCallback((update: (current: T | undefined) => T | undefined) => {
    setSnapshot((prev) => ({ ...prev, data: update(prev.data) }))
  }, [])

  return {
    data: snapshot.data,
    error: snapshot.error,
    loading: snapshot.data === undefined && snapshot.error === undefined,
    refresh,
    setData,
  }
}
