import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Play, RefreshCw, Square, Users, Vote } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, Election, VoterRecord } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { ConfirmationModal } from '../components/ui/ConfirmationModal'
import ShareCard from '../components/ShareCard'
import VoterDatabase from '../components/VoterDatabase'

export default function ManageElection() {
  const { id } = useParams<{ id: string }>()
  const [election, setElection] = useState<Election | null>(null)
  const [voters, setVoters] = useState<VoterRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const [modal, setModal] = useState<'open' | 'close' | null>(null)
  const [acting, setActing] = useState(false)

  const load = useCallback(
    async (silent = false) => {
      if (!id) return
      if (!silent) setLoading(true)
      setError(null)
      try {
        const [e, v] = await Promise.all([api.getElection(id), api.getVoters(id)])
        setElection(e)
        setVoters(v)
      } catch (err) {
        setError(err as ApiError)
      } finally {
        setLoading(false)
      }
    },
    [id]
  )

  useEffect(() => {
    load()
  }, [load])

  const changeStatus = async (status: 'open' | 'closed') => {
    if (!id) return
    setActing(true)
    setError(null)
    try {
      setElection(await api.updateElectionStatus(id, status))
      setModal(null)
    } catch (err) {
      setError(err as ApiError)
      setModal(null)
    } finally {
      setActing(false)
    }
  }

  if (loading) return <LoadingSpinner label="Loading election..." />

  if (!election) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12 text-center">
        <ErrorMessage error={error || 'Election not found.'} />
        <Link to="/organizer" className="mt-4 inline-block">
          <Button variant="secondary">Back to dashboard</Button>
        </Link>
      </div>
    )
  }

  const isDraft = election.status === 'draft'
  const isOpen = election.status === 'open'
  const isClosed = election.status === 'closed'

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <Link
          to="/organizer"
          className="inline-flex items-center gap-2 font-mono text-xs text-ash transition hover:text-paper"
        >
          <ArrowLeft className="h-4 w-4" />
          BACK TO DASHBOARD
        </Link>
        <Button variant="ghost" size="sm" onClick={() => load(true)}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {error && <ErrorMessage error={error} className="mb-6" />}

      <div className="rounded-3xl border border-white/10 bg-charcoal/60 p-6 backdrop-blur-xl sm:p-8">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <StatusBadge status={election.status} type="election" />
              <StatusBadge status={election.publicationStatus} type="publication" />
            </div>
            <h1 className="font-display text-3xl font-bold text-paper">{election.title}</h1>
            {election.description && (
              <p className="max-w-2xl text-sm leading-relaxed text-ash">{election.description}</p>
            )}
            <div className="flex flex-wrap items-center gap-6 pt-1 font-mono text-xs text-ash">
              <span className="flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-saffron" />
                {voters.length} voters
              </span>
              <span className="flex items-center gap-1.5">
                <Vote className="h-3.5 w-3.5 text-electric" />
                {election.ballotCount} ballots cast
              </span>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            {isDraft && (
              <Button onClick={() => setModal('open')} disabled={voters.length === 0}>
                <Play className="h-4 w-4" />
                Open voting
              </Button>
            )}
            {isOpen && (
              <Button variant="danger" onClick={() => setModal('close')}>
                <Square className="h-4 w-4" />
                Close & publish results
              </Button>
            )}
            {isClosed && (
              <Link to={`/results/${election.id}`}>
                <Button>View results →</Button>
              </Link>
            )}
          </div>
        </div>
        {isDraft && voters.length === 0 && (
          <p className="mt-4 font-mono text-xs text-amber-300">Add at least one voter before opening the election.</p>
        )}
      </div>

      {!isClosed && (
        <div className="mt-8">
          <h2 className="mb-3 font-mono text-xs font-semibold tracking-wider text-ash">SHARE WITH VOTERS</h2>
          <ShareCard code={election.code} title={election.title} />
        </div>
      )}

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-4 self-start rounded-3xl border border-white/10 bg-charcoal/40 p-6">
          <h2 className="border-b border-white/10 pb-3 font-display text-lg font-bold text-paper">Candidates</h2>
          {election.candidates.map((c, i) => (
            <div key={c.id} className="rounded-2xl border border-white/10 bg-obsidian/70 p-4">
              <p className="font-mono text-[10px] text-saffron">CANDIDATE {i + 1}</p>
              <p className="mt-1 font-display font-bold text-paper">{c.name}</p>
              {c.description && <p className="mt-1 text-xs leading-relaxed text-ash">{c.description}</p>}
            </div>
          ))}
        </div>

        <VoterDatabase election={election} voters={voters} onChanged={() => load(true)} />
      </div>

      <ConfirmationModal
        isOpen={modal === 'open'}
        title="Open voting?"
        description="Voters will be able to join with the election code and cast ballots. Candidates can no longer be changed."
        confirmText="Open voting"
        isLoading={acting}
        onConfirm={() => changeStatus('open')}
        onCancel={() => setModal(null)}
      />
      <ConfirmationModal
        isOpen={modal === 'close'}
        title="Close election and publish results?"
        description="This is permanent. No more ballots can be cast, and the final tally will be computed and recorded."
        confirmText="Close election"
        variant="danger"
        isLoading={acting}
        onConfirm={() => changeStatus('closed')}
        onCancel={() => setModal(null)}
      />
    </div>
  )
}
