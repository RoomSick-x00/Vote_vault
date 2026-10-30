import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Organizer } from '../types'
import { api, getOrganizerToken } from '../services/api'

interface AuthContextValue {
  user: Organizer | null
  loading: boolean
  sessionExpired: boolean
  signup: (payload: {
    email: string
    password: string
    full_name: string
    organization_name: string
  }) => Promise<Organizer>
  login: (email: string, password: string) => Promise<Organizer>
  logout: () => void
  /** Found an organization for the signed-in user; updates the session's org list. */
  createOrganization: (name: string) => Promise<{ organization_id: string; name: string; role: string }>
  clearSessionExpired: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function toOrganizer(me: { user_id: string; email: string; full_name: string; organizations: Organizer['organizations'] }): Organizer {
  return { user_id: me.user_id, email: me.email, full_name: me.full_name, organizations: me.organizations }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Organizer | null>(null)
  const [loading, setLoading] = useState<boolean>(!!getOrganizerToken())
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    let active = true
    if (getOrganizerToken()) {
      api
        .getMe()
        .then((me) => active && me && setUser(toOrganizer(me)))
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

  const signup = useCallback<AuthContextValue['signup']>(async (payload) => {
    setSessionExpired(false)
    const session = await api.signup(payload)
    const organizer = toOrganizer({ ...session.user, organizations: session.organizations })
    setUser(organizer)
    return organizer
  }, [])

  const login = useCallback<AuthContextValue['login']>(async (email, password) => {
    setSessionExpired(false)
    const session = await api.login(email, password)
    const organizer = toOrganizer({ ...session.user, organizations: session.organizations })
    setUser(organizer)
    return organizer
  }, [])

  const logout = useCallback(() => {
    api.logout()
    setUser(null)
  }, [])

  const createOrganization = useCallback<AuthContextValue['createOrganization']>(async (name) => {
    const org = await api.createOrganization(name)
    setUser(
      (prev) =>
        prev
          ? {
              ...prev,
              organizations: [
                ...prev.organizations,
                { organization_id: org.organization_id, name: org.name, role: org.role },
              ],
            }
          : prev
    )
    return org
  }, [])

  const clearSessionExpired = useCallback(() => setSessionExpired(false), [])

  const value = useMemo(
    () => ({ user, loading, sessionExpired, signup, login, logout, createOrganization, clearSessionExpired }),
    [user, loading, sessionExpired, signup, login, logout, createOrganization, clearSessionExpired]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
