import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import GridLayout, { Layout } from 'react-grid-layout'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import api from '@/lib/api'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

interface Source { id: string; name: string; status: string }
interface Insight { id: string; type: string; title: string; body: string; data: any; created_at: string }
interface Profile { statistics: Record<string, any>; null_rates: Record<string, number>; total_rows: number }

const DEFAULT_LAYOUT: Layout[] = [
  { i: 'kpi', x: 0, y: 0, w: 3, h: 2 },
  { i: 'trend', x: 3, y: 0, w: 5, h: 4 },
  { i: 'anomaly', x: 8, y: 0, w: 4, h: 2 },
  { i: 'forecast', x: 0, y: 2, w: 6, h: 4 },
  { i: 'profile', x: 6, y: 4, w: 6, h: 3 },
  { i: 'insights', x: 0, y: 6, w: 12, h: 4 },
]

function KPICard({ profile, sourceName }: { profile: Profile | null; sourceName: string }) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">KPI — {sourceName}</CardTitle></CardHeader>
      <CardContent>
        {profile ? (
          <div className="grid grid-cols-2 gap-2">
            <div><p className="text-2xl font-bold">{profile.total_rows?.toLocaleString()}</p><p className="text-xs text-muted-foreground">Rows</p></div>
            <div>
              <p className="text-2xl font-bold">
                {Object.values(profile.null_rates || {}).length > 0
                  ? `${(Object.values(profile.null_rates).reduce((a, b) => a + b, 0) / Object.values(profile.null_rates).length * 100).toFixed(1)}%`
                  : 'N/A'}
              </p>
              <p className="text-xs text-muted-foreground">Avg Null Rate</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No profile yet</p>
        )}
      </CardContent>
    </Card>
  )
}

function TrendWidget({ insights }: { insights: Insight[] }) {
  const trendInsights = insights.filter((i) => i.type === 'trend')
  const mockData = Array.from({ length: 10 }, (_, i) => ({ name: `T${i + 1}`, value: Math.random() * 100 + i * 5 }))

  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">Trend Overview</CardTitle></CardHeader>
      <CardContent className="h-[calc(100%-60px)]">
        {trendInsights.length > 0 ? (
          <div className="space-y-1 mb-2">
            {trendInsights.slice(0, 2).map((t) => (
              <p key={t.id} className="text-xs text-muted-foreground">{t.title}</p>
            ))}
          </div>
        ) : null}
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={mockData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

function AnomalyWidget({ insights }: { insights: Insight[] }) {
  const anomalies = insights.filter((i) => i.type === 'anomaly')
  return (
    <Card className="h-full border-red-200">
      <CardHeader className="pb-2"><CardTitle className="text-sm text-red-700">Anomaly Alerts</CardTitle></CardHeader>
      <CardContent>
        {anomalies.length === 0 ? (
          <p className="text-xs text-muted-foreground">No anomalies detected</p>
        ) : (
          <div className="space-y-2">
            {anomalies.map((a) => (
              <div key={a.id} className="rounded bg-red-50 p-2">
                <p className="text-xs font-medium text-red-800">{a.title}</p>
                <p className="text-xs text-red-600">{a.body.slice(0, 80)}...</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ForecastWidget({ insights }: { insights: Insight[] }) {
  const forecasts = insights.filter((i) => i.type === 'forecast')
  const forecastData = forecasts[0]?.data?.forecast?.slice(0, 7) ?? Array.from({ length: 7 }, (_, i) => ({ ds: `D${i + 1}`, yhat: Math.random() * 50 + 100 }))

  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">Forecast</CardTitle></CardHeader>
      <CardContent className="h-[calc(100%-60px)]">
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={forecastData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="ds" tick={{ fontSize: 9 }} tickFormatter={(v) => String(v).slice(0, 5)} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Area type="monotone" dataKey="yhat" stroke="#8b5cf6" fill="#ede9fe" />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

function ProfileSummaryWidget({ profile }: { profile: Profile | null }) {
  if (!profile) return <Card className="h-full"><CardContent className="pt-6"><p className="text-sm text-muted-foreground">No profile data yet.</p></CardContent></Card>
  const cols = Object.entries(profile.statistics || {}).slice(0, 5)
  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">Data Profile Summary</CardTitle></CardHeader>
      <CardContent>
        <table className="w-full text-xs">
          <thead><tr className="border-b"><th className="text-left pb-1">Column</th><th className="text-right pb-1">Null%</th><th className="text-right pb-1">Cardinality</th></tr></thead>
          <tbody>
            {cols.map(([col, stats]) => (
              <tr key={col} className="border-b last:border-0">
                <td className="py-1 truncate max-w-[100px]">{col}</td>
                <td className="text-right py-1">{((profile.null_rates?.[col] ?? 0) * 100).toFixed(1)}%</td>
                <td className="text-right py-1">{(stats as any).cardinality ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function InsightFeed({ insights }: { insights: Insight[] }) {
  const TYPE_ICONS: Record<string, string> = { anomaly: '🚨', trend: '📈', forecast: '🔮', pattern: '🔁', summary: '📋' }
  return (
    <Card className="h-full">
      <CardHeader className="pb-2"><CardTitle className="text-sm">Insight Feed</CardTitle></CardHeader>
      <CardContent className="overflow-auto h-[calc(100%-60px)]">
        {insights.length === 0 ? (
          <p className="text-sm text-muted-foreground">No insights yet. Add a data source to begin.</p>
        ) : (
          <div className="space-y-2">
            {insights.map((insight) => (
              <div key={insight.id} className="rounded-lg border p-3">
                <div className="flex items-start gap-2">
                  <span className="text-base">{TYPE_ICONS[insight.type] ?? '💡'}</span>
                  <div>
                    <p className="text-sm font-medium">{insight.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{insight.body}</p>
                    <p className="text-xs text-muted-foreground mt-1">{new Date(insight.created_at).toLocaleString()}</p>
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

export default function DashboardPage() {
  const [layout, setLayout] = useState<Layout[]>(DEFAULT_LAYOUT)
  const [selectedSource, setSelectedSource] = useState<string | null>(null)

  const { data: sources = [] } = useQuery<Source[]>({
    queryKey: ['sources'],
    queryFn: async () => (await api.get('/sources')).data,
  })

  const activeSource = selectedSource ?? sources[0]?.id ?? null

  const { data: insights = [] } = useQuery<Insight[]>({
    queryKey: ['insights', activeSource],
    queryFn: async () => (await api.get(`/insights/${activeSource}`)).data,
    enabled: !!activeSource,
    refetchInterval: 30_000,
  })

  const { data: profile } = useQuery<Profile>({
    queryKey: ['profile', activeSource],
    queryFn: async () => (await api.get(`/profiles/${activeSource}`)).data,
    enabled: !!activeSource,
  })

  const sourceName = sources.find((s) => s.id === activeSource)?.name ?? 'No source'

  const handleLayoutChange = useCallback((newLayout: Layout[]) => setLayout(newLayout), [])

  const WIDGET_MAP: Record<string, React.ReactNode> = {
    kpi: <KPICard profile={profile ?? null} sourceName={sourceName} />,
    trend: <TrendWidget insights={insights} />,
    anomaly: <AnomalyWidget insights={insights} />,
    forecast: <ForecastWidget insights={insights} />,
    profile: <ProfileSummaryWidget profile={profile ?? null} />,
    insights: <InsightFeed insights={insights} />,
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        {sources.length > 0 && (
          <select
            className="rounded-md border bg-background px-3 py-1.5 text-sm"
            value={activeSource ?? ''}
            onChange={(e) => setSelectedSource(e.target.value)}
          >
            {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        )}
      </div>

      <GridLayout
        className="layout"
        layout={layout}
        cols={12}
        rowHeight={80}
        width={1200}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".card-drag-handle"
      >
        {layout.map((item) => (
          <div key={item.i}>
            {WIDGET_MAP[item.i] ?? null}
          </div>
        ))}
      </GridLayout>
    </div>
  )
}
