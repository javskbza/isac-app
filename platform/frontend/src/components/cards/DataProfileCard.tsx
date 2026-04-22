import { useQuery } from '@tanstack/react-query'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import api from '@/lib/api'

interface ProfileSummary {
  total_rows: number | null
  total_columns: number | null
  categorical_count: number
  discrete_count: number
  continuous_count: number
}

function StatChip({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-border p-3">
      <span className="text-2xl font-bold">{value ?? '—'}</span>
      <span className="text-xs text-muted-foreground mt-1">{label}</span>
    </div>
  )
}

interface Props {
  sourceId: string | null
  isSourceUnavailable?: boolean
}

export default function DataProfileCard({ sourceId, isSourceUnavailable }: Props) {
  const { data: profile, isLoading } = useQuery<ProfileSummary>({
    queryKey: ['profile', sourceId],
    queryFn: () => api.get(`/profiles/${sourceId}`).then(r => r.data),
    enabled: !!sourceId && !isSourceUnavailable,
    refetchInterval: 30_000,
  })

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Data Profile</CardTitle>
      </CardHeader>
      <CardContent>
        {!sourceId ? (
          <p className="text-sm text-muted-foreground">No source selected.</p>
        ) : isSourceUnavailable ? (
          <p className="text-sm text-muted-foreground">Source unavailable.</p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !profile ? (
          <p className="text-sm text-muted-foreground">Analysis in progress…</p>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            <StatChip label="Rows" value={(profile.total_rows ?? 0).toLocaleString()} />
            <StatChip label="Columns" value={profile.total_columns ?? 0} />
            <StatChip label="Categorical" value={profile.categorical_count} />
            <StatChip label="Discrete" value={profile.discrete_count} />
            <StatChip label="Continuous" value={profile.continuous_count} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
