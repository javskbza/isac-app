import { create } from 'zustand'

interface User {
  id: string
  email: string
  full_name?: string
  role: 'admin' | 'viewer'
}

interface AuthState {
  token: string | null
  user: User | null
  login: (token: string, user: User) => void
  logout: () => void
}

const SESSION_KEY = 'auth'

function loadSession(): Pick<AuthState, 'token' | 'user'> {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return { token: null, user: null }
}

export const useAuthStore = create<AuthState>((set) => ({
  ...loadSession(),
  login: (token, user) => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ token, user }))
    set({ token, user })
  },
  logout: () => {
    sessionStorage.removeItem(SESSION_KEY)
    set({ token: null, user: null })
  },
}))
