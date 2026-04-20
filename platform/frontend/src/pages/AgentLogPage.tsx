import { useQuery } from '@tanstack/react-query'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import api from '@/lib/api'

interface AgentLogEntry {
  id: string
  source_id: string | null
  agent_name: string
  status: 'running' | 'success' | 'error'
  output_summary: string | null
  error_message: string | null
  started_at: string
  completed_at: string | null
}

const STATUS_STYLES: Record<string, string> = {
  success: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  running: 'bg-yellow-100 text-yellow-800',
}

export default function AgentLogPage() {
  const { data: logs = [], isLoading, error } = useQuery<AgentLogEntry[]>({
    queryKey: ['agent-logs'],
    queryFn: async () => (await api.get('/agents/log')).data,
    refetchInterval: 10_000,
  })

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Agent Activity Log</h1>

      {isLoading && <p className="text-muted-foreground">Loading...</p>}
      {error && <p className="text-destructive text-sm">Failed to load agent logs.</p>}

      {!isLoading && logs.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-sm">No agent activity yet. Add a data source to trigger the pipeline.</p>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {logs.map((log) => (
          <Card key={log.id}>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm">{log.agent_name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[log.status] ?? 'bg-gray-100'}`}>
                      {log.status}
                    </span>
                  </div>
                  {log.source_id && (
                    <p className="text-xs text-muted-foreground mb-1">Source: {log.source_id}</p>
                  )}
                  {log.output_summary && (
                    <p className="text-sm text-foreground">{log.output_summary}</p>
                  )}
                  {log.error_message && (
                    <p className="text-sm text-destructive mt-1">{log.error_message}</p>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-xs text-muted-foreground">{new Date(log.started_at).toLocaleString()}</p>
                  {log.completed_at && (
                    <p className="text-xs text-muted-foreground">
                      {((new Date(log.completed_at).getTime() - new Date(log.started_at).getTime()) / 1000).toFixed(1)}s
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
