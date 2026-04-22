import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useAuthStore } from '@/store/authStore'
import api from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface UserRow {
  id: string
  email: string
  full_name: string | null
  role: 'admin' | 'viewer'
  status: 'active' | 'disabled'
  created_at: string
  updated_at: string | null
}

interface AuditEntry {
  id: string
  timestamp: string
  actor_email: string
  target_email: string
  action: string
  before_value: Record<string, unknown> | null
  after_value: Record<string, unknown> | null
  ip_address: string | null
}

// ---------------------------------------------------------------------------
// Role + Status badges
// ---------------------------------------------------------------------------
function RoleBadge({ role }: { role: string }) {
  return (
    <Badge variant={role === 'admin' ? 'default' : 'secondary'}>
      {role}
    </Badge>
  )
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={status === 'active' ? 'success' : 'muted'}>
      {status}
    </Badge>
  )
}

// ---------------------------------------------------------------------------
// Create User modal
// ---------------------------------------------------------------------------
function CreateUserModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<'admin' | 'viewer'>('viewer')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => api.post('/api/users', { email, password, full_name: fullName, role }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to create user'),
  })

  return (
    <DialogContent className="max-w-md">
      <DialogHeader>
        <DialogTitle>Create User</DialogTitle>
      </DialogHeader>
      <div className="space-y-4">
        <div className="space-y-1">
          <Label>Email</Label>
          <Input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="user@example.com" />
        </div>
        <div className="space-y-1">
          <Label>Full Name (optional)</Label>
          <Input value={fullName} onChange={e => setFullName(e.target.value)} placeholder="Jane Doe" />
        </div>
        <div className="space-y-1">
          <Label>Initial Password</Label>
          <Input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <div className="space-y-1">
          <Label>Role</Label>
          <Select value={role} onValueChange={v => setRole(v as 'admin' | 'viewer')}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="viewer">Viewer</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      <DialogFooter className="mt-4">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || !email || !password}>
          {mutation.isPending ? 'Creating…' : 'Create User'}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}

// ---------------------------------------------------------------------------
// Edit User modal
// ---------------------------------------------------------------------------
function EditUserModal({ user, onClose }: { user: UserRow; onClose: () => void }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState(user.email)
  const [fullName, setFullName] = useState(user.full_name ?? '')
  const [role, setRole] = useState(user.role)
  const [status, setStatus] = useState(user.status)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => api.patch(`/api/users/${user.id}`, {
      email: email !== user.email ? email : undefined,
      full_name: fullName !== user.full_name ? fullName : undefined,
      role: role !== user.role ? role : undefined,
      status: status !== user.status ? status : undefined,
      password: password || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to update user'),
  })

  return (
    <DialogContent className="max-w-md">
      <DialogHeader>
        <DialogTitle>Edit User</DialogTitle>
      </DialogHeader>
      <div className="space-y-4">
        <div className="space-y-1">
          <Label>Email</Label>
          <Input type="email" value={email} onChange={e => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Full Name</Label>
          <Input value={fullName} onChange={e => setFullName(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Role</Label>
          <Select value={role} onValueChange={v => setRole(v as 'admin' | 'viewer')}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="viewer">Viewer</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>Status</Label>
          <Select value={status} onValueChange={v => setStatus(v as 'active' | 'disabled')}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="disabled">Disabled</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>Reset Password (leave blank to keep current)</Label>
          <Input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="New password…" />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      <DialogFooter className="mt-4">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : 'Save Changes'}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}

// ---------------------------------------------------------------------------
// Delete confirmation
// ---------------------------------------------------------------------------
function DeleteConfirmModal({ user, onClose }: { user: UserRow; onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => api.delete(`/api/users/${user.id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to delete user'),
  })

  return (
    <DialogContent className="max-w-sm">
      <DialogHeader>
        <DialogTitle>Delete User</DialogTitle>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        Permanently delete <strong>{user.email}</strong>? This cannot be undone.
      </p>
      {error && <p className="text-sm text-destructive mt-2">{error}</p>}
      <DialogFooter className="mt-4">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button variant="destructive" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? 'Deleting…' : 'Delete'}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}

// ---------------------------------------------------------------------------
// Users tab
// ---------------------------------------------------------------------------
function UsersTab() {
  const { user: me } = useAuthStore()
  const [createOpen, setCreateOpen] = useState(false)
  const [editUser, setEditUser] = useState<UserRow | null>(null)
  const [deleteUser, setDeleteUser] = useState<UserRow | null>(null)

  const { data: users = [], isLoading } = useQuery<UserRow[]>({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users').then(r => r.data),
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-muted-foreground">{users.length} user{users.length !== 1 ? 's' : ''}</p>
        <Button size="sm" onClick={() => setCreateOpen(true)}>New User</Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="rounded-md border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Email</th>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Role</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-left px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-t border-border hover:bg-muted/30">
                  <td className="px-4 py-2">{u.email} {u.id === me?.id && <span className="text-xs text-muted-foreground">(you)</span>}</td>
                  <td className="px-4 py-2 text-muted-foreground">{u.full_name ?? '—'}</td>
                  <td className="px-4 py-2"><RoleBadge role={u.role} /></td>
                  <td className="px-4 py-2"><StatusBadge status={u.status} /></td>
                  <td className="px-4 py-2 text-muted-foreground">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2 justify-end">
                      <Button size="sm" variant="outline" onClick={() => setEditUser(u)}>Edit</Button>
                      <Button size="sm" variant="destructive" onClick={() => setDeleteUser(u)}>Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={open => !open && setCreateOpen(false)}>
        {createOpen && <CreateUserModal onClose={() => setCreateOpen(false)} />}
      </Dialog>
      <Dialog open={!!editUser} onOpenChange={open => !open && setEditUser(null)}>
        {editUser && <EditUserModal user={editUser} onClose={() => setEditUser(null)} />}
      </Dialog>
      <Dialog open={!!deleteUser} onOpenChange={open => !open && setDeleteUser(null)}>
        {deleteUser && <DeleteConfirmModal user={deleteUser} onClose={() => setDeleteUser(null)} />}
      </Dialog>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Audit Log tab
// ---------------------------------------------------------------------------
function AuditLogTab() {
  const [actorFilter, setActorFilter] = useState('')
  const [targetFilter, setTargetFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)

  const params = new URLSearchParams()
  if (actorFilter) params.set('actor_id', actorFilter)
  if (targetFilter) params.set('target_id', targetFilter)
  if (actionFilter) params.set('action', actionFilter)
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  params.set('page', String(page))
  params.set('page_size', '50')

  const { data: logs = [], isLoading } = useQuery<AuditEntry[]>({
    queryKey: ['audit-log', actorFilter, targetFilter, actionFilter, dateFrom, dateTo, page],
    queryFn: () => api.get(`/api/users/audit-log?${params.toString()}`).then(r => r.data),
  })

  const ACTION_OPTIONS = ['create', 'modify_email', 'modify_role', 'modify_status', 'reset_password', 'delete']

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-4">
        <Input className="w-40" placeholder="Filter by action…" value={actionFilter}
          onChange={e => { setActionFilter(e.target.value); setPage(1) }}
          list="action-options"
        />
        <datalist id="action-options">
          {ACTION_OPTIONS.map(a => <option key={a} value={a} />)}
        </datalist>
        <Input className="w-56" placeholder="Date from (ISO)…" type="datetime-local" value={dateFrom}
          onChange={e => { setDateFrom(e.target.value); setPage(1) }} />
        <Input className="w-56" placeholder="Date to (ISO)…" type="datetime-local" value={dateTo}
          onChange={e => { setDateTo(e.target.value); setPage(1) }} />
        <Button variant="outline" size="sm" onClick={() => { setActionFilter(''); setDateFrom(''); setDateTo(''); setPage(1) }}>
          Clear
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div className="rounded-md border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Timestamp</th>
                  <th className="text-left px-4 py-2 font-medium">Actor</th>
                  <th className="text-left px-4 py-2 font-medium">Action</th>
                  <th className="text-left px-4 py-2 font-medium">Target</th>
                  <th className="text-left px-4 py-2 font-medium">Before</th>
                  <th className="text-left px-4 py-2 font-medium">After</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">No audit entries found.</td></tr>
                )}
                {logs.map(log => (
                  <tr key={log.id} className="border-t border-border hover:bg-muted/30">
                    <td className="px-4 py-2 whitespace-nowrap text-xs text-muted-foreground">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-xs">{log.actor_email}</td>
                    <td className="px-4 py-2">
                      <Badge variant="outline" className="text-xs">{log.action}</Badge>
                    </td>
                    <td className="px-4 py-2 text-xs">{log.target_email}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground font-mono">
                      {log.before_value ? JSON.stringify(log.before_value) : '—'}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground font-mono">
                      {log.after_value ? JSON.stringify(log.after_value) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2 mt-3 justify-end">
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground self-center">Page {page}</span>
            <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={logs.length < 50}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AccountManagementPage() {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Account Management</h1>
      <Card>
        <CardContent className="pt-6">
          <Tabs defaultValue="users">
            <TabsList>
              <TabsTrigger value="users">Users</TabsTrigger>
              <TabsTrigger value="audit">Audit Log</TabsTrigger>
            </TabsList>
            <TabsContent value="users">
              <UsersTab />
            </TabsContent>
            <TabsContent value="audit">
              <AuditLogTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
