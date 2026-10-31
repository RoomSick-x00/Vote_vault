import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Clock, Plus, RefreshCw, Users, Vote } from 'lucide-react'
import { api } from '../services/api'
import { useAuth } from '../context/AuthContext'
import type { ApiError, Election } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'

/** Dashboard: server-side list of elections in organizations the user organizes. */
export default function OrganizerDashboard() {
  const { user } = useAuth()
  const [elections, setElections] = useState<Election[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setElections((await api.getElections()).elections)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const stats = [
    { label: 'ELECTIONS', value: elections.length, tone: 'text-paper' },
    { label: 'VOTING OPEN', value: elections.filter((e) => e.status === 'open').length, tone: 'text-emerald-400' },
    { label: 'CLOSING', value: elections.filter((e) => e.status === 'closing').length, tone: 'text-electric' },
    { label: 'CLOSED', value: elections.filter((e) => e.status === 'closed').length, tone: 'text-amber-400' },
  ]

  const orgName = user?.organizations?.[0]?.name

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center">
        <div>
          <span className="rounded bg-saffron/10 px-2.5 py-0.5 font-mono text-[10px] font-bold text-saffron">
            ORGANISER
          </span>
          <h1 className="mt-2 font-display text-3xl font-bold text-paper">Your elections</h1>
          <p className="mt-1 text-sm text-ash">
            Signed in as {user?.full_name || user?.email}
            {orgName ? ` · ${orgName}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Link to="/organizer/create">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              Create election
            </Button>
          </Link>
        </div>
      </div>

      {error && <ErrorMessage error={error} onRetry={load} className="mt-6" />}

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-2xl border border-white/10 bg-charcoal/40 p-4">
            <p className="font-mono text-[10px] tracking-wider text-ash">{s.label}</p>
            <p className={`mt-1 font-display text-2xl font-bold ${s.tone}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-8">
        {loading ? (
          <LoadingSpinner label="Loading your elections..." />
        ) : elections.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-white/20 bg-charcoal/20 p-12 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-ash">
              <Vote className="h-7 w-7" />
            </div>
            <h3 className="mt-4 font-display text-lg font-bold text-paper">No elections yet</h3>
            <p className="mx-auto mt-2 max-w-md text-sm text-ash">
              Create a draft election, add candidates and eligible voters, then open it for voting.
            </p>
            <Link to="/organizer/create" className="mt-6 inline-block">
              <Button>
                <Plus className="h-4 w-4" />
                Create your first election
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {elections.map((e) => (
              <div
                key={e.election_id}
                className="flex flex-col justify-between gap-6 rounded-3xl border border-white/10 bg-charcoal/50 p-6 transition hover:border-white/20 lg:flex-row lg:items-center"
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <StatusBadge status={e.status} type="election" />
                  </div>
                  <div>
                    <h3 className="font-display text-xl font-bold text-paper">{e.title}</h3>
                    <p className="mt-0.5 font-mono text-[11px] text-ash/70">
                      ID {e.election_id}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-6 font-mono text-xs text-ash">
                    <span className="flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 text-saffron" />
                      {e.candidates.length} candidates
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" />
                      {new Date(e.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-3">
                  <Link to={`/organizer/elections/${e.election_id}`}>
                    <Button variant="secondary" size="sm">
                      Manage
                    </Button>
                  </Link>
                  {e.status === 'closed' && (
                    <Link to={`/results/${e.election_id}`}>
                      <Button size="sm">
                        Results
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
