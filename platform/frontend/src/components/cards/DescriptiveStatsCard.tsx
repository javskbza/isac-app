import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useChartColors } from '@/hooks/useChartColors'
import type { WidgetState } from '@/store/dashboardStore'
import api from '@/lib/api'

interface ColStats {
  dtype: string
  data_classification: 'categorical' | 'discrete' | 'continuous'
  min?: number; max?: number; mean?: number; std?: number; mode?: number | null
  kde?: Array<{ x: number; y: number }>
}

interface Profile {
  statistics: Record<string, ColStats>
  distributions: Record<string, { type: string; counts: number[]; bin_edges: number[] }>
}

function StatChip({ label, value }: { label: string; value: number | string | null | undefined }) {
  return (
    <div className="flex flex-col items-center rounded border border-border px-3 py-2">
      <span className="text-sm font-bold">{value !== null && value !== undefined ? Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 }) : '—'}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

interface Props {
  sourceId: string | null
  widgetState?: WidgetState
  onWidgetStateChange?: (key: keyof WidgetState, value: string) => void
  isSourceUnavailable?: boolean
}

export default function DescriptiveStatsCard({ sourceId, widgetState, onWidgetStateChange, isSourceUnavailable }: Props) {
  const colors = useChartColors()

  const { data: profile, isLoading } = useQuery<Profile>({
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

  const colStats = selectedCol ? profile?.statistics[selectedCol] : null
  const dist = selectedCol ? profile?.distributions[selectedCol] : null

  // Build chart data: merge histogram bars with KDE line on same x domain
  const chartData = useMemo(() => {
    if (!colStats?.kde?.length || !dist?.bin_edges?.length) return []
    const kde = colStats.kde
    // Map bin edges to bar data
    const bars = dist.bin_edges.slice(0, -1).map((edge, i) => ({
      x: Number(((edge + (dist.bin_edges[i + 1] ?? edge)) / 2).toFixed(4)),
      count: dist.counts[i] ?? 0,
    }))
    // Merge KDE points (by nearest x)
    return bars.map(bar => {
      const nearest = kde.reduce((prev, cur) =>
        Math.abs(cur.x - bar.x) < Math.abs(prev.x - bar.x) ? cur : prev
      )
      return { ...bar, density: nearest.y }
    })
  }, [colStats, dist])

  const mean = colStats?.mean
  const std = colStats?.std

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-1">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Descriptive Statistics</CardTitle>
          {numericCols.length > 0 && (
            <Select value={selectedCol ?? ''} onValueChange={v => onWidgetStateChange?.('selected_column', v)}>
              <SelectTrigger className="h-7 w-40 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {numericCols.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
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
            <div className="flex gap-2 flex-wrap mb-3">
              <StatChip label="Min" value={colStats?.min} />
              <StatChip label="Max" value={colStats?.max} />
              <StatChip label="Mean" value={colStats?.mean} />
              <StatChip label="Std" value={colStats?.std} />
              <StatChip label="Mode" value={colStats?.mode} />
            </div>
            {chartData.length > 0 ? (
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
                    <XAxis dataKey="x" tick={{ fontSize: 9 }} tickFormatter={v => Number(v).toFixed(1)} />
                    <YAxis yAxisId="left" tick={{ fontSize: 9 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 9 }} />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--background)', border: '1px solid var(--border)', fontSize: 11 }} />
                    <Bar yAxisId="left" dataKey="count" fill={colors.muted} name="Count" opacity={0.6} />
                    <Line yAxisId="right" type="monotone" dataKey="density" stroke={colors.kde} dot={false} strokeWidth={2} name="Density" />
                    {mean !== undefined && mean !== null && (
                      <ReferenceLine yAxisId="left" x={Number(mean.toFixed(4))} stroke={colors.primary} strokeWidth={2} label={{ value: 'μ', fontSize: 10, fill: colors.primary }} />
                    )}
                    {mean !== undefined && std !== undefined && mean !== null && std !== null && (
                      <>
                        <ReferenceLine yAxisId="left" x={Number((mean + std).toFixed(4))} stroke={colors.refLine} strokeDasharray="4 2" label={{ value: '+1σ', fontSize: 9, fill: colors.refLine }} />
                        <ReferenceLine yAxisId="left" x={Number((mean - std).toFixed(4))} stroke={colors.refLine} strokeDasharray="4 2" label={{ value: '-1σ', fontSize: 9, fill: colors.refLine }} />
                        <ReferenceLine yAxisId="left" x={Number((mean + 2 * std).toFixed(4))} stroke={colors.refLine} strokeDasharray="2 4" label={{ value: '+2σ', fontSize: 9, fill: colors.refLine }} />
                        <ReferenceLine yAxisId="left" x={Number((mean - 2 * std).toFixed(4))} stroke={colors.refLine} strokeDasharray="2 4" label={{ value: '-2σ', fontSize: 9, fill: colors.refLine }} />
                        <ReferenceLine yAxisId="left" x={Number((mean + 3 * std).toFixed(4))} stroke={colors.anomaly} strokeDasharray="1 3" label={{ value: '+3σ', fontSize: 9, fill: colors.anomaly }} />
                        <ReferenceLine yAxisId="left" x={Number((mean - 3 * std).toFixed(4))} stroke={colors.anomaly} strokeDasharray="1 3" label={{ value: '-3σ', fontSize: 9, fill: colors.anomaly }} />
                      </>
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground mt-2">Distribution not available.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
