import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, Election, VoterRecord, VoterSchema } from '../types'
import { Button } from './ui/Button'
import { ErrorMessage } from './ui/ErrorMessage'

interface VerificationSetupProps {
  election: Election
  voters: VoterRecord[]
  onChanged: () => void
}

type IdentityCol = 'name' | 'rollNo'
type ChannelCol = 'email' | 'phone'

const LABELS: Record<IdentityCol | ChannelCol, string> = {
  name: 'Name',
  rollNo: 'Roll no / Admin no',
  email: 'Email / Gmail',
  phone: 'Phone number',
}

const COLUMN_FIELD: Record<IdentityCol | ChannelCol, keyof VoterRecord> = {
  name: 'name',
  rollNo: 'rollNo',
  email: 'email',
  phone: 'phone',
}

/**
 * Step 2 of the workflow: choose which roster columns verify voters and which
 * contact column receives the one-time code — selected AFTER the database is
 * uploaded, from the columns it actually has. Draft-only; freezes at open.
 */
export default function VerificationSetup({ election, voters, onChanged }: VerificationSetupProps) {
  const schema = election.voter_schema
  const isSet = (schema?.identityColumns?.length ?? 0) > 0 && (schema?.otpChannels?.length ?? 0) > 0
  const isDraft = election.status === 'draft'

  const [identity, setIdentity] = useState<IdentityCol[]>(schema?.identityColumns ?? [])
  const [channels, setChannels] = useState<ChannelCol[]>(schema?.otpChannels ?? [])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  if (!isDraft && isSet) {
    return (
      <section className="space-y-3 self-start rounded-3xl border border-white/10 bg-charcoal/40 p-6">
        <h2 className="border-b border-white/10 pb-3 font-display text-lg font-bold text-paper">
          Voter verification
        </h2>
        <div className="space-y-2 font-mono text-[11px] text-ash">
          <p>
            IDENTIFY BY:{' '}
            <span className="text-paper">{schema!.identityColumns.map((c) => LABELS[c]).join(' + ')}</span>
          </p>
          <p>
            OTP CHANNELS:{' '}
            <span className="text-paper">{schema!.otpChannels.map((c) => LABELS[c]).join(' + ')}</span>
          </p>
          <p className="text-ash/70">Frozen when voting opened.</p>
        </div>
      </section>
    )
  }

  const coverage = (col: IdentityCol | ChannelCol) =>
    voters.filter((v) => !!v[COLUMN_FIELD[col]]).length

  const toggle = <T,>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.setVoterSchema(election.election_id, {
        identityColumns: identity,
        otpChannels: channels,
      } as VoterSchema)
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setSaving(false)
    }
  }

  const option = (col: IdentityCol | ChannelCol, kind: 'identity' | 'channel') => {
    const selected = kind === 'identity' ? identity.includes(col as IdentityCol) : channels.includes(col as ChannelCol)
    const have = coverage(col)
    const complete = voters.length === 0 || have === voters.length
    const onToggle = () =>
      kind === 'identity'
        ? setIdentity((prev) => toggle(prev, col as IdentityCol))
        : setChannels((prev) => toggle(prev, col as ChannelCol))
    return (
      <label
        key={col}
        className={`flex cursor-pointer items-center justify-between gap-3 rounded-2xl border p-3 transition ${
          selected ? 'border-saffron bg-saffron/10' : 'border-white/10 bg-obsidian/60 hover:border-white/25'
        } ${complete ? '' : 'cursor-not-allowed opacity-45'}`}
      >
        <span className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            disabled={!complete}
            className="h-4 w-4 accent-[#ff9933]"
          />
          <span className="font-display text-sm font-bold text-paper">{LABELS[col]}</span>
        </span>
        <span className={`font-mono text-[10px] ${complete ? 'text-ash' : 'text-amber-300'}`}>
          {voters.length === 0 ? 'no roster yet' : `${have}/${voters.length} have it`}
        </span>
      </label>
    )
  }

  return (
    <section className="space-y-4 self-start rounded-3xl border border-white/10 bg-charcoal/40 p-6">
      <div className="border-b border-white/10 pb-3">
        <h2 className="flex items-center gap-2 font-display text-lg font-bold text-paper">
          <ShieldCheck className="h-4 w-4 text-saffron" />
          Voter verification
        </h2>
        <p className="mt-1 font-mono text-[10px] leading-relaxed text-ash">
          Pick attributes from your uploaded database. Every roster entry must have a value in the chosen column.
        </p>
      </div>

      {error && <ErrorMessage error={error} />}

      {voters.length === 0 ? (
        <p className="font-mono text-[11px] text-amber-300">
          Upload the voter database first — the selectable attributes come from its columns.
        </p>
      ) : (
        <>
          <div>
            <p className="mb-2 font-mono text-[11px] tracking-wide text-ash">IDENTIFY VOTERS BY</p>
            <div className="grid gap-2">
              {option('rollNo', 'identity')}
              {option('name', 'identity')}
            </div>
          </div>

          <div>
            <p className="mb-2 font-mono text-[11px] tracking-wide text-ash">SEND ONE-TIME CODE TO</p>
            <div className="grid gap-2">
              {option('email', 'channel')}
              {option('phone', 'channel')}
            </div>
          </div>

          <Button
            size="sm"
            onClick={save}
            isLoading={saving}
            loadingText="Saving..."
            disabled={identity.length === 0 || channels.length === 0}
          >
            Save verification setup
          </Button>
          <p className="font-mono text-[10px] leading-relaxed text-ash/70">
            Voters match on the identity column, then prove ownership of the contact with a one-time code. Frozen
            when voting opens.
          </p>
        </>
      )}
    </section>
  )
}
