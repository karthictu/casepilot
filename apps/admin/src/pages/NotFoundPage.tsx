import { Link } from 'react-router'
import { EmptyState } from '../components/States'

export function NotFoundPage() {
  return (
    <EmptyState title="Page not found">
      <Link to="/" className="font-medium text-indigo-700 hover:text-indigo-900">
        Back to the dashboard
      </Link>
    </EmptyState>
  )
}
