import { create } from 'zustand'
import api from '@/lib/api'

export type Theme = 'light' | 'dark' | 'system'

interface ThemeStore {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
  init: (serverTheme: Theme) => void
}

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

function resolve(theme: Theme): 'light' | 'dark' {
  return theme === 'system' ? getSystemTheme() : theme
}

function applyTheme(resolved: 'light' | 'dark') {
  const root = document.documentElement
  if (resolved === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

let persistTimer: ReturnType<typeof setTimeout> | null = null

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: 'light',
  resolvedTheme: 'light',

  init(serverTheme: Theme) {
    const resolved = resolve(serverTheme)
    applyTheme(resolved)
    set({ theme: serverTheme, resolvedTheme: resolved })

    // Keep resolved in sync when OS preference changes (only matters for 'system' mode)
    if (typeof window !== 'undefined') {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const current = get().theme
        if (current === 'system') {
          const newResolved = getSystemTheme()
          applyTheme(newResolved)
          set({ resolvedTheme: newResolved })
        }
      })
    }
  },

  setTheme(theme: Theme) {
    const resolved = resolve(theme)
    applyTheme(resolved)
    set({ theme, resolvedTheme: resolved })

    // Debounced persist to server
    if (persistTimer) clearTimeout(persistTimer)
    persistTimer = setTimeout(() => {
      api.patch('/api/users/me/preferences', { theme_preference: theme }).catch(() => {
        // Non-fatal: preference will re-sync on next login
      })
    }, 300)
  },
}))
