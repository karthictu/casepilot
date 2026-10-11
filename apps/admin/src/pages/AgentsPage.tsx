import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment, useCallback, useState } from 'react'
import { listAgents, listTools } from '../api/client'
import type { AgentInfo, ToolInfo } from '../api/types'
import { Badge, OperationBadge } from '../components/Badge'
import { JsonBlock } from '../components/JsonBlock'
import { Card, PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { usePolling } from '../hooks/usePolling'
import { formatConfidence } from '../lib/format'

async function loadRegistry(signal: AbortSignal) {
  const [agents, tools] = await Promise.all([listAgents(signal), listTools(signal)])
  return { agents: agents.items, tools: tools.items }
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{agent.display_name}</h3>
          <p className="font-mono text-xs text-slate-500">
            {agent.agent_id} · v{agent.version}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Badge tone={agent.write_capable ? 'amber' : 'sky'}>{agent.write_capable ? 'Write-capable' : 'Read-only'}</Badge>
          {agent.requires_hitl && <Badge tone="violet">HITL</Badge>}
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-600">{agent.description}</p>
      <dl className="mt-4 space-y-3 text-sm">
        <div>
          <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">Intents</dt>
          <dd className="mt-1 flex flex-wrap gap-1">
            {agent.intents.length ? agent.intents.map((i) => <Badge key={i} tone="indigo">{i}</Badge>) : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">Scopes</dt>
          <dd className="mt-1 flex flex-wrap gap-1">
            {agent.scopes.length ? agent.scopes.map((s) => <Badge key={s}>{s}</Badge>) : '—'}
          </dd>
        </div>
        <div className="flex gap-6">
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">HITL threshold</dt>
            <dd className="mt-0.5 text-slate-800">{formatConfidence(agent.hitl_confidence_threshold)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">Owner</dt>
            <dd className="mt-0.5 text-slate-800">{agent.owner_team || '—'}</dd>
          </div>
        </div>
      </dl>
    </Card>
  )
}

function ToolTable({ tools }: { tools: ToolInfo[] }) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())
  const toggle = (name: string) =>
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })

  return (
    <Card className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <caption className="sr-only">Registered tools</caption>
        <thead className="bg-slate-50 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
          <tr>
            <th scope="col" className="w-8 px-3 py-2.5"><span className="sr-only">Schema</span></th>
            <th scope="col" className="px-3 py-2.5">Name</th>
            <th scope="col" className="px-3 py-2.5">Type</th>
            <th scope="col" className="px-3 py-2.5">MCP scope</th>
            <th scope="col" className="px-3 py-2.5">Agent scopes</th>
            <th scope="col" className="px-3 py-2.5">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tools.map((tool) => {
            const expanded = open.has(tool.name)
            return (
              <Fragment key={tool.name}>
                <tr className="align-top hover:bg-slate-50">
                  <td className="px-3 py-2.5">
                    <button
                      type="button"
                      aria-expanded={expanded}
                      aria-label={`${expanded ? 'Hide' : 'Show'} parameter schema for ${tool.name}`}
                      onClick={() => toggle(tool.name)}
                      className="rounded p-0.5 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
                    >
                      {expanded ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
                    </button>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs font-medium text-slate-900">{tool.name}</td>
                  <td className="px-3 py-2.5">
                    <OperationBadge operation={tool.operation_type} />
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-700">{tool.scope ?? '—'}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {tool.agent_scopes.map((s) => (
                        <Badge key={s}>{s}</Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-slate-600">{tool.description}</td>
                </tr>
                {expanded && (
                  <tr>
                    <td />
                    <td colSpan={5} className="px-3 pb-4">
                      <JsonBlock value={tool.parameters} label={`Parameter schema for ${tool.name}`} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}

export function AgentsPage() {
  const fetcher = useCallback((signal: AbortSignal) => loadRegistry(signal), [])
  const { data, error, loading, refresh } = usePolling(fetcher, null)

  return (
    <>
      <PageHeader
        title="Agents & Tools"
        description="What the platform has registered. MCP callers only see the tools whose scope their token holds; write tools always route through HITL."
      />
      {error !== undefined && <ErrorState error={error} onRetry={() => void refresh()} />}
      {loading && <LoadingState />}
      {data && (
        <div className="space-y-8">
          <section aria-labelledby="agents-heading">
            <h2 id="agents-heading" className="mb-3 text-sm font-semibold text-slate-900">
              Agents ({data.agents.length})
            </h2>
            {data.agents.length === 0 ? (
              <EmptyState title="No agents registered" />
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {data.agents.map((agent) => (
                  <AgentCard key={agent.agent_id} agent={agent} />
                ))}
              </div>
            )}
          </section>
          <section aria-labelledby="tools-heading">
            <h2 id="tools-heading" className="mb-3 text-sm font-semibold text-slate-900">
              Tools ({data.tools.length})
            </h2>
            {data.tools.length === 0 ? <EmptyState title="No tools registered" /> : <ToolTable tools={data.tools} />}
          </section>
        </div>
      )}
    </>
  )
}
