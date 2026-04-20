import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import api from '@/lib/api'

interface DataSource {
  id: string
  name: string
  source_type: string
  status: string
  is_active: boolean
  created_at: string
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  pending: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
}

function SourceBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  )
}

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
      // Upload file, then create source with file path
      const res = await api.post('/sources', {
        name: name || file.name,
        source_type: 'file',
        config: { file_name: file.name, file_size: file.size },
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
  const [interval, setInterval] = useState('300')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      const headers: Record<string, string> = {}
      if (authHeader && authValue) headers[authHeader] = authValue
      const res = await api.post('/sources', {
        name,
        source_type: 'rest_api',
        config: { url, headers, polling_interval_seconds: parseInt(interval, 10) },
      })
      return res.data
    },
    onSuccess: () => {
      setName(''); setUrl(''); setAuthHeader(''); setAuthValue(''); setInterval('300')
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
      <div className="space-y-1">
        <Label>Polling Interval (seconds)</Label>
        <Input value={interval} onChange={(e) => setInterval(e.target.value)} type="number" min="60" />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button onClick={() => mutation.mutate()} disabled={!name || !url || mutation.isPending} className="w-full">
        {mutation.isPending ? 'Adding...' : 'Add API Connector'}
      </Button>
    </div>
  )
}

export default function SourcesPage() {
  const queryClient = useQueryClient()
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

        <Card>
          <CardHeader><CardTitle>Connected Sources ({sources.length})</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sources connected yet.</p>
            ) : (
              <ul className="space-y-3">
                {sources.map((s) => (
                  <li key={s.id} className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <p className="font-medium text-sm">{s.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">{s.source_type}</span>
                        <SourceBadge status={s.status} />
                      </div>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => deleteMutation.mutate(s.id)}
                      disabled={deleteMutation.isPending}
                    >
                      Remove
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
