import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { runtimeConfig } from '../test/fixtures'
import { jsonResponse, mockFetch, renderRoute } from '../test/utils'
import { AppLayout } from './AppLayout'

describe('AppLayout', () => {
  it('renders the wordmark and the main navigation', async () => {
    mockFetch({ 'GET /api/config': runtimeConfig })
    renderRoute(<AppLayout />)

    expect(screen.getByText('casepilot')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    for (const label of ['Dashboard', 'Cases', 'HITL queue', 'Agents & Tools', 'Chat', 'Audit log']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
    await screen.findByRole('list', { name: 'Runtime configuration' })
  })

  it('shows runtime config badges from /api/config', async () => {
    mockFetch({
      'GET /api/config': { ...runtimeConfig, write_mode: 'live', llm_provider: 'litellm', agent_runtime: 'adk', temporal_enabled: true },
    })
    renderRoute(<AppLayout />)

    const badges = await screen.findByRole('list', { name: 'Runtime configuration' })
    expect(within(badges).getByText('Writes').parentElement).toHaveTextContent('Writeslive')
    expect(within(badges).getByText('LLM').parentElement).toHaveTextContent('LLMlitellm')
    expect(within(badges).getByText('Runtime').parentElement).toHaveTextContent('Runtimeadk')
    expect(within(badges).getByText('Temporal').parentElement).toHaveTextContent('Temporalon')
    expect(within(badges).getByText('v0.1.0')).toBeInTheDocument()
  })

  it('shows shadow mode and temporal off', async () => {
    mockFetch({ 'GET /api/config': runtimeConfig })
    renderRoute(<AppLayout />)

    const badges = await screen.findByRole('list', { name: 'Runtime configuration' })
    expect(within(badges).getByText('shadow')).toBeInTheDocument()
    expect(within(badges).getByText('off')).toBeInTheDocument()
  })

  it('explains when the API is unreachable', async () => {
    mockFetch({ 'GET /api/config': () => jsonResponse(null, 503) })
    renderRoute(<AppLayout />)

    expect(await screen.findByRole('alert')).toHaveTextContent('API not reachable at')
  })
})
