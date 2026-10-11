import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { usePolling } from './usePolling'

afterEach(() => {
  vi.useRealTimers()
})

describe('usePolling', () => {
  it('loads immediately, then refreshes on the interval', async () => {
    vi.useFakeTimers()
    let n = 0
    const fetcher = vi.fn(async () => ++n)
    const { result } = renderHook(() => usePolling(fetcher, 5000))

    expect(result.current.loading).toBe(true)
    await act(async () => {})
    expect(result.current.data).toBe(1)
    expect(result.current.loading).toBe(false)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(result.current.data).toBe(2)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('stops polling on unmount', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn(async () => 'ok')
    const { unmount } = renderHook(() => usePolling(fetcher, 5000))
    await act(async () => {})
    unmount()

    await vi.advanceTimersByTimeAsync(20_000)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('keeps the last good data when a refresh fails', async () => {
    const fetcher = vi.fn<() => Promise<string>>().mockResolvedValueOnce('first').mockRejectedValueOnce(new Error('boom'))
    const { result } = renderHook(() => usePolling(fetcher, null))
    await waitFor(() => expect(result.current.data).toBe('first'))

    await act(() => result.current.refresh())

    expect(result.current.data).toBe('first')
    expect(result.current.error).toEqual(new Error('boom'))
  })
})
