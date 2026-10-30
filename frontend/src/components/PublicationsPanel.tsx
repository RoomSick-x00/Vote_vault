import { useCallback, useEffect, useRef, useState } from 'react'
import { Link2, Loader2, RefreshCw, RotateCcw } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, PublicationJob, PublicationsOut } from '../types'
import { StatusBadge } from './ui/StatusBadge'
import { Button } from './ui/Button'

interface PublicationsPanelProps {
  electionId: string
  /** Refresh trigger from the parent (e.g. after open/close actions). */
  refreshKey?: number
}

const JOB_LABELS: Record<string, string> = {
  register_election: 'Register election',
  open_election: 'Open election',
  publish_ballot: 'Publish ballot',
  close_election: 'Close election',
  publish_result: 'Publish result',
}

/** Organizer view of every chain publication job for this election, with operator retry. */
export default function PublicationsPanel({ electionId, refreshKey = 0 }: PublicationsPanelProps) {
  const [data, setData] = useState<PublicationsOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true)
      try {
        setData(await api.getPublications(electionId))
        setError(null)
      } catch (err) {
        setError(err as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [electionId]
  )

  useEffect(() => {
    load()
  }, [load, refreshKey])

  // Keep the monitor live while jobs are still draining to the chain.
  useEffect(() => {
    const hasPending = (data?.summary.pending ?? 0) > 0 || data?.publications.some((j) => j.status === 'pending')
    pollRef.current = setInterval(
      () => {
        // While closing, the election itself is also transitioning — parent polls that.
        load(true)
      },
      hasPending ? 2500 : 15000
    )
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [data?.summary.pending, data?.publications, load])

  const retry = async () => {
    setRetrying(true)
    try {
      await api.retryPublications(electionId)
      await load(true)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setRetrying(false)
    }
  }

  const summary = data?.summary ?? {}
  const jobs: PublicationJob[] = [...(data?.publications ?? [])].sort((a, b) =>
    a.created_at.localeCompare(b.created_at)
  )

  return (
    <div className="rounded-3xl border border-white/10 bg-charcoal/40 p-6">
      <div className="flex flex-col justify-between gap-3 border-b border-white/10 pb-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="font-display text-lg font-bold text-paper">Blockchain publications</h2>
          <p className="mt-0.5 font-mono text-[10px] text-ash">
            Local Hardhat chain · every job is receipt-verified on chain id 31337
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-3 font-mono text-[11px]">
            <span className="text-emerald-400">{summary.confirmed ?? 0} confirmed</span>
            <span className="text-amber-300">{summary.pending ?? 0} pending</span>
            <span className="text-red-400">{summary.failed ?? 0} failed</span>
          </span>
          <Button variant="ghost" size="sm" onClick={() => load(true)}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button variant="secondary" size="sm" onClick={retry} isLoading={retrying} loadingText="Requeuing...">
            <RotateCcw className="h-3.5 w-3.5" />
            Retry failed
          </Button>
        </div>
      </div>

      {error && (
        <p className="mt-3 font-mono text-[11px] text-red-400">
          {error.message} — is the Hardhat node and backend publisher running?
        </p>
      )}

      {loading && !data ? (
        <div className="flex items-center gap-2 py-6 font-mono text-xs text-ash">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading publication jobs…
        </div>
      ) : jobs.length === 0 ? (
        <p className="py-6 text-center font-mono text-xs text-ash">No publication jobs yet.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {jobs.map((job) => (
            <li key={job.job_id} className="rounded-2xl border border-white/10 bg-obsidian/70 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <StatusBadge status={job.status} type="publication" />
                  <span className="font-display text-sm font-bold text-paper">
                    {JOB_LABELS[job.job_type] ?? job.job_type}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-ash">
                  attempts {job.attempts}/{job.max_attempts}
                </span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1 font-mono text-[10px] text-ash">
                {job.block_number != null && (
                  <span>
                    block <span className="text-paper">#{job.block_number}</span>
                  </span>
                )}
                {job.receipt_id && (
                  <span className="max-w-[220px] truncate" title={job.receipt_id}>
                    ballot <span className="text-paper/70">{job.receipt_id}</span>
                  </span>
                )}
                {job.transaction_hash && (
                  <a
                    href={`#tx-${job.transaction_hash}`}
                    onClick={(e) => {
                      e.preventDefault()
                      navigator.clipboard?.writeText(job.transaction_hash || '')
                    }}
                    className="flex items-center gap-1 text-paper/60 transition hover:text-saffron"
                    title={`${job.transaction_hash} (click to copy)`}
                  >
                    <Link2 className="h-3 w-3" />
                    <span className="max-w-[140px] truncate">{job.transaction_hash}</span>
                  </a>
                )}
                {job.status === 'pending' && job.next_attempt_at && (
                  <span>next attempt {new Date(job.next_attempt_at).toLocaleTimeString()}</span>
                )}
              </div>

              {job.last_error && (
                <p className="mt-2 break-all rounded-lg border border-red-500/20 bg-red-950/20 p-2 font-mono text-[10px] text-red-300">
                  {job.last_error}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
