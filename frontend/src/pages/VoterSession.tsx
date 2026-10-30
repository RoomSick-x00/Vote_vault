import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Check, Lock } from 'lucide-react'
import { api, getVoterToken } from '../services/api'
import type { ApiError, IdentifyResponse, OtpChannel, PublicElection, VoterSessionInfo } from '../types'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { extractElectionCode } from '../lib/code'
import IdentifyStep from '../components/voter/IdentifyStep'
import ContactStep from '../components/voter/ContactStep'
import OtpStep from '../components/voter/OtpStep'
import BallotStep from '../components/voter/BallotStep'

type Step = 'identify' | 'contact' | 'otp' | 'ballot'
const STEPS: Array<{ key: Step; label: string }> = [
  { key: 'identify', label: 'Identify' },
  { key: 'contact', label: 'Contact' },
  { key: 'otp', label: 'OTP' },
  { key: 'ballot', label: 'Vote' },
]

export default function VoterSession() {
  const params = useParams<{ code: string }>()
  const code = extractElectionCode(params.code || '')

  const [election, setElection] = useState<PublicElection | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const [step, setStep] = useState<Step>('identify')
  const [identity, setIdentity] = useState<IdentifyResponse | null>(null)
  const [otp, setOtp] = useState<{ channel: OtpChannel; contact: string; resendAfter: number } | null>(null)
  const [session, setSession] = useState<VoterSessionInfo | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setStep('identify')
    setIdentity(null)
    setOtp(null)
    setSession(null)

    ;(async () => {
      try {
        const e = await api.getPublicElection(code)
        if (!active) return
        setElection(e)

        // Resume an already verified session for this election (e.g. page refresh).
        if (e.status === 'open' && getVoterToken()) {
          try {
            const s = await api.getVoterSession()
            if (active && s.election.code === e.code) {
              setSession(s)
              setStep('ballot')
            } else {
              api.endVoterSession()
            }
          } catch {
            api.endVoterSession()
          }
        }
      } catch (err) {
        if (active) setError(err as ApiError)
      } finally {
        if (active) setLoading(false)
      }
    })()

    return () => {
      active = false
    }
  }, [code])

  const stepIndex = STEPS.findIndex((s) => s.key === step)

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

  if (loading) return <LoadingSpinner label="Finding election..." />

  if (!election) {
    return shell(
      <div className="space-y-4 text-center">
        <ErrorMessage
          error={
            error?.error === 'NETWORK_FAILURE'
              ? error
              : { error: 'NOT_FOUND', message: error?.message || 'No election found for that code.' }
          }
        />
        <Link to="/voter">
          <Button variant="secondary">Try another code</Button>
        </Link>
      </div>
    )
  }

  if (election.status !== 'open') {
    return shell(
      <div className="space-y-4 text-center">
        <Lock className="mx-auto h-9 w-9 text-ash" />
        <h1 className="font-display text-xl font-bold text-paper">{election.title}</h1>
        {election.status === 'draft' ? (
          <p className="text-sm text-ash">Voting has not opened yet. Please check back later.</p>
        ) : (
          <>
            <p className="text-sm text-ash">Voting has ended for this election.</p>
            <Link to={`/results/${election.id}`}>
              <Button>View results</Button>
            </Link>
          </>
        )}
      </div>
    )
  }

  return shell(
    <>
      <div className="mb-6">
        <p className="font-mono text-[10px] tracking-wider text-electric">ELECTION · {election.code}</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-paper">{election.title}</h1>
        {election.description && <p className="mt-1 text-xs text-ash">{election.description}</p>}
      </div>

      <ol className="mb-6 flex items-center gap-2" aria-label="Progress">
        {STEPS.map((s, i) => (
          <li key={s.key} className="flex flex-1 flex-col items-center gap-1.5">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full font-mono text-xs font-bold ${
                i < stepIndex
                  ? 'bg-emerald-500 text-obsidian'
                  : i === stepIndex
                  ? 'bg-electric text-obsidian'
                  : 'bg-white/10 text-ash'
              }`}
            >
              {i < stepIndex ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            <span className={`font-mono text-[10px] ${i === stepIndex ? 'text-paper' : 'text-ash'}`}>{s.label}</span>
          </li>
        ))}
      </ol>

      {step === 'identify' && (
        <IdentifyStep
          election={election}
          onDone={(res) => {
            setIdentity(res)
            setStep('contact')
          }}
        />
      )}

      {step === 'contact' && identity && (
        <ContactStep
          identifyToken={identity.identifyToken}
          channels={identity.channels}
          onDone={(info) => {
            setOtp({ channel: info.channel, contact: info.contact, resendAfter: info.resendAfter })
            setStep('otp')
          }}
        />
      )}

      {step === 'otp' && identity && otp && (
        <OtpStep
          identifyToken={identity.identifyToken}
          channel={otp.channel}
          contact={otp.contact}
          resendAfter={otp.resendAfter}
          onChangeContact={() => setStep('contact')}
          onVerified={(v) => {
            setSession(v.session)
            setStep('ballot')
          }}
        />
      )}

      {step === 'ballot' && session && <BallotStep session={session} />}
    </>
  )
}
