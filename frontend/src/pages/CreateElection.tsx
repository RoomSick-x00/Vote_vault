import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, OtpChannel, VoterSchema } from '../types'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { Field } from '../components/ui/Field'
import { columnLabels, mandatoryColumns } from '../lib/voterColumns'

const MIN_CANDIDATES = 2
const MAX_CANDIDATES = 20

export default function CreateElection() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [candidates, setCandidates] = useState([
    { name: '', description: '' },
    { name: '', description: '' },
  ])
  const [identity, setIdentity] = useState<VoterSchema['identityColumns']>(['name', 'rollNo'])
  const [channels, setChannels] = useState<OtpChannel[]>(['email'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const updateCandidate = (i: number, field: 'name' | 'description', value: string) =>
    setCandidates((prev) => prev.map((c, idx) => (idx === i ? { ...c, [field]: value } : c)))

  const toggle = <T,>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

  const schema: VoterSchema = { identityColumns: identity, otpChannels: channels }
  const required = mandatoryColumns(schema)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (title.trim().length < 3) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Election title must be at least 3 characters.' })
    }
    if (candidates.some((c) => !c.name.trim())) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Every candidate needs a name.' })
    }
    if (identity.length === 0) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Pick at least one column used to identify voters.' })
    }
    if (channels.length === 0) {
      return setError({ error: 'VALIDATION_ERROR', message: 'Pick at least one OTP channel (email or phone).' })
    }

    setLoading(true)
    try {
      const election = await api.createElection({
        title: title.trim(),
        description: description.trim(),
        candidates: candidates.map((c) => ({ name: c.name.trim(), description: c.description.trim() })),
        voterSchema: schema,
      })
      navigate(`/organizer/elections/${election.id}`, { replace: true })
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  const checkbox = (checked: boolean, onChange: () => void, label: string, hint: string) => (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition ${
        checked ? 'border-saffron bg-saffron/10' : 'border-white/10 bg-obsidian/60 hover:border-white/25'
      }`}
    >
      <input type="checkbox" checked={checked} onChange={onChange} className="mt-1 h-4 w-4 accent-[#ff9933]" />
      <span>
        <span className="block font-display text-sm font-bold text-paper">{label}</span>
        <span className="block text-xs text-ash">{hint}</span>
      </span>
    </label>
  )

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
          After creating it you will get a join code and QR, and can add your voter list.
        </p>
      </div>

      {error && <ErrorMessage error={error} className="mt-6" />}

      <form onSubmit={handleSubmit} className="mt-8 space-y-8">
        <section className="space-y-4 rounded-3xl border border-white/10 bg-charcoal/50 p-6">
          <h2 className="font-display text-lg font-bold text-paper">1. Election details</h2>
          <Field
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Student Council Election 2026"
            required
          />
          <div>
            <label htmlFor="elec-desc" className="block font-mono text-[11px] font-medium tracking-wide text-ash">
              DESCRIPTION
            </label>
            <textarea
              id="elec-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper focus:border-saffron focus:outline-none"
            />
          </div>
        </section>

        <section className="space-y-4 rounded-3xl border border-white/10 bg-charcoal/50 p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-bold text-paper">2. Candidates</h2>
            <span className="font-mono text-xs text-ash">
              {candidates.length} / {MAX_CANDIDATES}
            </span>
          </div>

          {candidates.map((c, i) => (
            <div key={i} className="space-y-3 rounded-2xl border border-white/10 bg-obsidian/70 p-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-saffron">CANDIDATE {i + 1}</span>
                {candidates.length > MIN_CANDIDATES && (
                  <button
                    type="button"
                    onClick={() => setCandidates((prev) => prev.filter((_, idx) => idx !== i))}
                    className="text-ash transition hover:text-red-400"
                    aria-label={`Remove candidate ${i + 1}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
              <Field
                label="Name"
                value={c.name}
                onChange={(e) => updateCandidate(i, 'name', e.target.value)}
                required
              />
              <Field
                label="Short description"
                value={c.description}
                onChange={(e) => updateCandidate(i, 'description', e.target.value)}
                placeholder="Optional"
              />
            </div>
          ))}

          {candidates.length < MAX_CANDIDATES && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setCandidates((prev) => [...prev, { name: '', description: '' }])}
            >
              <Plus className="h-3.5 w-3.5" />
              Add candidate
            </Button>
          )}
        </section>

        <section className="space-y-5 rounded-3xl border border-white/10 bg-charcoal/50 p-6">
          <div>
            <h2 className="font-display text-lg font-bold text-paper">3. Voter verification</h2>
            <p className="mt-1 text-xs text-ash">
              Choose the mandatory columns. Voters are matched on these, so only they are checked against your
              database.
            </p>
          </div>

          <div>
            <p className="mb-2 font-mono text-[11px] tracking-wide text-ash">IDENTIFY VOTERS BY</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {checkbox(
                identity.includes('name'),
                () => setIdentity((p) => toggle(p, 'name')),
                'Name',
                'Voter types their full name'
              )}
              {checkbox(
                identity.includes('rollNo'),
                () => setIdentity((p) => toggle(p, 'rollNo')),
                'Roll number',
                'Voter types their roll / ID number'
              )}
            </div>
          </div>

          <div>
            <p className="mb-2 font-mono text-[11px] tracking-wide text-ash">SEND OTP TO</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {checkbox(
                channels.includes('email'),
                () => setChannels((p) => toggle(p, 'email')),
                'College email',
                'OTP sent to the email in your list'
              )}
              {checkbox(
                channels.includes('phone'),
                () => setChannels((p) => toggle(p, 'phone')),
                'Phone number',
                'OTP sent by SMS to the phone in your list'
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-obsidian/60 p-4">
            <p className="font-mono text-[11px] tracking-wide text-ash">MANDATORY COLUMNS IN YOUR VOTER LIST</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {required.length === 0 ? (
                <span className="text-xs text-ash">None selected</span>
              ) : (
                required.map((c) => (
                  <span key={c} className="rounded-full bg-saffron/10 px-3 py-1 font-mono text-xs text-saffron">
                    {columnLabels[c]}
                  </span>
                ))
              )}
            </div>
          </div>
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
