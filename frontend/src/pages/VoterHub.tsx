import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Vote } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { extractElectionCode, isElectionCode } from '../lib/code'

/**
 * Voters join with the short share code or the QR link from the organizer.
 */
export default function VoterHub() {
  const navigate = useNavigate()
  const [electionId, setElectionId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const join = () => {
    const clean = extractElectionCode(electionId)
    if (!isElectionCode(clean)) {
      setError('Enter the 8-character election code or scan the link the organizer shared.')
      return
    }
    navigate(`/vote/${clean}`)
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-140px)] max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-3xl border border-white/10 bg-charcoal/70 p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-electric/10 text-electric">
            <Vote className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-paper">Voter Hub</h1>
            <p className="text-xs text-ash">Open an election with its link or ID.</p>
          </div>
        </div>

        {error && <ErrorMessage error={error} className="mt-5" />}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            join()
          }}
          className="mt-6 space-y-4"
        >
          <div>
            <label htmlFor="election-id" className="block font-mono text-[11px] tracking-wide text-ash">
              ELECTION CODE OR LINK
            </label>
            <input
              id="election-id"
              value={electionId}
              onChange={(e) => setElectionId(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder="ABCD2345"
              className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 font-mono text-sm text-paper placeholder:text-ash/30 focus:border-electric focus:outline-none"
            />
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={!electionId.trim()}>
            Continue
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-ash">
          Only voters on the organizer's roster can verify and cast a ballot.
        </p>
      </div>
    </div>
  )
}
