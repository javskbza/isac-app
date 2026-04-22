import { create } from 'zustand'

export interface AuthUser {
  id: string
  email: string
  full_name?: string
  role: 'admin' | 'viewer'
  theme_preference: 'light' | 'dark' | 'system'
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  login: (token: string, user: AuthUser) => void
  logout: () => void
}

const STORAGE_KEY = 'auth'

function loadSession(): Pick<AuthState, 'token' | 'user'> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return { token: null, user: null }
}

export const useAuthStore = create<AuthState>((set) => ({
  ...loadSession(),
  login: (token, user) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user }))
    set({ token, user })
  },
  logout: () => {
    localStorage.removeItem(STORAGE_KEY)
    set({ token: null, user: null })
  },
}))
