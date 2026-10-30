import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Organizer } from '../types'
import { api, getOrganizerToken } from '../services/api'

interface AuthContextValue {
  user: Organizer | null
  loading: boolean
  sessionExpired: boolean
  register: (payload: { name: string; email: string; password: string; organization?: string }) => Promise<Organizer>
  login: (email: string, password: string) => Promise<Organizer>
  logout: () => Promise<void>
  clearSessionExpired: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Organizer | null>(null)
  const [loading, setLoading] = useState<boolean>(!!getOrganizerToken())
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    let active = true
    if (getOrganizerToken()) {
      api
        .getMe()
        .then((me) => active && setUser(me))
        .finally(() => active && setLoading(false))
    }

    const onExpired = () => {
      setUser(null)
      setSessionExpired(true)
    }
    window.addEventListener('votevault:session-expired', onExpired)
    return () => {
      active = false
      window.removeEventListener('votevault:session-expired', onExpired)
    }
  }, [])

  const register = useCallback<AuthContextValue['register']>(async (payload) => {
    setSessionExpired(false)
    const session = await api.register(payload)
    setUser(session.user)
    return session.user
  }, [])

  const login = useCallback<AuthContextValue['login']>(async (email, password) => {
    setSessionExpired(false)
    const session = await api.login(email, password)
    setUser(session.user)
    return session.user
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])

  const clearSessionExpired = useCallback(() => setSessionExpired(false), [])

  const value = useMemo(
    () => ({ user, loading, sessionExpired, register, login, logout, clearSessionExpired }),
    [user, loading, sessionExpired, register, login, logout, clearSessionExpired]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
