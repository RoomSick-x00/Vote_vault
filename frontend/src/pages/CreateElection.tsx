import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { api, electionIndex } from '../services/api'
import { useAuth } from '../context/AuthContext'
import type { ApiError } from '../types'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { Field } from '../components/ui/Field'

const MIN_CANDIDATES = 2
const MAX_CANDIDATES = 20

/**
 * Backend flow: POST /elections creates a draft (organization + title, optional
 * schedule). Candidates are added separately while still a draft, so this form
 * creates the election and then adds the entered candidate names in one go.
 */
export default function CreateElection() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const organizations = user?.organizations ?? []

  const [organizationId, setOrganizationId] = useState(organizations[0]?.organization_id ?? '')
  const [title, setTitle] = useState('')
  const [opensAt, setOpensAt] = useState('')
  const [closesAt, setClosesAt] = useState('')
  const [candidates, setCandidates] = useState([{ name: '' }, { name: '' }])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const updateCandidate = (i: number, value: string) =>
    setCandidates((prev) => prev.map((c, idx) => (idx === i ? { name: value } : c)))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!organizationId) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Select the organisation that owns this election.' })
    }
    if (title.trim().length < 3) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Election title must be at least 3 characters.' })
    }
    const names = candidates.map((c) => c.name.trim()).filter(Boolean)
    if (names.length < MIN_CANDIDATES) {
      return setError({
        error: 'VALIDATION_ERROR',
        message: `At least ${MIN_CANDIDATES} candidate names are required.`,
      })
    }
    if (opensAt && closesAt && new Date(opensAt) >= new Date(closesAt)) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Closing time must be after the opening time.' })
    }

    setLoading(true)
    try {
      const election = await api.createElection({
        organization_id: organizationId,
        title: title.trim(),
        opens_at: opensAt ? new Date(opensAt).toISOString() : null,
        closes_at: closesAt ? new Date(closesAt).toISOString() : null,
      })
      electionIndex.remember(election.election_id)
      await api.addCandidates(
        election.election_id,
        names.map((name) => ({ name }))
      )
      navigate(`/organizer/elections/${election.election_id}`, { replace: true })
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        to="/organizer"
        className="inline-flex items-center gap-2 font-mono text-xs text-ash transition hover:text-paper"
      >
        <ArrowLeft className="h-4 w-4" />
        BACK TO DASHBOARD
      </Link>

      <div className="mt-6 border-b border-white/10 pb-6">
        <h1 className="font-display text-3xl font-bold text-paper">Create election</h1>
        <p className="mt-1 text-sm text-ash">
          A draft is created first; candidates are frozen when voting opens, and eligible voters are added on the
          next screen.
        </p>
      </div>

      {error && <ErrorMessage error={error} className="mt-6" />}

      <form onSubmit={handleSubmit} className="mt-8 space-y-8">
        <section className="space-y-4 rounded-3xl border border-white/10 bg-charcoal/50 p-6">
          <h2 className="font-display text-lg font-bold text-paper">1. Election details</h2>

          {organizations.length <= 1 ? (
            organizations.length === 1 && (
              <p className="rounded-2xl border border-white/10 bg-obsidian/60 p-3 font-mono text-xs text-ash">
                Organisation: <span className="text-paper">{organizations[0].name}</span>
              </p>
            )
          ) : (
            <div>
              <label
                htmlFor="elec-org"
                className="block font-mono text-[11px] font-medium tracking-wide text-ash"
              >
                ORGANISATION
              </label>
              <select
                id="elec-org"
                value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value)}
                className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper focus:border-saffron focus:outline-none"
              >
                {organizations.map((o) => (
                  <option key={o.organization_id} value={o.organization_id}>
                    {o.name} ({o.role})
                  </option>
                ))}
              </select>
            </div>
          )}

          <Field
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Student Council Election 2026"
            required
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="elec-opens"
                className="block font-mono text-[11px] font-medium tracking-wide text-ash"
              >
                OPENS AT (OPTIONAL)
              </label>
              <input
                id="elec-opens"
                type="datetime-local"
                value={opensAt}
                onChange={(e) => setOpensAt(e.target.value)}
                className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper focus:border-saffron focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="elec-closes"
                className="block font-mono text-[11px] font-medium tracking-wide text-ash"
              >
                CLOSES AT (OPTIONAL)
              </label>
              <input
                id="elec-closes"
                type="datetime-local"
                value={closesAt}
                onChange={(e) => setClosesAt(e.target.value)}
                className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper focus:border-saffron focus:outline-none"
              />
            </div>
          </div>
          <p className="font-mono text-[10px] text-ash/70">
            If set, ballots are only accepted inside this window while the election is open.
          </p>
        </section>

        <section className="space-y-4 rounded-3xl border border-white/10 bg-charcoal/50 p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-bold text-paper">2. Candidates</h2>
            <span className="font-mono text-xs text-ash">
              {candidates.filter((c) => c.name.trim()).length} named / {MAX_CANDIDATES}
            </span>
          </div>

          {candidates.map((c, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-2xl border border-white/10 bg-obsidian/70 p-4"
            >
              <span className="w-24 shrink-0 font-mono text-xs font-bold text-saffron">
                CANDIDATE {i + 1}
              </span>
              <input
                value={c.name}
                onChange={(e) => updateCandidate(i, e.target.value)}
                placeholder="Name"
                aria-label={`Candidate ${i + 1} name`}
                className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper focus:border-saffron focus:outline-none"
              />
              {candidates.length > MIN_CANDIDATES && (
                <button
                  type="button"
                  onClick={() => setCandidates((prev) => prev.filter((_, idx) => idx !== i))}
                  className="shrink-0 text-ash transition hover:text-red-400"
                  aria-label={`Remove candidate ${i + 1}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}

          {candidates.length < MAX_CANDIDATES && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setCandidates((prev) => [...prev, { name: '' }])}
            >
              <Plus className="h-3.5 w-3.5" />
              Add candidate
            </Button>
          )}
          <p className="font-mono text-[10px] text-ash/70">
            Duplicate names are skipped; the insertion order becomes the immutable on-chain index.
          </p>
        </section>

        <div className="flex items-center justify-end gap-3">
          <Link to="/organizer">
            <Button type="button" variant="ghost">
              Cancel
            </Button>
          </Link>
          <Button type="submit" size="lg" isLoading={loading} loadingText="Creating...">
            Create election
          </Button>
        </div>
      </form>
    </div>
  )
}
