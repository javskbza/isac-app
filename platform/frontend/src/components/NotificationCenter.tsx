import { useEffect, useRef, useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import api from '@/lib/api'
import { useNotificationStore } from '@/store/notificationStore'

interface Notification {
  id: string
  title: string
  is_read: boolean
  created_at: string
  insight_id: string
}

const TYPE_ICONS: Record<string, string> = {
  anomaly: '🚨',
  forecast: '🔮',
  trend: '📈',
  pattern: '🔁',
  summary: '📋',
}

export default function NotificationCenter() {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const { setNotifications, markRead: markReadStore } = useNotificationStore()

  const { data: rawNotifications } = useQuery<Notification[]>({
    queryKey: ['notifications'],
    queryFn: async () => (await api.get('/notifications')).data,
    refetchInterval: 15_000, // poll every 15s
  })

  const notifications = useMemo(() => rawNotifications ?? [], [rawNotifications])

  useEffect(() => {
    setNotifications(notifications)
  }, [notifications, setNotifications])

  const unreadCount = notifications.filter((n) => !n.is_read).length

  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/notifications/${id}/read`),
    onSuccess: (_, id) => {
      markReadStore(id)
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-full p-2 hover:bg-accent transition-colors"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-80 rounded-lg border bg-card shadow-lg">
          <div className="border-b px-4 py-3">
            <h3 className="font-semibold text-sm">Notifications</h3>
            {unreadCount > 0 && (
              <p className="text-xs text-muted-foreground">{unreadCount} unread</p>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground text-center">No notifications yet</p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => { if (!n.is_read) markReadMutation.mutate(n.id) }}
                  className={`w-full text-left px-4 py-3 border-b last:border-0 hover:bg-accent/50 transition-colors ${n.is_read ? 'opacity-60' : 'bg-primary/5'}`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-base mt-0.5">💡</span>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm truncate ${!n.is_read ? 'font-semibold' : ''}`}>{n.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                    {!n.is_read && <span className="mt-1.5 h-2 w-2 rounded-full bg-primary flex-shrink-0" />}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
