import { useState } from 'react'
import { CheckCircle2, Vote } from 'lucide-react'
import { api, rememberReceipt } from '../../services/api'
import type { ApiError, Candidate } from '../../types'
import { Button } from '../ui/Button'
import { ConfirmationModal } from '../ui/ConfirmationModal'
import { ErrorMessage } from '../ui/ErrorMessage'

interface BallotStepProps {
  electionId: string
  candidates: Candidate[]
  /** Called when the backend reports this voter already has a ballot on file. */
  onAlreadyVoted: (receiptId: string) => void
}

/**
 * One eligible voter, one ballot. Submitting the same choice again returns the
 * original receipt (idempotent retry); a different choice is rejected with
 * DUPLICATE_VOTE and the original stands.
 */
export default function BallotStep({ electionId, candidates, onAlreadyVoted }: BallotStepProps) {
  const [selected, setSelected] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [retryInfo, setRetryInfo] = useState<string | null>(null)

  const chosen = candidates.find((c) => c.candidate_id === selected)

  const submit = async () => {
    if (!selected) return
    setSubmitting(true)
    setError(null)
    try {
      const receipt = await api.submitBallot(electionId, selected)
      rememberReceipt(electionId, receipt.receipt_id)
      if (receipt.idempotent_retry) {
        onAlreadyVoted(receipt.receipt_id)
        return
      }
      window.location.assign(`/receipt/${electionId}/${receipt.receipt_id}`)
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr)
      if (apiErr.error === 'DUPLICATE_VOTE') {
        // The original ballot stands; without a stored receipt id we cannot link
        // to it, but the organizer's publication monitor shows it on chain.
        setRetryInfo(
          'A ballot from this account was already recorded — the original choice stands. Ask the organizer to check the publication monitor for your receipt id.'
        )
        setConfirming(false)
        return
      }
      setConfirming(false)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-xl font-bold text-paper">Cast your ballot</h2>
        <p className="mt-1 text-xs text-ash">Select one candidate. You can review before submitting.</p>
      </div>

      {error && <ErrorMessage error={error} />}
      {retryInfo && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-500/40 bg-amber-950/20 p-4 text-xs text-amber-200">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-amber-400" />
          {retryInfo}
        </div>
      )}

      <div className="space-y-3" role="radiogroup" aria-label="Candidates">
        {candidates.map((c) => {
          const active = selected === c.candidate_id
          return (
            <label
              key={c.candidate_id}
              className={`flex cursor-pointer items-start gap-4 rounded-2xl border p-4 transition ${
                active
                  ? 'border-saffron bg-saffron/10 ring-1 ring-saffron'
                  : 'border-white/10 bg-charcoal/40 hover:border-white/25'
              }`}
            >
              <input
                type="radio"
                name="candidate"
                value={c.candidate_id}
                checked={active}
                onChange={() => setSelected(c.candidate_id)}
                className="mt-1 h-5 w-5 accent-[#ff9933]"
              />
              <span>
                <span className="block font-display text-base font-bold text-paper">{c.name}</span>
                <span className="mt-0.5 block font-mono text-[10px] text-ash/70">
                  chain index {c.chain_index}
                </span>
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
