import { useState } from 'react'
import { KeyRound, UserPlus } from 'lucide-react'
import { api } from '../services/api'
import { useAuth } from '../context/AuthContext'
import type { ApiError, EligibleVotersOut } from '../types'
import { Button } from './ui/Button'
import { ErrorMessage } from './ui/ErrorMessage'

interface EligibleVotersProps {
  electionId: string
  voters: EligibleVotersOut['eligible_test_voters']
  onChanged: () => void
  disabled?: boolean
}

const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/

/**
 * Milestone-1 roster: eligibility is a list of Supabase user IDs. Voters sign in
 * with their own account to vote — no names, emails, or CSV import exists in the
 * backend yet.
 */
export default function EligibleVoters({ electionId, voters, onChanged, disabled }: EligibleVotersProps) {
  const { user } = useAuth()
  const [input, setInput] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const add = async () => {
    const ids = input
      .split(/[\s,;]+/)
      .map((s) => s.trim())
      .filter(Boolean)

    const invalid = ids.filter((id) => !UUID_RE.test(id))
    if (ids.length === 0) return
    if (invalid.length > 0) {
      setError({
        error: 'VALIDATION_ERROR',
        message: `Not valid user IDs: ${invalid.slice(0, 2).join(', ')}${invalid.length > 2 ? '…' : ''}`,
      })
      return
    }

    setAdding(true)
    setError(null)
    setNotice(null)
    try {
      const out = await api.addEligibleVoters(electionId, ids)
      const added = out.added ?? ids.length
      const skipped = out.skipped ?? 0
      setInput('')
      setNotice(
        added > 0
          ? `Added ${added} voter${added === 1 ? '' : 's'}${skipped ? `, skipped ${skipped} duplicate(s)` : ''}.`
          : 'No new voters added (all were already eligible).'
      )
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="space-y-4 self-start rounded-3xl border border-white/10 bg-charcoal/40 p-6">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <h2 className="font-display text-lg font-bold text-paper">Eligible voters</h2>
        <span className="font-mono text-xs text-ash">{voters.length} eligible</span>
      </div>

      {!disabled && (
        <>
          {user && (
            <button
              type="button"
              onClick={() => setInput((prev) => (prev ? `${prev.trim()}\n${user.user_id}` : user.user_id))}
              className="flex w-full items-center gap-2 rounded-2xl border border-white/10 bg-obsidian/60 p-3 text-left font-mono text-[11px] text-ash transition hover:border-saffron/40"
              title="Copy your own user ID into the box to let yourself vote in this election"
            >
              <KeyRound className="h-3.5 w-3.5 shrink-0 text-saffron" />
              <span className="truncate">
                Add yourself: <span className="text-paper">{user.user_id}</span>
              </span>
            </button>
          )}

          <div>
            <label
              htmlFor="voter-ids"
              className="block font-mono text-[11px] font-medium tracking-wide text-ash"
            >
              VOTER USER IDS (ONE PER LINE)
            </label>
            <textarea
              id="voter-ids"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              rows={4}
              spellCheck={false}
              placeholder="00000000-0000-0000-0000-000000000000"
              className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 font-mono text-xs text-paper focus:border-saffron focus:outline-none"
            />
          </div>

          <Button size="sm" onClick={add} isLoading={adding} loadingText="Adding..." disabled={!input.trim()}>
            <UserPlus className="h-3.5 w-3.5" />
            Add voters
          </Button>

          {notice && (
            <p className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3 font-mono text-[11px] text-emerald-300">
              {notice}
            </p>
          )}
          {error && <ErrorMessage error={error} />}
          <p className="font-mono text-[10px] leading-relaxed text-ash/70">
            Voters sign in with their own VoteVault account (same sign-up as organizers) and open the election link
            to vote.
          </p>
        </>
      )}

      {voters.length > 0 ? (
        <ul className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
          {voters.map((v) => (
            <li
              key={v.user_id}
              className="truncate rounded-lg border border-white/10 bg-obsidian/70 px-3 py-1.5 font-mono text-[11px] text-paper/80"
              title={v.user_id}
            >
              {v.user_id}
            </li>
          ))}
        </ul>
      ) : (
        !disabled && <p className="font-mono text-[11px] text-amber-300">Add at least one voter before opening.</p>
      )}
    </div>
  )
}
