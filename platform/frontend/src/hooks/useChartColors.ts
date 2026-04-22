import { useThemeStore } from '@/store/themeStore'

export interface ChartColors {
  primary: string
  muted: string
  anomaly: string
  kde: string
  refLine: string
  gridLine: string
}

export function useChartColors(): ChartColors {
  const { resolvedTheme } = useThemeStore()
  const isDark = resolvedTheme === 'dark'

  return {
    primary:  isDark ? '#60a5fa' : '#3b82f6',
    muted:    isDark ? '#475569' : '#cbd5e1',
    anomaly:  isDark ? '#f97316' : '#ef4444',
    kde:      isDark ? '#a78bfa' : '#8b5cf6',
    refLine:  isDark ? '#64748b' : '#94a3b8',
    gridLine: isDark ? '#1e293b' : '#e2e8f0',
  }
}
