import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Check, Lock, Receipt } from 'lucide-react'
import { api, getRememberedReceipt, getVoterToken } from '../services/api'
import type { ApiError, Election } from '../types'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { isElectionId } from '../lib/code'
import VoterSignIn from '../components/voter/VoterSignIn'
import BallotStep from '../components/voter/BallotStep'

/**
 * Voter flow for this milestone: open the election link → sign in with the
 * Supabase account the organizer whitelisted → cast one ballot → receipt.
 * The old code+OTP flow has no backend endpoints yet and was removed.
 */
export default function VoterSession() {
  const params = useParams<{ electionId: string }>()
  const electionId = params.electionId || ''

  const [election, setElection] = useState<Election | null>(null)
  const [loading, setLoading] = useState(true)
  const [needsSignIn, setNeedsSignIn] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [session, setSession] = useState(0) // bump to reload election after sign-in

  const rememberedReceipt = getRememberedReceipt(electionId)
  const signedIn = !!getVoterToken()

  const loadElection = useCallback(async () => {
    if (!isElectionId(electionId)) {
      setError({ error: 'NOT_FOUND', message: 'That election link is not valid.' })
      setLoading(false)
      return
    }
    if (!getVoterToken()) {
      setNeedsSignIn(true)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setElection(await api.getElection(electionId, 'voter'))
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr.error === 'UNAUTHENTICATED' || apiErr.error === 'FORBIDDEN') {
        // 403 on a draft, or a token whose account cannot see this election yet.
        setNeedsSignIn(apiErr.error === 'UNAUTHENTICATED')
      }
      setError(apiErr)
    } finally {
      setLoading(false)
    }
  }, [electionId])

  useEffect(() => {
    loadElection()
  }, [loadElection, session, signedIn])

  const shell = (children: React.ReactNode) => (
    <div className="mx-auto flex min-h-[calc(100vh-140px)] max-w-md flex-col justify-center px-4 py-10">
      <Link
        to="/voter"
        className="mb-4 inline-flex items-center gap-2 font-mono text-xs text-ash transition hover:text-paper"
      >
        <ArrowLeft className="h-4 w-4" />
        VOTER HUB
      </Link>
      <div className="rounded-3xl border border-white/10 bg-charcoal/70 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
        {children}
      </div>
    </div>
  )

  if (loading && !election) return <LoadingSpinner label="Finding election..." />

  if (needsSignIn || !signedIn) {
    return shell(
      <div className="space-y-5">
        <div>
          <p className="font-mono text-[10px] tracking-wider text-electric">ELECTION</p>
          <h1 className="mt-1 font-display text-xl font-bold text-paper">
            {election?.title ?? 'Sign in required'}
          </h1>
          <p className="mt-1 text-xs text-ash">Sign in with your account to view this election and vote.</p>
        </div>
        <VoterSignIn
          onSignedIn={() => {
            setNeedsSignIn(false)
            setSession((n) => n + 1)
          }}
        />
      </div>
    )
  }

  if (!election) {
    const notOpenYet = error?.error === 'FORBIDDEN'
    return shell(
      <div className="space-y-4 text-center">
        <ErrorMessage error={notOpenYet ? { error: 'NOT_OPEN', message: 'Voting has not opened for this election yet.' } : error || 'Election not found.'} />
        <Link to="/voter">
          <Button variant="secondary">Try another election</Button>
        </Link>
      </div>
    )
  }

  if (election.status === 'draft' || election.status === 'closed' || election.status === 'closing') {
    const isClosing = election.status === 'closing'
    return shell(
      <div className="space-y-4 text-center">
        <Lock className="mx-auto h-9 w-9 text-ash" />
        <h1 className="font-display text-xl font-bold text-paper">{election.title}</h1>
        {election.status === 'draft' ? (
          <p className="text-sm text-ash">Voting has not opened yet. Please check back later.</p>
        ) : isClosing ? (
          <p className="text-sm text-ash">
            Voting has ended — ballots are being published to the chain and results are being finalized.
          </p>
        ) : (
          <>
            <p className="text-sm text-ash">Voting has ended for this election.</p>
            <Link to={`/results/${election.election_id}`}>
              <Button>View results</Button>
            </Link>
          </>
        )}
      </div>
    )
  }

  // Open: either show the remembered receipt, or the ballot.
  return shell(
    <>
      <div className="mb-6">
        <p className="font-mono text-[10px] tracking-wider text-electric">ELECTION · OPEN</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-paper">{election.title}</h1>
        {election.closes_at && (
          <p className="mt-1 text-xs text-ash">Ballots accepted until {new Date(election.closes_at).toLocaleString()}</p>
        )}
      </div>

      {rememberedReceipt ? (
        <div className="space-y-4 text-center">
          <Check className="mx-auto h-10 w-10 text-emerald-400" />
          <h2 className="font-display text-xl font-bold text-paper">You have already voted</h2>
          <p className="text-sm text-ash">Only one ballot per voter is allowed.</p>
          <Button onClick={() => window.location.assign(`/receipt/${electionId}/${rememberedReceipt}`)}>
            <Receipt className="h-4 w-4" />
            View my receipt
          </Button>
        </div>
      ) : (
        <BallotStep
          electionId={electionId}
          candidates={election.candidates}
          onAlreadyVoted={(receiptId) => window.location.assign(`/receipt/${electionId}/${receiptId}`)}
        />
      )}
    </>
  )
}
