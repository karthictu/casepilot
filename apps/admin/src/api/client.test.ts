import { describe, expect, it } from 'vitest'
import { fetchCalls, jsonResponse, mockFetch } from '../test/utils'
import { ApiError, buildUrl, configureClient, describeError, listCases, reviewHitl } from './client'

describe('buildUrl', () => {
  it('joins the base URL and path, dropping empty query values', () => {
    configureClient({ baseUrl: 'https://api.example.com/' })
    expect(buildUrl('/api/cases', { status: 'new', limit: 100, event_type: '' })).toBe(
      'https://api.example.com/api/cases?status=new&limit=100',
    )
  })

  it('uses a same-origin path when no base URL is set', () => {
    configureClient({ baseUrl: '' })
    expect(buildUrl('api/audit', { limit: 10, event_type: undefined })).toBe('/api/audit?limit=10')
  })
})

describe('request', () => {
  it('sends no Authorization header without a token', async () => {
    configureClient({ baseUrl: '', token: undefined })
    const fetchMock = mockFetch({ 'GET /api/cases': { items: [], total: 0 } })

    await listCases({ status: 'booked' })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/cases?status=booked&limit=100')
    expect(init.headers).not.toHaveProperty('Authorization')
  })

  it('adds the bearer header when a token is configured', async () => {
    configureClient({ baseUrl: 'http://api.test', token: 'secret-token' })
    const fetchMock = mockFetch({ 'GET /api/cases': { items: [], total: 0 } })

    await listCases()

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://api.test/api/cases?limit=100')
    expect(init.headers).toMatchObject({ Authorization: 'Bearer secret-token' })
  })

  it('posts a JSON body and omits a blank review note', async () => {
    configureClient({ baseUrl: '' })
    const fetchMock = mockFetch({ 'POST /api/hitl/queue/h1/review': { id: 'h1', status: 'executed' } })

    await reviewHitl('h1', { decision: 'approve', note: '   ' })

    expect(fetchCalls(fetchMock)).toEqual([['POST', '/api/hitl/queue/h1/review', { decision: 'approve' }]])
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json' })
  })

  it('throws an ApiError carrying the status and parsed body on non-2xx', async () => {
    configureClient({ baseUrl: '' })
    mockFetch({ 'GET /api/cases': () => jsonResponse({ detail: 'case source unavailable' }, 422) })

    const error = await listCases().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, body: { detail: 'case source unavailable' } })
    expect(describeError(error)).toBe('422: case source unavailable')
  })

  it('reports a network failure as "API not reachable"', async () => {
    configureClient({ baseUrl: 'http://api.test' })
    mockFetch({})
    const fetchMock = globalThis.fetch as unknown as { mockRejectedValueOnce: (e: unknown) => void }
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    const error = await listCases().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect(describeError(error)).toBe('API not reachable at http://api.test')
  })
})
