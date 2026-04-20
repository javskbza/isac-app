import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import SourcesPage from './pages/SourcesPage'
import AgentLogPage from './pages/AgentLogPage'
import Navbar from './components/Navbar'
import ErrorBoundary from './components/ErrorBoundary'
import { useAuthStore } from './store/authStore'

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

export default function App() {
  const { token } = useAuthStore()
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/dashboard"
        element={token ? <AuthenticatedLayout><DashboardPage /></AuthenticatedLayout> : <Navigate to="/login" replace />}
      />
      <Route
        path="/sources"
        element={token ? <AuthenticatedLayout><SourcesPage /></AuthenticatedLayout> : <Navigate to="/login" replace />}
      />
      <Route
        path="/agents"
        element={token ? <AuthenticatedLayout><AgentLogPage /></AuthenticatedLayout> : <Navigate to="/login" replace />}
      />
      <Route path="/" element={<Navigate to={token ? '/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
