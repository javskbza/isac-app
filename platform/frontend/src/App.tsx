import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import SourcesPage from './pages/SourcesPage'
import AgentLogPage from './pages/AgentLogPage'
import AccountManagementPage from './pages/AccountManagementPage'
import Navbar from './components/Navbar'
import ErrorBoundary from './components/ErrorBoundary'
import { useAuthStore } from './store/authStore'

function ForbiddenPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center">
        <p className="text-4xl font-bold text-muted-foreground">403</p>
        <p className="text-lg mt-2">You don't have permission to view this page.</p>
      </div>
    </div>
  )
}

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </div>
  )
}

function ProtectedRoute({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { token, user } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  if (adminOnly && user?.role !== 'admin') {
    return <AuthenticatedLayout><ForbiddenPage /></AuthenticatedLayout>
  }
  return <AuthenticatedLayout>{children}</AuthenticatedLayout>
}

export default function App() {
  const { token } = useAuthStore()
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/sources" element={<ProtectedRoute><SourcesPage /></ProtectedRoute>} />
      <Route path="/agents" element={<ProtectedRoute><AgentLogPage /></ProtectedRoute>} />
      <Route path="/account-management" element={<ProtectedRoute adminOnly><AccountManagementPage /></ProtectedRoute>} />
      <Route path="/" element={<Navigate to={token ? '/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
