import { useRef, useState } from 'react'
import { FileUp, Trash2 } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, VoterImportReport, VoterRecord } from '../types'
import { Button } from './ui/Button'
import { ErrorMessage } from './ui/ErrorMessage'

interface VoterRosterProps {
  electionId: string
  voters: VoterRecord[]
  onChanged: () => void
  disabled?: boolean
  canUpload?: boolean
  canDelete?: boolean
}

export default function VoterRoster({
  electionId,
  voters,
  onChanged,
  disabled,
  canUpload,
  canDelete,
}: VoterRosterProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [report, setReport] = useState<VoterImportReport | null>(null)

  const upload = async (file?: File) => {
    if (!file) return
    setError(null)
    setReport(null)
    setUploading(true)
    try {
      const result = await api.uploadVoters(electionId, file)
      setReport(result)
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const remove = async (voter: VoterRecord) => {
    if (!canDelete || !window.confirm(`Remove ${voter.name || voter.rollNo || 'this voter'} from the roster?`)) return
    setDeleting(voter.id)
    setError(null)
    try {
      await api.deleteVoter(electionId, voter.id)
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <section className="space-y-4 self-start rounded-3xl border border-white/10 bg-charcoal/40 p-6">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div>
          <h2 className="font-display text-lg font-bold text-paper">Voter roster</h2>
          <p className="mt-1 font-mono text-[10px] text-ash">{voters.length} registered</p>
        </div>
        {canUpload && (
          <Button size="sm" onClick={() => inputRef.current?.click()} isLoading={uploading} loadingText="Importing...">
            <FileUp className="h-3.5 w-3.5" />
            Upload CSV/XLSX
          </Button>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={(event) => upload(event.target.files?.[0])}
        disabled={disabled || uploading}
      />

      {canDelete && (
        <p className="font-mono text-[10px] leading-relaxed text-ash/70">
          Include the configured identity columns and contact columns in the header row. The roster is organizer-only;
          voters use their election code and a one-time code sent to their registered contact.
        </p>
      )}
      {error && <ErrorMessage error={error} />}
      {report && (
        <div className="space-y-2 rounded-xl border border-white/10 bg-obsidian/60 p-3 font-mono text-[11px]">
          <p className="text-paper">
            Imported {report.imported}; skipped {report.skipped}.
          </p>
          {report.errors.map((item, index) => (
            <p key={`${item.row}-${index}`} className="text-amber-300">
              Row {item.row}: {item.message}
            </p>
          ))}
        </div>
      )}

      {voters.length > 0 ? (
        <ul className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {voters.map((voter) => (
            <li
              key={voter.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-obsidian/70 px-3 py-2"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm text-paper">{voter.name || voter.rollNo || 'Voter'}</span>
                <span className="block truncate font-mono text-[10px] text-ash">
                  {[voter.rollNo, voter.email, voter.phone].filter(Boolean).join(' · ')}
                </span>
              </span>
              <span className={`shrink-0 font-mono text-[10px] ${voter.hasVoted ? 'text-emerald-300' : 'text-ash'}`}>
                {voter.hasVoted ? 'VOTED' : 'NOT VOTED'}
              </span>
              {canDelete && (
                <button
                  type="button"
                  aria-label={`Remove ${voter.name || voter.rollNo || 'voter'}`}
                  disabled={disabled || deleting === voter.id}
                  onClick={() => remove(voter)}
                  className="shrink-0 text-ash hover:text-red-400 disabled:opacity-40"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="font-mono text-[11px] text-amber-300">
          {canDelete ? 'Upload a roster before opening this election.' : 'No roster entries.'}
        </p>
      )}
    </section>
  )
}
