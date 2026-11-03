import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../providers/AuthProvider.jsx'

export default function ProtectedRoute({ children }) {
  const { ready, user } = useAuth()
  const location = useLocation()
  if (!ready) return <main className="grid min-h-screen place-items-center bg-slate-50 text-sm text-slate-500">Restoring your session…</main>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}
