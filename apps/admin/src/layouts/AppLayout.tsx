import { Bot, Inbox, LayoutDashboard, MessageSquare, Navigation, ScrollText, ShieldCheck, type LucideIcon } from 'lucide-react'
import { useCallback } from 'react'
import { NavLink, Outlet } from 'react-router'
import { describeError, getRuntimeConfig } from '../api/client'
import { Badge } from '../components/Badge'
import { usePolling } from '../hooks/usePolling'
import { configBadges } from '../lib/runtimeConfig'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/cases', label: 'Cases', icon: Inbox },
  { to: '/hitl', label: 'HITL queue', icon: ShieldCheck },
  { to: '/agents', label: 'Agents & Tools', icon: Bot },
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/audit', label: 'Audit log', icon: ScrollText },
]

function ConfigBar() {
  const fetcher = useCallback((signal: AbortSignal) => getRuntimeConfig(signal), [])
  const { data, error } = usePolling(fetcher, 30_000)

  if (error && !data) {
    return (
      <p role="alert" className="text-xs font-medium text-rose-700">
        {describeError(error)}
      </p>
    )
  }
  if (!data) return <p className="text-xs text-slate-400">Loading runtime config…</p>

  return (
    <ul aria-label="Runtime configuration" className="flex flex-wrap items-center gap-2">
      {configBadges(data).map((badge) => (
        <li key={badge.key}>
          <Badge tone={badge.tone} title={badge.hint}>
            <span className="text-current/70">{badge.label}</span>
            <span className="font-semibold">{badge.value}</span>
          </Badge>
        </li>
      ))}
      <li className="text-xs text-slate-400">v{data.version}</li>
    </ul>
  )
}

export function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-5">
          <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-white">
            <Navigation className="size-4" aria-hidden />
          </span>
          <span className="text-base font-semibold tracking-tight text-slate-900">casepilot</span>
        </div>
        <nav aria-label="Main" className="flex-1 overflow-y-auto p-3">
          <ul className="space-y-0.5">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`
                  }
                >
                  <Icon className="size-4" aria-hidden />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <p className="border-t border-slate-200 px-5 py-3 text-xs text-slate-400">Operator console</p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-end gap-4 border-b border-slate-200 bg-white/90 px-6 backdrop-blur">
          <ConfigBar />
        </header>
        <main className="min-w-0 flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
