import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import NotificationCenter from './NotificationCenter'
import { Button } from '@/components/ui/button'

export default function Navbar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav className="border-b bg-card px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/dashboard" className="font-bold text-lg">Data Intelligence</Link>
        <Link to="/dashboard" className="text-sm text-muted-foreground hover:text-foreground">Dashboard</Link>
        <Link to="/sources" className="text-sm text-muted-foreground hover:text-foreground">Sources</Link>
        <Link to="/agents" className="text-sm text-muted-foreground hover:text-foreground">Agent Log</Link>
      </div>
      <div className="flex items-center gap-3">
        <NotificationCenter />
        <span className="text-sm text-muted-foreground">{user?.email}</span>
        <Button variant="outline" size="sm" onClick={handleLogout}>Logout</Button>
      </div>
    </nav>
  )
}
