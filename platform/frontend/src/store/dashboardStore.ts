import { create } from 'zustand'
import type { Layout } from 'react-grid-layout'
import api from '@/lib/api'

export interface WidgetState {
  selected_column?: string
  selected_date_column?: string
}

interface DashboardStore {
  layout: Layout[]
  widgetState: Record<string, WidgetState>
  selectedSourceId: string | null
  isLoaded: boolean

  fetchLayout: () => Promise<void>
  saveLayout: (layout: Layout[], widgetState: Record<string, WidgetState>) => void
  setSelectedSource: (id: string) => void
  setWidgetState: (widgetId: string, key: keyof WidgetState, value: string) => void
}

const DEFAULT_LAYOUT: Layout[] = [
  { i: 'data_profile',      x: 0,  y: 0,  w: 4,  h: 3 },
  { i: 'profile_details',   x: 4,  y: 0,  w: 8,  h: 3 },
  { i: 'descriptive_stats', x: 0,  y: 3,  w: 6,  h: 4 },
  { i: 'trend_analysis',    x: 6,  y: 3,  w: 6,  h: 4 },
  { i: 'anomaly_detection', x: 0,  y: 7,  w: 6,  h: 4 },
  { i: 'forecast',          x: 6,  y: 7,  w: 6,  h: 4 },
  { i: 'insights',          x: 0,  y: 11, w: 12, h: 4 },
]

let saveTimer: ReturnType<typeof setTimeout> | null = null

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  layout: DEFAULT_LAYOUT,
  widgetState: {},
  selectedSourceId: null,
  isLoaded: false,

  async fetchLayout() {
    try {
      const [layoutRes, meRes] = await Promise.all([
        api.get('/api/dashboard/layout'),
        api.get('/api/users/me').catch(() => null),
      ])
      const data = layoutRes.data
      const layout: Layout[] = data.grid ?? DEFAULT_LAYOUT
      const widgetState: Record<string, WidgetState> = data.widget_state ?? {}
      const selectedSourceId = meRes?.data?.last_selected_source_id ?? null
      set({ layout, widgetState, selectedSourceId, isLoaded: true })
    } catch {
      set({ layout: DEFAULT_LAYOUT, widgetState: {}, isLoaded: true })
    }
  },

  saveLayout(layout, widgetState) {
    set({ layout, widgetState })
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      api.put('/api/dashboard/layout', { grid: layout, widget_state: widgetState }).catch(() => {})
    }, 500)
  },

  setSelectedSource(id) {
    set({ selectedSourceId: id })
    api.patch('/api/users/me/preferences', { last_selected_source_id: id }).catch(() => {})
  },

  setWidgetState(widgetId, key, value) {
    const { widgetState, layout } = get()
    const updated = { ...widgetState, [widgetId]: { ...widgetState[widgetId], [key]: value } }
    get().saveLayout(layout, updated)
  },
}))
