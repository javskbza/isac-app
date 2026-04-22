import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useChartColors } from '@/hooks/useChartColors'
import type { WidgetState } from '@/store/dashboardStore'
import api from '@/lib/api'

interface ColStats {
  dtype: string
  data_classification: 'categorical' | 'discrete' | 'continuous'
  time_series?: Record<string, Array<{ date: string; value: number }>>
}

interface Profile {
  statistics: Record<string, ColStats>
}

interface Props {
  sourceId: string | null
  widgetState?: WidgetState
  onWidgetStateChange?: (key: keyof WidgetState, value: string) => void
  isSourceUnavailable?: boolean
}

export default function TrendAnalysisCard({ sourceId, widgetState, onWidgetStateChange, isSourceUnavailable }: Props) {
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

  const dateCols = useMemo(() => {
    if (!profile?.statistics) return []
    return Object.entries(profile.statistics)
      .filter(([, s]) => s.data_classification === 'continuous' && s.dtype.includes('datetime'))
      .map(([name]) => name)
  }, [profile])

  const defaultNumericCol = useMemo(() => {
    if (!profile?.statistics) return null
    const discrete = Object.entries(profile.statistics).find(([, s]) => s.data_classification === 'discrete')?.[0]
    const continuous = Object.entries(profile.statistics).find(([, s]) => s.data_classification === 'continuous')?.[0]
    return discrete ?? continuous ?? null
  }, [profile])

  const selectedCol = widgetState?.selected_column ?? defaultNumericCol ?? numericCols[0] ?? null
  const selectedDateCol = widgetState?.selected_date_column ?? dateCols[0] ?? null

  const trendData = useMemo(() => {
    if (!selectedCol || !selectedDateCol) return []
    const ts = profile?.statistics[selectedCol]?.time_series
    return ts?.[selectedDateCol] ?? []
  }, [profile, selectedCol, selectedDateCol])

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }
    catch { return iso }
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-1">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm">Trend Analysis</CardTitle>
          <div className="flex gap-2">
            {numericCols.length > 0 && (
              <Select value={selectedCol ?? ''} onValueChange={v => onWidgetStateChange?.('selected_column', v)}>
                <SelectTrigger className="h-7 w-36 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {numericCols.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
            {dateCols.length > 1 && (
              <Select value={selectedDateCol ?? ''} onValueChange={v => onWidgetStateChange?.('selected_date_column', v)}>
                <SelectTrigger className="h-7 w-36 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {dateCols.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
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
        ) : !profile ? (
          <p className="text-sm text-muted-foreground">Analysis in progress…</p>
        ) : dateCols.length === 0 ? (
          <p className="text-sm text-muted-foreground">Trend analysis requires a date/time column in your dataset.</p>
        ) : numericCols.length === 0 ? (
          <p className="text-sm text-muted-foreground">No numeric columns available.</p>
        ) : trendData.length === 0 ? (
          <p className="text-sm text-muted-foreground">No trend data available for this combination.</p>
        ) : (
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
                <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={formatDate} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'var(--background)', border: '1px solid var(--border)', fontSize: 11 }}
                  labelFormatter={formatDate}
                />
                <Line type="monotone" dataKey="value" stroke={colors.primary} dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
