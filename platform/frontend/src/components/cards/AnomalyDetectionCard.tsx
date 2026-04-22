import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useChartColors } from '@/hooks/useChartColors'
import type { WidgetState } from '@/store/dashboardStore'
import api from '@/lib/api'

interface ColStats {
  data_classification: 'categorical' | 'discrete' | 'continuous'
  dtype: string
}

interface Profile {
  statistics: Record<string, ColStats>
  total_rows: number | null
}

interface AnomalyRecord {
  row_index: number
  column: string
  value: number
  z_score: number
  mean: number
  std: number
  full_row: Record<string, unknown>
}

interface AnomaliesResponse {
  anomalies: AnomalyRecord[]
  total: number
}

interface Props {
  sourceId: string | null
  widgetState?: WidgetState
  onWidgetStateChange?: (key: keyof WidgetState, value: string) => void
  isSourceUnavailable?: boolean
}

export default function AnomalyDetectionCard({ sourceId, widgetState, onWidgetStateChange, isSourceUnavailable }: Props) {
  const colors = useChartColors()
  const [view, setView] = useState<'list' | 'scatter'>('list')

  const { data: profile, isLoading: profileLoading } = useQuery<Profile>({
    queryKey: ['profile', sourceId],
    queryFn: () => api.get(`/profiles/${sourceId}`).then(r => r.data),
    enabled: !!sourceId && !isSourceUnavailable,
    refetchInterval: 30_000,
  })

  const numericCols = useMemo(() => {
    if (!profile?.statistics) return []
    return Object.entries(profile.statistics)
      .filter(([, s]) => s.data_classification !== 'categorical')
      .map(([name]) => name)
  }, [profile])

  const defaultCol = useMemo(() => {
    if (!profile?.statistics) return null
    const discrete = Object.entries(profile.statistics).find(([, s]) => s.data_classification === 'discrete')?.[0]
    const continuous = Object.entries(profile.statistics).find(([, s]) => s.data_classification === 'continuous')?.[0]
    return discrete ?? continuous ?? null
  }, [profile])

  const selectedCol = widgetState?.selected_column ?? defaultCol ?? numericCols[0] ?? null

  const { data: anomalyData, isLoading: anomalyLoading } = useQuery<AnomaliesResponse>({
    queryKey: ['anomalies', sourceId, selectedCol],
    queryFn: () => api.get(`/profiles/${sourceId}/anomalies?column=${selectedCol}`).then(r => r.data),
    enabled: !!sourceId && !!selectedCol && !isSourceUnavailable,
    refetchInterval: 30_000,
  })

  const anomalies = anomalyData?.anomalies ?? []
  const anomalySet = useMemo(() => new Set(anomalies.map(a => a.row_index)), [anomalies])

  const isLoading = profileLoading || anomalyLoading

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-1">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm">Anomaly Detection</CardTitle>
          <div className="flex items-center gap-2">
            {numericCols.length > 0 && (
              <Select value={selectedCol ?? ''} onValueChange={v => onWidgetStateChange?.('selected_column', v)}>
                <SelectTrigger className="h-7 w-36 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {numericCols.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
            <Button size="sm" variant={view === 'list' ? 'default' : 'outline'}
              className="h-7 text-xs" onClick={() => setView('list')}>List</Button>
            <Button size="sm" variant={view === 'scatter' ? 'default' : 'outline'}
              className="h-7 text-xs" onClick={() => setView('scatter')}>Scatter</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col flex-1 min-h-0">
        {!sourceId ? (
          <p className="text-sm text-muted-foreground">No source selected.</p>
        ) : isSourceUnavailable ? (
          <p className="text-sm text-muted-foreground">Source unavailable.</p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !profile || numericCols.length === 0 ? (
          <p className="text-sm text-muted-foreground">No numeric columns available.</p>
        ) : (
          <>
            {/* Summary bar */}
            <div className="flex items-center justify-between mb-2">
              <Badge variant={anomalies.length > 0 ? 'destructive' : 'success'}>
                {anomalies.length} anomal{anomalies.length === 1 ? 'y' : 'ies'} detected (&gt;3σ)
              </Badge>
              {anomalies.length > 0 && (
                <Sheet>
                  <SheetTrigger asChild>
                    <Button size="sm" variant="outline" className="h-7 text-xs">Audit</Button>
                  </SheetTrigger>
                  <SheetContent side="right">
                    <SheetHeader>
                      <SheetTitle>Anomaly Audit — {selectedCol}</SheetTitle>
                    </SheetHeader>
                    <div className="overflow-auto flex-1 mt-2">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-border text-muted-foreground">
                            <th className="text-left px-2 py-1">Row</th>
                            <th className="text-left px-2 py-1">Value</th>
                            <th className="text-left px-2 py-1">Z-Score</th>
                            <th className="text-left px-2 py-1">Full Row</th>
                          </tr>
                        </thead>
                        <tbody>
                          {anomalies.map((a, i) => (
                            <tr key={i} className="border-b border-border hover:bg-muted/30">
                              <td className="px-2 py-1">{a.row_index}</td>
                              <td className="px-2 py-1 text-destructive font-mono">{a.value}</td>
                              <td className="px-2 py-1 font-mono">{a.z_score > 0 ? '+' : ''}{a.z_score}σ</td>
                              <td className="px-2 py-1">
                                <details>
                                  <summary className="cursor-pointer text-muted-foreground">Show row</summary>
                                  <div className="mt-1 space-y-0.5">
                                    {Object.entries(a.full_row).map(([k, v]) => (
                                      <div key={k} className={`flex gap-1 ${k === a.column ? 'text-destructive font-semibold' : ''}`}>
                                        <span className="font-mono">{k}:</span>
                                        <span>{String(v ?? '—')}</span>
                                      </div>
                                    ))}
                                  </div>
                                </details>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </SheetContent>
                </Sheet>
              )}
            </div>

            {view === 'list' ? (
              <div className="overflow-auto flex-1">
                {anomalies.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No anomalies found in this column.</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="text-left px-2 py-1">Row</th>
                        <th className="text-left px-2 py-1">Value</th>
                        <th className="text-left px-2 py-1">Z-Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {anomalies.slice(0, 50).map((a, i) => (
                        <tr key={i} className="border-b border-border last:border-0">
                          <td className="px-2 py-1">{a.row_index}</td>
                          <td className="px-2 py-1 text-destructive font-mono">{a.value}</td>
                          <td className="px-2 py-1 font-mono">{a.z_score > 0 ? '+' : ''}{a.z_score}σ</td>
                        </tr>
                      ))}
                      {anomalies.length > 50 && (
                        <tr><td colSpan={3} className="px-2 py-1 text-center text-muted-foreground">+{anomalies.length - 50} more — use Audit panel to see all</td></tr>
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            ) : (
              /* Scatter view */
              <div className="flex-1 min-h-0">
                <ScatterPlot sourceId={sourceId} selectedCol={selectedCol} anomalySet={anomalySet} colors={colors} profile={profile} />
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

// Scatter plot sub-component
function ScatterPlot({
  sourceId, selectedCol, anomalySet, colors, profile,
}: {
  sourceId: string
  selectedCol: string
  anomalySet: Set<number>
  colors: ReturnType<typeof useChartColors>
  profile: Profile
}) {
  // Build scatter data from anomaly records + use row_index as x
  const { data: anomalyData } = useQuery<AnomaliesResponse>({
    queryKey: ['anomalies', sourceId, selectedCol],
    queryFn: () => api.get(`/profiles/${sourceId}/anomalies?column=${selectedCol}`).then(r => r.data),
    enabled: !!sourceId && !!selectedCol,
  })

  const scatterData = useMemo(() => {
    if (!anomalyData) return []
    return anomalyData.anomalies.map(a => ({
      x: a.row_index,
      y: a.value,
      isAnomaly: true,
    }))
  }, [anomalyData])

  if (scatterData.length === 0) {
    return <p className="text-sm text-muted-foreground">No anomalous points to plot.</p>
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
        <XAxis dataKey="x" type="number" name="Row" tick={{ fontSize: 9 }} label={{ value: 'Row Index', position: 'insideBottom', offset: -2, fontSize: 9 }} />
        <YAxis dataKey="y" type="number" name={selectedCol} tick={{ fontSize: 9 }} />
        <Tooltip
          contentStyle={{ backgroundColor: 'var(--background)', border: '1px solid var(--border)', fontSize: 11 }}
          cursor={{ strokeDasharray: '3 3' }}
        />
        <Scatter data={scatterData} name={selectedCol}>
          {scatterData.map((entry, index) => (
            <Cell key={index} fill={colors.anomaly} />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}
