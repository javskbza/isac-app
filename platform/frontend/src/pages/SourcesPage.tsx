import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useAuthStore } from '@/store/authStore'
import api from '@/lib/api'

interface DataSource {
  id: string
  name: string
  source_type: string
  status: string
  is_active: boolean
  created_at: string
}

interface Schedule {
  source_id: string
  schedule_expr: string
  enabled: boolean
}

interface PollLog {
  id: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  status: 'success' | 'failure'
  attempt_number: number
  error_message: string | null
}


// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_VARIANTS: Record<string, 'success' | 'warning' | 'destructive' | 'secondary' | 'default'> = {
  active: 'success',
  degraded: 'warning',
  paused: 'secondary',
  disconnected: 'destructive',
  pending: 'default',
}

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  degraded: 'Degraded',
  paused: 'Paused',
  disconnected: 'Disconnected',
  pending: 'Pending',
}

function SourceStatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANTS[status] ?? 'secondary'
  return <Badge variant={variant}>{STATUS_LABELS[status] ?? status}</Badge>
}

// ---------------------------------------------------------------------------
// Schedule section (admin only)
// ---------------------------------------------------------------------------

const SCHEDULE_PRESETS = [
  { label: 'Every 5 minutes', value: '*/5 * * * *' },
  { label: 'Every 15 minutes', value: '*/15 * * * *' },
  { label: 'Hourly', value: '0 * * * *' },
  { label: 'Every 6 hours', value: '0 */6 * * *' },
  { label: 'Daily', value: '0 0 * * *' },
  { label: 'Weekly', value: '0 0 * * 0' },
  { label: 'Custom…', value: '__custom__' },
]

function ScheduleSection({ sourceId }: { sourceId: string }) {
  const queryClient = useQueryClient()
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [customExpr, setCustomExpr] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)

  const { data: schedule, isLoading } = useQuery<Schedule | null>({
    queryKey: ['schedule', sourceId],
    queryFn: () => api.get(`/sources/${sourceId}/schedule`).then(r => r.data).catch(e => {
      if (e.response?.status === 404) return null
      throw e
    }),
  })

  const [selectedPreset, setSelectedPreset] = useState<string>(() => {
    if (!schedule) return '0 * * * *'
    const match = SCHEDULE_PRESETS.find(p => p.value === schedule.schedule_expr && p.value !== '__custom__')
    return match ? match.value : '__custom__'
  })
  const [enabled, setEnabled] = useState(schedule?.enabled ?? true)

  const effectiveExpr = selectedPreset === '__custom__' ? customExpr : selectedPreset

  const saveMutation = useMutation({
    mutationFn: () => api.post(`/sources/${sourceId}/schedule`, {
      schedule_expr: effectiveExpr,
      enabled,
    }),
    onSuccess: () => {
      setSaveError(null)
      queryClient.invalidateQueries({ queryKey: ['schedule', sourceId] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    },
    onError: (err: any) => setSaveError(err.response?.data?.detail || 'Failed to save schedule'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/sources/${sourceId}/schedule`),
    onSuccess: () => {
      setSaveError(null)
      queryClient.invalidateQueries({ queryKey: ['schedule', sourceId] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    },
  })

  if (isLoading) return <p className="text-xs text-muted-foreground">Loading schedule…</p>

  return (
    <div className="mt-3 border-t border-border pt-3 space-y-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Schedule</p>
      <div className="flex items-center gap-3">
        <Select
          value={selectedPreset}
          onValueChange={v => {
            setSelectedPreset(v)
            if (v !== '__custom__') setShowAdvanced(false)
            else setShowAdvanced(true)
          }}
        >
          <SelectTrigger className="h-7 text-xs w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SCHEDULE_PRESETS.map(p => (
              <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1.5">
          <Switch
            checked={enabled}
            onCheckedChange={setEnabled}
            id={`schedule-enabled-${sourceId}`}
          />
          <Label htmlFor={`schedule-enabled-${sourceId}`} className="text-xs cursor-pointer">
            {enabled ? 'Enabled' : 'Disabled'}
          </Label>
        </div>
      </div>
      {showAdvanced && (
        <div className="space-y-1">
          <Label className="text-xs">Cron expression</Label>
          <Input
            value={customExpr || schedule?.schedule_expr || ''}
            onChange={e => setCustomExpr(e.target.value)}
            placeholder="*/30 * * * *"
            className="h-7 text-xs font-mono"
          />
        </div>
      )}
      {schedule && !showAdvanced && (
        <p className="text-xs text-muted-foreground font-mono">{schedule.schedule_expr}</p>
      )}
      {saveError && <p className="text-xs text-destructive">{saveError}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          className="h-7 text-xs"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !effectiveExpr}
        >
          {saveMutation.isPending ? 'Saving…' : 'Save Schedule'}
        </Button>
        {schedule && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
          >
            Remove
          </Button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Poll log sheet (admin only)
// ---------------------------------------------------------------------------

function PollLogSheet({ sourceId, sourceName }: { sourceId: string; sourceName: string }) {
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const { data: logs = [], isLoading } = useQuery<PollLog[]>({
    queryKey: ['poll-log', sourceId, page],
    queryFn: () => api.get(`/sources/${sourceId}/poll-log?page=${page}&page_size=${PAGE_SIZE}`).then(r => r.data),
  })

  const hasMore = logs.length === PAGE_SIZE

  const formatDuration = (ms: number | null) => {
    if (ms === null) return '—'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' })

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button size="sm" variant="outline" className="h-7 text-xs">Poll Log</Button>
      </SheetTrigger>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Poll Log — {sourceName}</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col flex-1 min-h-0 overflow-auto">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : logs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No poll history yet.</p>
          ) : (
            <>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left px-2 py-1.5">Started</th>
                    <th className="text-left px-2 py-1.5">Status</th>
                    <th className="text-left px-2 py-1.5">Duration</th>
                    <th className="text-left px-2 py-1.5">Attempt</th>
                    <th className="text-left px-2 py-1.5">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                      <td className="px-2 py-1.5 whitespace-nowrap">{formatDate(log.started_at)}</td>
                      <td className="px-2 py-1.5">
                        <Badge variant={log.status === 'success' ? 'success' : 'destructive'}>
                          {log.status}
                        </Badge>
                      </td>
                      <td className="px-2 py-1.5 font-mono">{formatDuration(log.duration_ms)}</td>
                      <td className="px-2 py-1.5">{log.attempt_number}</td>
                      <td className="px-2 py-1.5 text-destructive max-w-[200px] truncate">
                        {log.error_message ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(page > 1 || hasMore) && (
                <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
                  <span>Page {page}</span>
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" className="h-6 text-xs px-2"
                      disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
                    <Button size="sm" variant="outline" className="h-6 text-xs px-2"
                      disabled={!hasMore} onClick={() => setPage(p => p + 1)}>Next</Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

// ---------------------------------------------------------------------------
// Source card
// ---------------------------------------------------------------------------

function SourceCard({ source, isAdmin, onDelete, isDeleting }: {
  source: DataSource
  isAdmin: boolean
  onDelete: () => void
  isDeleting: boolean
}) {
  const queryClient = useQueryClient()
  const [scheduleOpen, setScheduleOpen] = useState(false)

  const refreshMutation = useMutation({
    mutationFn: () => api.post(`/sources/${source.id}/refresh`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  })

  return (
    <li className="rounded-lg border border-border p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-sm">{source.name}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-muted-foreground capitalize">{source.source_type.replace('_', ' ')}</span>
            <SourceStatusBadge status={source.status} />
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {isAdmin && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
            >
              {refreshMutation.isPending ? 'Running…' : 'Refresh Now'}
            </Button>
          )}
          {isAdmin && <PollLogSheet sourceId={source.id} sourceName={source.name} />}
          <Button
            variant="destructive"
            size="sm"
            className="h-7 text-xs"
            onClick={onDelete}
            disabled={isDeleting}
          >
            Remove
          </Button>
        </div>
      </div>

      {isAdmin && (
        <>
          <button
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
            onClick={() => setScheduleOpen(o => !o)}
          >
            <svg
              className={`h-3 w-3 transition-transform ${scheduleOpen ? 'rotate-90' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            {scheduleOpen ? 'Hide' : 'Configure'} schedule
          </button>
          {scheduleOpen && <ScheduleSection sourceId={source.id} />}
        </>
      )}
    </li>
  )
}

// ---------------------------------------------------------------------------
// Add source forms
// ---------------------------------------------------------------------------

function FileUploadForm({ onSuccess }: { onSuccess: () => void }) {
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('No file selected')
      const formData = new FormData()
      formData.append('file', file)
      const uploadRes = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const { file_path } = uploadRes.data
      const res = await api.post('/sources', {
        name: name || file.name,
        source_type: 'file',
        config: { file_path },
      })
      return res.data
    },
    onSuccess: () => {
      setName('')
      setFile(null)
      setError(null)
      onSuccess()
    },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to add source'),
  })

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }, [])

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label>Source Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="My CSV file" />
      </div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${dragging ? 'border-primary bg-primary/5' : 'border-border'}`}
      >
        {file ? (
          <p className="text-sm">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">Drag & drop a CSV, Excel, or JSON file</p>
            <p className="mt-1 text-xs text-muted-foreground">or</p>
            <label className="mt-2 inline-block cursor-pointer text-sm text-primary hover:underline">
              Browse files
              <input
                type="file"
                accept=".csv,.xlsx,.xls,.json"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </>
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button onClick={() => mutation.mutate()} disabled={!file || mutation.isPending} className="w-full">
        {mutation.isPending ? 'Adding...' : 'Add File Source'}
      </Button>
    </div>
  )
}

function APIConnectorForm({ onSuccess }: { onSuccess: () => void }) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [authHeader, setAuthHeader] = useState('')
  const [authValue, setAuthValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      const headers: Record<string, string> = {}
      if (authHeader && authValue) headers[authHeader] = authValue
      const res = await api.post('/sources', {
        name,
        source_type: 'rest_api',
        config: { url, headers },
      })
      return res.data
    },
    onSuccess: () => {
      setName(''); setUrl(''); setAuthHeader(''); setAuthValue('')
      setError(null)
      onSuccess()
    },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to add connector'),
  })

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label>Source Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="My API" required />
      </div>
      <div className="space-y-1">
        <Label>Endpoint URL</Label>
        <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.example.com/data" type="url" required />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label>Auth Header Name</Label>
          <Input value={authHeader} onChange={(e) => setAuthHeader(e.target.value)} placeholder="Authorization" />
        </div>
        <div className="space-y-1">
          <Label>Auth Value</Label>
          <Input value={authValue} onChange={(e) => setAuthValue(e.target.value)} placeholder="Bearer token..." type="password" />
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button onClick={() => mutation.mutate()} disabled={!name || !url || mutation.isPending} className="w-full">
        {mutation.isPending ? 'Adding...' : 'Add API Connector'}
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SourcesPage() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'
  const [activeTab, setActiveTab] = useState<'file' | 'api'>('file')

  const { data: sources = [], isLoading } = useQuery<DataSource[]>({
    queryKey: ['sources'],
    queryFn: async () => (await api.get('/sources')).data,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/sources/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  })

  const refreshSources = () => queryClient.invalidateQueries({ queryKey: ['sources'] })

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Data Sources</h1>

      <div className="grid gap-6 md:grid-cols-2">
        {isAdmin && (
          <Card>
            <CardHeader>
              <CardTitle>Add Source</CardTitle>
              <div className="flex gap-2 mt-2">
                <Button variant={activeTab === 'file' ? 'default' : 'outline'} size="sm" onClick={() => setActiveTab('file')}>File Upload</Button>
                <Button variant={activeTab === 'api' ? 'default' : 'outline'} size="sm" onClick={() => setActiveTab('api')}>REST API</Button>
              </div>
            </CardHeader>
            <CardContent>
              {activeTab === 'file' ? <FileUploadForm onSuccess={refreshSources} /> : <APIConnectorForm onSuccess={refreshSources} />}
            </CardContent>
          </Card>
        )}

        <Card className={isAdmin ? '' : 'md:col-span-2'}>
          <CardHeader><CardTitle>Connected Sources ({sources.length})</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sources connected yet.</p>
            ) : (
              <ul className="space-y-3">
                {sources.map((s) => (
                  <SourceCard
                    key={s.id}
                    source={s}
                    isAdmin={isAdmin}
                    onDelete={() => deleteMutation.mutate(s.id)}
                    isDeleting={deleteMutation.isPending && deleteMutation.variables === s.id}
                  />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
