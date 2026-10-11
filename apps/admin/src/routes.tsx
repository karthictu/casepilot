import type { RouteObject } from 'react-router'
import { AppLayout } from './layouts/AppLayout'
import { AgentsPage } from './pages/AgentsPage'
import { AuditPage } from './pages/AuditPage'
import { CaseDetailPage } from './pages/CaseDetailPage'
import { CasesPage } from './pages/CasesPage'
import { DashboardPage } from './pages/DashboardPage'
import { HitlPage } from './pages/HitlPage'
import { NotFoundPage } from './pages/NotFoundPage'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'cases', element: <CasesPage /> },
      { path: 'cases/:id', element: <CaseDetailPage /> },
      { path: 'hitl', element: <HitlPage /> },
      { path: 'agents', element: <AgentsPage /> },
      {
        // The chat runtime is the heaviest dependency; load it on first visit.
        path: 'chat',
        lazy: async () => ({ Component: (await import('./pages/ChatPage')).ChatPage }),
      },
      { path: 'audit', element: <AuditPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
