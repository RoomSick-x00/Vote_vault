import { useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Plus, Trash2, UploadCloud } from 'lucide-react'
import { api } from '../services/api'
import type { ApiError, ColumnKey, Election, VoterImportReport, VoterInput, VoterRecord } from '../types'
import { Button } from './ui/Button'
import { ErrorMessage } from './ui/ErrorMessage'
import { Field } from './ui/Field'
import { columnHeaders, columnLabels, mandatoryColumns } from '../lib/voterColumns'

interface Props {
  election: Election
  voters: VoterRecord[]
  onChanged: () => void
}

const ACCEPT = '.csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const inputType: Record<ColumnKey, string> = { name: 'text', rollNo: 'text', email: 'email', phone: 'tel' }

export default function VoterDatabase({ election, voters, onChanged }: Props) {
  const [tab, setTab] = useState<'upload' | 'manual'>('upload')
  const [error, setError] = useState<ApiError | null>(null)
  const locked = election.status === 'closed'
  const columns = mandatoryColumns(election.voterSchema)

  // --- upload ---
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [report, setReport] = useState<VoterImportReport | null>(null)

  const upload = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    setReport(null)
    if (!/\.(csv|xlsx|xls)$/i.test(file.name)) {
      return setError({ error: 'INVALID_FILE', message: 'Please choose a .csv, .xlsx or .xls file.' })
    }
    setUploading(true)
    try {
      setReport(await api.uploadVoters(election.id, file))
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const downloadTemplate = () => {
    const blob = new Blob([columns.map((c) => columnHeaders[c]).join(',') + '\n'], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'voter-list-template.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  // --- manual ---
  const empty = (): Record<ColumnKey, string> => ({ name: '', rollNo: '', email: '', phone: '' })
  const [form, setForm] = useState(empty)
  const [adding, setAdding] = useState(false)
  const [added, setAdded] = useState<string | null>(null)

  const addVoter = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setAdded(null)
    const payload: VoterInput = {}
    for (const c of columns) payload[c] = form[c].trim()
    setAdding(true)
    try {
      await api.addVoter(election.id, payload)
      setAdded(payload.name || payload.rollNo || 'Voter')
      setForm(empty())
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setAdding(false)
    }
  }

  const remove = async (id: string) => {
    setError(null)
    try {
      await api.removeVoter(election.id, id)
      onChanged()
    } catch (err) {
      setError(err as ApiError)
    }
  }

  return (
    <div className="space-y-5 rounded-3xl border border-white/10 bg-charcoal/40 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div>
          <h2 className="font-display text-lg font-bold text-paper">Voter database</h2>
          <p className="text-xs text-ash">Only voters in this list can vote.</p>
        </div>
        <span className="rounded-full bg-electric/10 px-2.5 py-0.5 font-mono text-xs text-electric">
          {voters.length} VOTERS
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] tracking-wider text-ash">MANDATORY COLUMNS</span>
        {columns.map((c) => (
          <span key={c} className="rounded-full bg-saffron/10 px-2.5 py-0.5 font-mono text-[11px] text-saffron">
            {columnLabels[c]}
          </span>
        ))}
      </div>

      {error && <ErrorMessage error={error} />}

      {locked ? (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-ash">
          This election is closed. The voter list is locked.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-obsidian p-1">
            {(
              [
                ['upload', 'CSV / Excel upload'],
                ['manual', 'Manual entry'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`rounded-lg px-3 py-2 font-mono text-xs font-semibold transition ${
                  tab === key ? 'bg-saffron text-obsidian' : 'text-ash hover:text-paper'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === 'upload' ? (
            <div className="space-y-3">
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragging(true)
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragging(false)
                  upload(e.dataTransfer.files?.[0])
                }}
                className={`flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed p-8 text-center transition ${
                  dragging ? 'border-saffron bg-saffron/5' : 'border-white/15 bg-obsidian/50'
                }`}
              >
                <UploadCloud className="h-8 w-8 text-saffron" />
                <p className="text-sm text-paper">Drop your voter list here</p>
                <p className="text-xs text-ash">.csv, .xlsx or .xls · first row must be the header</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept={ACCEPT}
                  className="hidden"
                  onChange={(e) => upload(e.target.files?.[0])}
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  isLoading={uploading}
                  loadingText="Importing..."
                  onClick={() => fileRef.current?.click()}
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                  Choose file
                </Button>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ash">
                <span>
                  Required headers:{' '}
                  <code className="text-paper">{columns.map((c) => columnHeaders[c]).join(', ')}</code>
                </span>
                <button
                  type="button"
                  onClick={downloadTemplate}
                  className="inline-flex items-center gap-1 text-saffron hover:underline"
                >
                  <Download className="h-3 w-3" />
                  Download template
                </button>
              </div>

              {report && (
                <div
                  className={`rounded-2xl border p-4 text-xs ${
                    report.errors.length
                      ? 'border-amber-500/40 bg-amber-950/20 text-amber-200'
                      : 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300'
                  }`}
                >
                  <p className="flex items-center gap-2 font-semibold">
                    {report.errors.length ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                    {report.imported} imported · {report.skipped} skipped
                  </p>
                  {report.errors.length > 0 && (
                    <ul className="mt-2 max-h-32 space-y-0.5 overflow-auto font-mono text-[11px]">
                      {report.errors.slice(0, 50).map((er, i) => (
                        <li key={i}>
                          Row {er.row}: {er.message}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={addVoter} className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                {columns.map((c) => (
                  <Field
                    key={c}
                    label={columnLabels[c]}
                    type={inputType[c]}
                    value={form[c]}
                    onChange={(e) => setForm((f) => ({ ...f, [c]: e.target.value }))}
                    required
                  />
                ))}
              </div>
              <div className="flex items-center justify-between">
                <Button type="submit" size="sm" isLoading={adding} loadingText="Adding...">
                  <Plus className="h-3.5 w-3.5" />
                  Add voter
                </Button>
                {added && (
                  <span className="flex items-center gap-1.5 font-mono text-xs text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {added} added
                  </span>
                )}
              </div>
            </form>
          )}
        </>
      )}

      <div className="overflow-hidden rounded-2xl border border-white/10">
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-obsidian font-mono text-[10px] tracking-wider text-ash">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="px-3 py-2 font-medium">
                    {columnLabels[c].toUpperCase()}
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">STATUS</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 bg-obsidian/40">
              {voters.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 2} className="px-3 py-8 text-center text-ash">
                    No voters yet. Upload a file or add voters manually.
                  </td>
                </tr>
              ) : (
                voters.map((v) => (
                  <tr key={v.id} className="text-paper">
                    {columns.map((c) => (
                      <td key={c} className="max-w-[180px] truncate px-3 py-2">
                        {v[c] || '—'}
                      </td>
                    ))}
                    <td className="px-3 py-2">
                      {v.hasVoted ? (
                        <span className="rounded bg-emerald-950/40 px-2 py-0.5 font-mono text-[10px] text-emerald-400">
                          VOTED
                        </span>
                      ) : (
                        <span className="font-mono text-[10px] text-ash">PENDING</span>
                      )}
                    </td>
                    <td className="px-2">
                      {!locked && !v.hasVoted && (
                        <button
                          type="button"
                          onClick={() => remove(v.id)}
                          className="text-ash transition hover:text-red-400"
                          aria-label="Remove voter"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
