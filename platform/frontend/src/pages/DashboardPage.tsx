import { useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import GridLayout, { WidthProvider } from 'react-grid-layout'
import type { Layout } from 'react-grid-layout'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import DataProfileCard from '@/components/cards/DataProfileCard'
import ProfileDetailsCard from '@/components/cards/ProfileDetailsCard'
import DescriptiveStatsCard from '@/components/cards/DescriptiveStatsCard'
import TrendAnalysisCard from '@/components/cards/TrendAnalysisCard'
import AnomalyDetectionCard from '@/components/cards/AnomalyDetectionCard'
import { useDashboardStore } from '@/store/dashboardStore'
import { useAuthStore } from '@/store/authStore'
import { useChartColors } from '@/hooks/useChartColors'
import api from '@/lib/api'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

const ResponsiveGrid = WidthProvider(GridLayout)

interface Source { id: string; name: string; status: string; is_active: boolean }
interface Insight { id: string; type: string; title: string; body: string; data: any; created_at: string }

// ---------------------------------------------------------------------------
// Unchanged v1 widgets (forecast + insight feed)
// ---------------------------------------------------------------------------

function ForecastWidget({ insights }: { insights: Insight[] }) {
  const colors = useChartColors()
  const forecasts = insights.filter(i => i.type === 'forecast')
  const data = forecasts[0]?.data?.forecast?.slice(0, 7)
    ?? Array.from({ length: 7 }, (_, i) => ({ ds: `D${i + 1}`, yhat: 100 + i * 3 }))
  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">Forecast</CardTitle></CardHeader>
      <CardContent className="h-[calc(100%-60px)]">
        <ResponsiveContainer width="100%" height={120}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
            <XAxis dataKey="ds" tick={{ fontSize: 9 }} tickFormatter={v => String(v).slice(0, 5)} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ backgroundColor: 'var(--background)', border: '1px solid var(--border)' }} />
            <Area type="monotone" dataKey="yhat" stroke={colors.kde} fill={colors.kde} fillOpacity={0.2} />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

function InsightFeed({ insights }: { insights: Insight[] }) {
  const TYPE_ICONS: Record<string, string> = {
    anomaly: '🚨', trend: '📈', forecast: '🔮', pattern: '🔁', summary: '📋',
  }
  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">Insight Feed</CardTitle></CardHeader>
      <CardContent className="overflow-auto h-[calc(100%-60px)]">
        {insights.length === 0 ? (
          <p className="text-sm text-muted-foreground">No insights yet. Add a data source to begin.</p>
        ) : (
          <div className="space-y-2">
            {insights.map(insight => (
              <div key={insight.id} className="rounded-lg border border-border p-3">
                <div className="flex items-start gap-2">
                  <span className="text-base">{TYPE_ICONS[insight.type] ?? '💡'}</span>
                  <div>
                    <p className="text-sm font-medium">{insight.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{insight.body}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Source selector
// ---------------------------------------------------------------------------

function SourceSelector({ sources, activeId, onSelect }: {
  sources: Source[]
  activeId: string | null
  onSelect: (id: string) => void
}) {
  if (sources.length === 0) return null
  return (
    <Select value={activeId ?? ''} onValueChange={onSelect}>
      <SelectTrigger className="w-56">
        <SelectValue placeholder="Select a source…" />
      </SelectTrigger>
      <SelectContent>
        {sources.map(s => {
          const unavailable = !s.is_active || s.status === 'disconnected'
          return (
            <SelectItem key={s.id} value={s.id} className={unavailable ? 'opacity-60' : ''}>
              <span className={unavailable ? 'line-through' : ''}>{s.name}</span>
              {unavailable && (
                <Badge variant="muted" className="ml-2 text-[10px] py-0">Unavailable</Badge>
              )}
            </SelectItem>
          )
        })}
      </SelectContent>
    </Select>
  )
}

// ---------------------------------------------------------------------------
// Empty states
// ---------------------------------------------------------------------------

function SourceUnavailableBanner() {
  return (
    <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
      This source is no longer available. Please select a different source from the dropdown above.
    </div>
  )
}

function NoSourceEmptyState({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="rounded-lg border border-border p-6 text-center text-sm text-muted-foreground">
      {isAdmin
        ? 'Add a data source to get started.'
        : 'Ask your Admin to add a data source.'}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { user } = useAuthStore()
  const {
    layout, widgetState, selectedSourceId, isLoaded,
    fetchLayout, saveLayout, setSelectedSource, setWidgetState,
  } = useDashboardStore()

  useEffect(() => {
    if (!isLoaded) fetchLayout()
  }, [isLoaded, fetchLayout])

  const { data: sources = [] } = useQuery<Source[]>({
    queryKey: ['sources'],
    queryFn: () => api.get('/sources').then(r => r.data),
  })

  // Restore last-selected source from user preferences or fall back to first active
  const activeSource = (() => {
    if (selectedSourceId) return selectedSourceId
    const src = sources.find(s => s.is_active)
    return src?.id ?? null
  })()

  const activeSourceObj = sources.find(s => s.id === activeSource)
  const isSourceUnavailable = activeSourceObj
    ? (!activeSourceObj.is_active || activeSourceObj.status === 'disconnected')
    : false
  const noSources = sources.length === 0

  const { data: insights = [] } = useQuery<Insight[]>({
    queryKey: ['insights', activeSource],
    queryFn: () => api.get(`/insights/${activeSource}`).then(r => r.data),
    enabled: !!activeSource && !isSourceUnavailable,
    refetchInterval: 30_000,
  })

  const handleLayoutChange = useCallback(
    (newLayout: Layout[]) => saveLayout(newLayout, widgetState),
    [widgetState, saveLayout],
  )

  const cardProps = (widgetId: string) => ({
    sourceId: activeSource,
    widgetState: widgetState[widgetId],
    onWidgetStateChange: (key: any, value: string) => setWidgetState(widgetId, key, value),
    isSourceUnavailable,
  })

  const WIDGET_MAP: Record<string, React.ReactNode> = {
    data_profile:      <DataProfileCard {...cardProps('data_profile')} />,
    profile_details:   <ProfileDetailsCard {...cardProps('profile_details')} />,
    descriptive_stats: <DescriptiveStatsCard {...cardProps('descriptive_stats')} />,
    trend_analysis:    <TrendAnalysisCard {...cardProps('trend_analysis')} />,
    anomaly_detection: <AnomalyDetectionCard {...cardProps('anomaly_detection')} />,
    forecast:          <ForecastWidget insights={insights} />,
    insights:          <InsightFeed insights={insights} />,
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <SourceSelector
          sources={sources}
          activeId={activeSource}
          onSelect={setSelectedSource}
        />
      </div>

      {noSources && <NoSourceEmptyState isAdmin={user?.role === 'admin'} />}
      {isSourceUnavailable && !noSources && <SourceUnavailableBanner />}

      {isLoaded && (
        <ResponsiveGrid
          layout={layout}
          cols={12}
          rowHeight={80}
          onLayoutChange={handleLayoutChange}
          isDraggable
          isResizable
        >
          {layout.map(item => (
            <div key={item.i}>
              {WIDGET_MAP[item.i] ?? null}
            </div>
          ))}
        </ResponsiveGrid>
      )}
    </div>
  )
}
