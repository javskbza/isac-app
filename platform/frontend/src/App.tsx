import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import SourcesPage from './pages/SourcesPage'
import { useAuthStore } from './store/authStore'

export default function App() {
  const { token } = useAuthStore()
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={token ? <DashboardPage /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/sources"
        element={token ? <SourcesPage /> : <Navigate to="/login" replace />}
      />
      <Route path="/" element={<Navigate to={token ? '/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
