import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, RefreshCw, ShieldAlert } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, ElectionResults } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'

/**
 * Backend demo tally (organizer-only, after close). Per the API contract the
 * `disclaimer` string must be shown as-is: results are NOT independently
 * verified yet.
 */
export default function ResultsAudit() {
  const { id } = useParams<{ id: string }>()
  const [results, setResults] = useState<ElectionResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const fetchResults = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      setResults(await api.getResults(id))
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchResults()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (loading && !results) return <LoadingSpinner label="Loading results..." />

  if (!results) {
    const notClosed = error?.error === 'ELECTION_NOT_CLOSED'
    const forbidden = error?.error === 'FORBIDDEN' || error?.error === 'UNAUTHENTICATED'
    return (
      <div className="mx-auto max-w-xl px-4 py-12 text-center">
        <ErrorMessage
          error={
            notClosed
              ? { error: 'ELECTION_NOT_CLOSED', message: 'Results become available once the election is closed and its result hash is published.' }
              : forbidden
                ? { error: 'FORBIDDEN', message: 'Results are visible to the election organizer. Sign in with the organizer account.' }
                : error || 'Unable to retrieve results.'
          }
        />
        <Link to="/organizer" className="mt-4 inline-block">
          <Button variant="secondary">Back to dashboard</Button>
        </Link>
      </div>
    )
  }

  const total = results.total_ballots
  const pct = (votes: number) => (total > 0 ? Math.round((votes / total) * 1000) / 10 : 0)
  const counts = [...results.counts].sort((a, b) => b.votes - a.votes)

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <Link
          to="/organizer"
          className="inline-flex items-center gap-2 font-mono text-xs text-ash transition hover:text-paper"
        >
          <ArrowLeft className="h-4 w-4" />
          BACK TO DASHBOARD
        </Link>

        <Button variant="ghost" size="sm" onClick={fetchResults}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <div className="rounded-3xl border border-white/10 bg-charcoal/60 p-6 backdrop-blur-xl sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={results.status} type="election" />
              <StatusBadge status={results.published_result_status} type="commitment" />
            </div>
            <p className="mt-2 font-mono text-[11px] text-ash/70">
              Tally type: {results.tally_type} · election {results.election_id}
            </p>
          </div>

          <div className="text-right">
            <p className="font-mono text-[10px] tracking-wider text-ash">TOTAL BALLOTS</p>
            <p className="font-display text-3xl font-bold text-saffron">{total}</p>
          </div>
        </div>

        {/* Mandatory disclaimer (API contract: show as-is) */}
        <div className="mt-4 flex items-start gap-3 rounded-2xl border border-amber-500/40 bg-amber-950/20 p-4 text-xs leading-relaxed text-amber-200">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <span>{results.disclaimer}</span>
        </div>

        {/* Tally */}
        <div className="mt-6 space-y-4">
          <h2 className="font-mono text-xs font-semibold tracking-wider text-ash">FINAL TALLY</h2>

          <div className="space-y-4">
            {counts.map((cand) => (
              <div key={cand.candidate_id} className="rounded-2xl border border-white/10 bg-obsidian/70 p-4">
                <div className="flex items-center justify-between font-display text-sm">
                  <span className="font-bold text-paper">
                    {cand.name}
                    <span className="ml-2 font-mono text-[10px] text-ash/70">#{cand.chain_index}</span>
                  </span>
                  <span className="font-mono text-xs font-bold text-saffron">
                    {cand.votes} votes ({pct(cand.votes)}%)
                  </span>
                </div>

                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                  <div className="h-full bg-saffron transition-all duration-500" style={{ width: `${pct(cand.votes)}%` }} />
                </div>
              </div>
            ))}
            {counts.length === 0 && (
              <p className="py-4 text-center font-mono text-xs text-ash">No votes were recorded.</p>
            )}
          </div>
        </div>

        {/* Publication summary */}
        <div className="mt-8 space-y-2 rounded-2xl border border-white/10 bg-obsidian/80 p-5 font-mono text-xs">
          <div className="border-b border-white/10 pb-2">
            <span className="text-ash">RESULT PUBLICATION:</span>{' '}
            <span className="font-bold text-paper">{results.published_result_status.toUpperCase()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-ash">CHAIN JOBS:</span>
            <span>
              <span className="text-emerald-400">{results.publications.confirmed ?? 0} confirmed</span>{' '}
              · <span className="text-amber-300">{results.publications.pending ?? 0} pending</span>{' '}
              · <span className="text-red-400">{results.publications.failed ?? 0} failed</span>
            </span>
          </div>
          {(results.publications.pending ?? 0) > 0 && (
            <p className="pt-1 text-[10px] text-amber-300">
              Jobs are still publishing — refresh, or use the publication monitor on the manage page.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
