import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Vote } from 'lucide-react'
import { api } from '../../services/api'
import type { ApiError, VoterSessionInfo } from '../../types'
import { Button } from '../ui/Button'
import { ConfirmationModal } from '../ui/ConfirmationModal'
import { ErrorMessage } from '../ui/ErrorMessage'

export default function BallotStep({ session }: { session: VoterSessionInfo }) {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const chosen = session.candidates.find((c) => c.id === selected)

  const submit = async () => {
    if (!selected) return
    setSubmitting(true)
    setError(null)
    try {
      const receipt = await api.submitBallot(selected)
      api.endVoterSession()
      navigate(`/receipt/${receipt.receiptId}`, { replace: true })
    } catch (err) {
      setError(err as ApiError)
      setConfirming(false)
    } finally {
      setSubmitting(false)
    }
  }

  if (session.hasVoted) {
    return (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-amber-400" />
        <h2 className="font-display text-xl font-bold text-paper">You have already voted</h2>
        <p className="text-sm text-ash">Only one ballot per voter is allowed.</p>
        {session.receiptId && (
          <Button onClick={() => navigate(`/receipt/${session.receiptId}`)} variant="secondary">
            View my receipt
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-xl font-bold text-paper">Cast your ballot</h2>
        <p className="mt-1 text-xs text-ash">
          Welcome, {session.voterName}. Select one candidate. You can review before submitting.
        </p>
      </div>

      {error && <ErrorMessage error={error} />}

      <div className="space-y-3" role="radiogroup" aria-label="Candidates">
        {session.candidates.map((c) => {
          const active = selected === c.id
          return (
            <label
              key={c.id}
              className={`flex cursor-pointer items-start gap-4 rounded-2xl border p-4 transition ${
                active
                  ? 'border-saffron bg-saffron/10 ring-1 ring-saffron'
                  : 'border-white/10 bg-charcoal/40 hover:border-white/25'
              }`}
            >
              <input
                type="radio"
                name="candidate"
                value={c.id}
                checked={active}
                onChange={() => setSelected(c.id)}
                className="mt-1 h-5 w-5 accent-[#ff9933]"
              />
              <span>
                <span className="block font-display text-base font-bold text-paper">{c.name}</span>
                {c.description && <span className="mt-0.5 block text-xs leading-relaxed text-ash">{c.description}</span>}
              </span>
            </label>
          )
        })}
      </div>

      <Button size="lg" className="w-full" disabled={!selected} onClick={() => setConfirming(true)}>
        <Vote className="h-4 w-4" />
        Review & cast ballot
      </Button>

      <ConfirmationModal
        isOpen={confirming}
        title="Confirm your vote"
        description={`You are voting for ${chosen?.name ?? ''}. Once submitted your ballot cannot be changed.`}
        confirmText="Cast ballot"
        isLoading={submitting}
        onConfirm={submit}
        onCancel={() => setConfirming(false)}
      />
    </div>
  )
}
