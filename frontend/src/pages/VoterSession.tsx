import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Lock } from 'lucide-react'
import { api, getVoterToken } from '../services/api'
import type { ApiError, IdentifyResponse, OtpRequestResponse, PublicElection, VoterSession as VoterSessionInfo } from '../types'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import BallotStep from '../components/voter/BallotStep'

export default function VoterSession() {
  const { electionId: rawCode = '' } = useParams<{ electionId: string }>()
  const code = rawCode.toUpperCase()
  const navigate = useNavigate()
  const [election, setElection] = useState<PublicElection | null>(null)
  const [session, setSession] = useState<VoterSessionInfo | null>(null)
  const [identity, setIdentity] = useState({ name: '', rollNo: '' })
  const [identify, setIdentify] = useState<IdentifyResponse | null>(null)
  const [channel, setChannel] = useState<'email' | 'phone'>('email')
  const [contact, setContact] = useState('')
  const [otpRequest, setOtpRequest] = useState<OtpRequestResponse | null>(null)
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const loadElection = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const current = await api.getPublicElection(code)
      setElection(current)
      if (getVoterToken()) {
        try {
          const voterSession = await api.getVoterSession()
          if (voterSession.election.code === current.code) setSession(voterSession)
          else api.endVoterSession()
        } catch {
          api.endVoterSession()
        }
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }, [code])

  useEffect(() => {
    void loadElection()
  }, [loadElection])

  const identifyVoter = async (event: React.FormEvent) => {
    event.preventDefault()
    setActing(true)
    setError(null)
    try {
      const result = await api.identifyVoter(code, {
        ...(identity.name.trim() ? { name: identity.name.trim() } : {}),
        ...(identity.rollNo.trim() ? { rollNo: identity.rollNo.trim() } : {}),
      })
      setIdentify(result)
      setChannel(result.channels[0] ?? 'email')
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setActing(false)
    }
  }

  const requestOtp = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!identify) return
    setActing(true)
    setError(null)
    try {
      setOtpRequest(await api.requestVoterOtp(identify.identifyToken, channel, contact.trim()))
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setActing(false)
    }
  }

  const verifyOtp = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!identify) return
    setActing(true)
    setError(null)
    try {
      setSession(await api.verifyVoterOtp(identify.identifyToken, otp.trim()))
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setActing(false)
    }
  }

  if (loading) return <LoadingSpinner label="Loading election..." />

  const shell = (children: React.ReactNode) => (
    <div className="mx-auto flex min-h-[calc(100vh-140px)] max-w-lg flex-col justify-center px-4 py-10">
      <Link to="/voter" className="mb-4 inline-flex items-center gap-2 font-mono text-xs text-ash hover:text-paper">
        <ArrowLeft className="h-4 w-4" />
        VOTER HUB
      </Link>
      <div className="rounded-3xl border border-white/10 bg-charcoal/70 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
        {children}
      </div>
    </div>
  )

  if (!election) {
    return shell(<ErrorMessage error={error || 'Election not found.'} />)
  }

  if (election.status !== 'open') {
    return shell(
      <div className="space-y-4 text-center">
        <Lock className="mx-auto h-9 w-9 text-ash" />
        <h1 className="font-display text-xl font-bold text-paper">{election.title}</h1>
        <p className="text-sm text-ash">
          {election.status === 'draft' ? 'Voting has not opened yet.' : 'Voting has ended for this election.'}
        </p>
        {election.status === 'closed' && (
          <Link to={`/results/${election.id}`}>
            <Button>View results</Button>
          </Link>
        )}
      </div>
    )
  }

  if (session?.hasVoted && session.receiptId) {
    return shell(
      <div className="space-y-4 text-center">
        <h1 className="font-display text-xl font-bold text-paper">Your ballot was received</h1>
        <p className="font-mono text-xs text-ash">Election {election.code}</p>
        <Button onClick={() => navigate(`/receipt/${session.election.id}/${session.receiptId}`)}>
          View ballot receipt
        </Button>
      </div>
    )
  }

  if (session) {
    return shell(
      <>
        <div className="mb-6">
          <p className="font-mono text-[10px] tracking-wider text-electric">ELECTION · {election.code}</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-paper">{election.title}</h1>
          <p className="mt-2 text-sm text-ash">Welcome, {session.voterName}. Your ballot choice stays private from the public chain.</p>
        </div>
        {error && <ErrorMessage error={error} className="mb-4" />}
        <BallotStep
          electionId={session.election.id}
          candidates={session.candidates}
          onAlreadyVoted={(receiptId) => navigate(`/receipt/${session.election.id}/${receiptId}`)}
        />
      </>
    )
  }

  return shell(
    <div className="space-y-5">
      <div>
        <p className="font-mono text-[10px] tracking-wider text-electric">ELECTION · {election.code}</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-paper">{election.title}</h1>
        {election.description && <p className="mt-2 text-sm text-ash">{election.description}</p>}
      </div>

      {error && <ErrorMessage error={error} />}

      {!identify ? (
        <form onSubmit={identifyVoter} className="space-y-4">
          <p className="text-sm text-ash">Enter the roster details requested by the organizer.</p>
          {election.voterSchema.identityColumns.map((field) => (
            <label key={field} className="block space-y-1">
              <span className="font-mono text-[11px] text-ash">{field === 'rollNo' ? 'ROLL NUMBER' : 'NAME'}</span>
              <input
                autoComplete={field === 'name' ? 'name' : 'off'}
                required
                value={identity[field]}
                onChange={(event) => setIdentity((current) => ({ ...current, [field]: event.target.value }))}
                className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 text-sm text-paper focus:border-electric focus:outline-none"
              />
            </label>
          ))}
          <Button type="submit" className="w-full" isLoading={acting} loadingText="Checking...">
            Continue
          </Button>
        </form>
      ) : !otpRequest ? (
        <form onSubmit={requestOtp} className="space-y-4">
          <p className="text-sm text-ash">Choose the roster contact channel and enter its registered address/number.</p>
          <label className="block space-y-1">
            <span className="font-mono text-[11px] text-ash">VERIFICATION CHANNEL</span>
            <select
              value={channel}
              onChange={(event) => setChannel(event.target.value as 'email' | 'phone')}
              className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 text-sm text-paper"
            >
              {identify.channels.map((option) => (
                <option key={option} value={option}>{option === 'email' ? 'Email' : 'Phone'}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="font-mono text-[11px] text-ash">{channel === 'email' ? 'REGISTERED EMAIL' : 'REGISTERED PHONE'}</span>
            <input
              required
              type={channel === 'email' ? 'email' : 'tel'}
              value={contact}
              onChange={(event) => setContact(event.target.value)}
              className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 text-sm text-paper focus:border-electric focus:outline-none"
            />
          </label>
          <Button type="submit" className="w-full" isLoading={acting} loadingText="Sending...">
            Send one-time code
          </Button>
        </form>
      ) : (
        <form onSubmit={verifyOtp} className="space-y-4">
          <p className="text-sm text-ash">
            Enter the one-time code sent to your registered {channel}. It expires in {Math.ceil(otpRequest.expiresIn / 60)} minutes.
          </p>
          {otpRequest.devCode && (
            <p className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-3 font-mono text-xs text-amber-200">
              Local development code: <strong>{otpRequest.devCode}</strong>
            </p>
          )}
          <label className="block space-y-1">
            <span className="font-mono text-[11px] text-ash">ONE-TIME CODE</span>
            <input
              required
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              value={otp}
              onChange={(event) => setOtp(event.target.value.replace(/\D/g, ''))}
              className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 text-center font-mono text-lg tracking-[0.4em] text-paper focus:border-electric focus:outline-none"
            />
          </label>
          <Button type="submit" className="w-full" isLoading={acting} loadingText="Verifying...">
            Verify and continue
          </Button>
          <button type="button" className="w-full font-mono text-xs text-ash hover:text-paper" onClick={() => setOtpRequest(null)}>
            Use a different contact channel
          </button>
        </form>
      )}
    </div>
  )
}
