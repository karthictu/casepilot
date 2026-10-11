import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { vi, type Mock } from 'vitest'
import { ToastProvider } from '../components/ToastProvider'

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

type Handler = (url: URL, init: RequestInit) => unknown

/**
 * Stub `fetch` with a table of `"METHOD /path"` handlers. A handler's return
 * value is sent as a JSON 200 unless it is already a Response. Unmatched calls
 * fail loudly with a 404 so a test never silently depends on a missing route.
 */
export function mockFetch(handlers: Record<string, Handler | unknown>): Mock {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const key = `${(init.method ?? 'GET').toUpperCase()} ${url.pathname}`
    if (!(key in handlers)) return jsonResponse({ detail: `no mock for ${key}` }, 404)
    const handler = handlers[key]
    const value = typeof handler === 'function' ? (handler as Handler)(url, init) : handler
    return value instanceof Response ? value : jsonResponse(value)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Calls made to the fetch mock as `[method, path+search, parsed body]`. */
export function fetchCalls(fetchMock: Mock): [string, string, unknown][] {
  return fetchMock.mock.calls.map((call) => {
    const [input, init] = call as [RequestInfo | URL, RequestInit | undefined]
    const url = new URL(String(input), 'http://localhost')
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    return [(init?.method ?? 'GET').toUpperCase(), `${url.pathname}${url.search}`, body]
  })
}

/** Render `element` at `path` inside a memory router and the toast provider. */
export function renderRoute(element: ReactElement, { path = '/', url = path }: { path?: string; url?: string } = {}) {
  const routes: RouteObject[] = [
    { path, element },
    { path: '*', element: <p>other route</p> },
  ]
  const router = createMemoryRouter(routes, { initialEntries: [url] })
  return { router, ...render(<ToastProvider><RouterProvider router={router} /></ToastProvider>) }
}
