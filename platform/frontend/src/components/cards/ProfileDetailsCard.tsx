import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ArrowUpDown } from 'lucide-react'
import api from '@/lib/api'

interface ColStats {
  dtype: string
  null_rate: number
  cardinality: number
  pk_candidate: boolean
  data_classification: 'categorical' | 'discrete' | 'continuous'
}

interface Profile {
  statistics: Record<string, ColStats>
}

type SortKey = 'column' | 'null_rate' | 'cardinality' | 'data_classification'
type SortDir = 'asc' | 'desc'

const CLASS_VARIANT: Record<string, 'muted' | 'secondary' | 'success'> = {
  categorical: 'muted',
  discrete: 'secondary',
  continuous: 'success',
}

interface Props {
  sourceId: string | null
  isSourceUnavailable?: boolean
}

export default function ProfileDetailsCard({ sourceId, isSourceUnavailable }: Props) {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('column')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const { data: profile, isLoading } = useQuery<Profile>({
    queryKey: ['profile', sourceId],
    queryFn: () => api.get(`/profiles/${sourceId}`).then(r => r.data),
    enabled: !!sourceId && !isSourceUnavailable,
    refetchInterval: 30_000,
  })

  const columns = useMemo(() => {
    if (!profile?.statistics) return []
    return Object.entries(profile.statistics).map(([name, stats]) => ({
      name,
      dtype: stats.dtype,
      null_rate: stats.null_rate,
      cardinality: stats.cardinality,
      pk_candidate: stats.pk_candidate,
      classification: stats.data_classification,
    }))
  }, [profile])

  const filtered = useMemo(() => {
    let rows = columns
    if (search) rows = rows.filter(r => r.name.toLowerCase().includes(search.toLowerCase()))
    rows = [...rows].sort((a, b) => {
      let av: any = a[sortKey === 'column' ? 'name' : sortKey === 'data_classification' ? 'classification' : sortKey]
      let bv: any = b[sortKey === 'column' ? 'name' : sortKey === 'data_classification' ? 'classification' : sortKey]
      if (typeof av === 'string') av = av.toLowerCase()
      if (typeof bv === 'string') bv = bv.toLowerCase()
      return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
    })
    return rows
  }, [columns, search, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const SortHeader = ({ label, k }: { label: string; k: SortKey }) => (
    <th
      className="text-left px-3 py-2 font-medium cursor-pointer hover:text-foreground select-none whitespace-nowrap"
      onClick={() => toggleSort(k)}
    >
      <span className="inline-flex items-center gap-1">
        {label} <ArrowUpDown className="h-3 w-3 opacity-50" />
      </span>
    </th>
  )

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Profile Details</CardTitle>
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
        ) : (
          <>
            <Input
              className="mb-2 h-7 text-xs"
              placeholder="Search columns…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            <div className="overflow-auto flex-1">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b border-border text-muted-foreground">
                    <SortHeader label="Column" k="column" />
                    <th className="text-left px-3 py-2 font-medium">Type</th>
                    <SortHeader label="Null %" k="null_rate" />
                    <SortHeader label="Cardinality" k="cardinality" />
                    <th className="text-left px-3 py-2 font-medium">PK</th>
                    <SortHeader label="Classification" k="data_classification" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <tr key={row.name} className="border-b border-border last:border-0 hover:bg-muted/30">
                      <td className="px-3 py-1.5 font-mono">{row.name}</td>
                      <td className="px-3 py-1.5 text-muted-foreground">{row.dtype}</td>
                      <td className="px-3 py-1.5">{(row.null_rate * 100).toFixed(1)}%</td>
                      <td className="px-3 py-1.5">{row.cardinality.toLocaleString()}</td>
                      <td className="px-3 py-1.5">
                        {row.pk_candidate ? <span className="text-green-600 dark:text-green-400">✓</span> : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="px-3 py-1.5">
                        <Badge variant={CLASS_VARIANT[row.classification] ?? 'muted'}>
                          {row.classification}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr><td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">No columns match.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
