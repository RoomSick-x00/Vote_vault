import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Play, Plus, RefreshCw, Square, Users, Vote } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, Election, VoterRecord } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { ConfirmationModal } from '../components/ui/ConfirmationModal'
import ShareCard from '../components/ShareCard'
import VoterRoster from '../components/VoterRoster'
import VerificationSetup from '../components/VerificationSetup'
import PublicationsPanel from '../components/PublicationsPanel'

/**
 * Lifecycle per the backend: draft → open → closing → closed. `closing` means
 * close was requested and accepted ballots are still draining onto the chain;
 * the UI polls until the close publication confirms and status flips to closed.
 */
export default function ManageElection() {
  const { id } = useParams<{ id: string }>()
  const [election, setElection] = useState<Election | null>(null)
  const [voters, setVoters] = useState<VoterRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [pubRefresh, setPubRefresh] = useState(0)

  const [modal, setModal] = useState<'open' | 'close' | null>(null)
  const [acting, setActing] = useState(false)

  const load = useCallback(
    async (silent = false) => {
      if (!id) return
      if (!silent) setLoading(true)
      setError(null)
      try {
        const [e, roster] = await Promise.all([api.getElection(id), api.getVoters(id)])
        setElection(e)
        setVoters(roster.voters)
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
  }, [id, load])

  // While closing, poll until the close publication confirms and status becomes closed.
  useEffect(() => {
    if (election?.status !== 'closing') return
    const timer = setInterval(async () => {
      try {
        const e = await api.getElection(election.election_id)
        setElection(e)
        if (e.status !== 'closing') setPubRefresh((k) => k + 1)
      } catch {
        /* transient poll failure — next tick retries */
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [election?.status, election?.election_id])

  const openVoting = async () => {
    if (!id) return
    setActing(true)
    setError(null)
    try {
      await api.openElection(id)
      setModal(null)
      await load(true)
      setPubRefresh((k) => k + 1)
    } catch (err) {
      setError(err as ApiError)
      setModal(null)
    } finally {
      setActing(false)
    }
  }

  const closeVoting = async () => {
    if (!id) return
    setActing(true)
    setError(null)
    try {
      await api.closeElection(id)
      setModal(null)
      await load(true)
      setPubRefresh((k) => k + 1)
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
  const isClosing = election.status === 'closing'
  const isClosed = election.status === 'closed'
  const verificationUnset =
    (election.voter_schema?.identityColumns?.length ?? 0) === 0 ||
    (election.voter_schema?.otpChannels?.length ?? 0) === 0

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
        <div className="flex items-center gap-3">
          {!isClosing && (
            <Button variant="ghost" size="sm" onClick={() => load(true)}>
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
          )}
        </div>
      </div>

      {error && <ErrorMessage error={error} className="mb-6" />}

      <div className="rounded-3xl border border-white/10 bg-charcoal/60 p-6 backdrop-blur-xl sm:p-8">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <StatusBadge status={election.status} type="election" />
            </div>
            <h1 className="font-display text-3xl font-bold text-paper">{election.title}</h1>
            <p className="font-mono text-[11px] text-ash/70">ID {election.election_id}</p>
            <div className="flex flex-wrap items-center gap-6 pt-1 font-mono text-xs text-ash">
              <span className="flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-saffron" />
                {voters.length} eligible voters
              </span>
              <span className="flex items-center gap-1.5">
                <Vote className="h-3.5 w-3.5 text-electric" />
                {election.candidates.length} candidates
              </span>
              {election.opens_at && (
                <span>opens {new Date(election.opens_at).toLocaleString()}</span>
              )}
              {election.closes_at && (
                <span>closes {new Date(election.closes_at).toLocaleString()}</span>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            {isDraft && (
              <Button
                onClick={() => setModal('open')}
                disabled={voters.length === 0 || verificationUnset}
                title={verificationUnset ? 'Select verification attributes from the roster first' : undefined}
              >
                <Play className="h-4 w-4" />
                Open voting
              </Button>
            )}
            {(isOpen || isClosing) && (
              <Button variant="danger" onClick={() => setModal('close')} disabled={isClosing}>
                {isClosing ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Closing…
                  </>
                ) : (
                  <>
                    <Square className="h-4 w-4" />
                    Close & tally
                  </>
                )}
              </Button>
            )}
            {isClosed && (
              <Link to={`/results/${election.election_id}`}>
                <Button>View results →</Button>
              </Link>
            )}
          </div>
        </div>

        {isDraft && voters.length === 0 && (
          <p className="mt-4 font-mono text-xs text-amber-300">
            Add at least one eligible voter before opening the election.
          </p>
        )}
        {isDraft && election.candidates.length === 0 && (
          <p className="mt-4 font-mono text-xs text-amber-300">
            Add at least one candidate before opening the election.
          </p>
        )}
        {isDraft && verificationUnset && voters.length > 0 && (
          <p className="mt-4 font-mono text-xs text-amber-300">
            Select which roster columns verify voters (below) before opening the election.
          </p>
        )}
        {isClosing && (
          <p className="mt-4 rounded-2xl border border-sky-500/30 bg-sky-950/20 p-3 font-mono text-xs text-sky-300">
            Close requested — accepted ballots are draining onto the chain. Status becomes `closed` once the close
            publication confirms. No new ballots are accepted.
          </p>
        )}
      </div>

      {!isClosed && (
        <div className="mt-8">
          <h2 className="mb-3 font-mono text-xs font-semibold tracking-wider text-ash">SHARE WITH VOTERS</h2>
          <ShareCard electionCode={election.code} title={election.title} />
        </div>
      )}

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.3fr_1.3fr_1fr]">
        <div className="space-y-4 self-start rounded-3xl border border-white/10 bg-charcoal/40 p-6">
          <h2 className="border-b border-white/10 pb-3 font-display text-lg font-bold text-paper">Candidates</h2>
          {election.candidates.map((c) => (
            <div key={c.candidate_id} className="rounded-2xl border border-white/10 bg-obsidian/70 p-4">
              <p className="font-mono text-[10px] text-saffron">CHAIN INDEX {c.chain_index}</p>
              <p className="mt-1 font-display font-bold text-paper">{c.name}</p>
              {c.description && <p className="mt-1 text-xs text-ash">{c.description}</p>}
            </div>
          ))}
          {isDraft && <DraftCandidates electionId={election.election_id} onAdded={() => load(true)} />}
          {!isDraft && (
            <p className="font-mono text-[10px] text-ash/70">
              Candidate set is frozen — the chain index above is immutable once voting has opened.
            </p>
          )}
        </div>

        <VoterRoster
          electionId={election.election_id}
          voters={voters}
          onChanged={() => load(true)}
          disabled={isClosing || isClosed}
          canUpload={isDraft || isOpen}
          canDelete={isDraft}
        />

        <VerificationSetup election={election} voters={voters} onChanged={() => load(true)} />
      </div>

      <div className="mt-8"><Link to={`/audit/${election.election_id}`} className="text-saffron">Inspect public audit records</Link></div>
      <div className="mt-8">
        <PublicationsPanel electionId={election.election_id} refreshKey={pubRefresh} />
      </div>

      <ConfirmationModal
        isOpen={modal === 'open'}
        title="Open voting?"
        description="Voters on the uploaded roster can verify their contact and cast a ballot. The candidate set and configuration freeze and are committed on chain."
        confirmText="Open voting"
        isLoading={acting}
        onConfirm={openVoting}
        onCancel={() => setModal(null)}
      />
      <ConfirmationModal
        isOpen={modal === 'close'}
        title="Close election and tally?"
        description="No more ballots are accepted. Accepted ballots drain onto the chain, then the demo tally is computed and its hash published. This may take a moment."
        confirmText="Close election"
        variant="danger"
        isLoading={acting}
        onConfirm={closeVoting}
        onCancel={() => setModal(null)}
      />
    </div>
  )
}

/** Draft-only inline form to append more candidate names. */
function DraftCandidates({ electionId, onAdded }: { electionId: string; onAdded: () => void }) {
  const [name, setName] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const add = async () => {
    if (!name.trim()) return
    setAdding(true)
    setError(null)
    try {
      await api.addCandidates(electionId, [{ name: name.trim() }])
      setName('')
      onAdded()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="space-y-3 border-t border-white/10 pt-4">
      <div className="flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Add another candidate…"
          aria-label="New candidate name"
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper focus:border-saffron focus:outline-none"
        />
        <Button size="sm" onClick={add} isLoading={adding} loadingText="…" disabled={!name.trim()}>
          <Plus className="h-3.5 w-3.5" />
          Add
        </Button>
      </div>
      {error && <ErrorMessage error={error} />}
    </div>
  )
}
