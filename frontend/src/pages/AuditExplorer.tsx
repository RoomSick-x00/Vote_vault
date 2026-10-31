import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type AuditCheck, type AuditRecord } from '../services/api'
import { Button } from '../components/ui/Button'

export default function AuditExplorer() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [input, setInput] = useState(id || '')
  const [record, setRecord] = useState<AuditRecord | null>(null)
  const [checks, setChecks] = useState<AuditCheck[]>([])
  const [control, setControl] = useState<AuditCheck[]>([])
  const [lab, setLab] = useState<AuditCheck[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!id) return
    let active = true
    setInput(id); setBusy(true); setError(''); setRecord(null); setLab(null)
    api.auditRecord(id).then(async r => {
      const verified = await api.verifyAudit(r)
      if (active) { setRecord(r); setChecks(verified.checks) }
    }).catch(e => { if (active) setError(e.message || 'Unable to load records') }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [id])
  async function mutate(kind: string) {
    if (!record) return
    setBusy(true); setError('')
    try {
      const copy = structuredClone(record)
      if (kind === 'ballot') { const b = copy.records.find(r => r.type === 'publish_ballot'); if (!b) throw new Error('A published ballot record is required.'); b.payload.commitment = '0x' + '00'.repeat(32) }
      if (kind === 'remove') { const i = copy.records.findIndex(r => r.type === 'publish_ballot'); if (i < 0) throw new Error('A ballot record is required.'); copy.records.splice(i, 1) }
      if (kind === 'result') { if (!copy.result?.counts.length) throw new Error('Published result data is required.'); copy.result.counts[0].votes += 1 }
      if (kind === 'id') copy.election_id = '00000000-0000-0000-0000-000000000001'
      const [original, changed] = await Promise.all([api.verifyAudit(record), api.verifyAudit(copy)])
      setControl(original.checks); setLab(changed.checks)
    } catch (e) { setError((e as Error).message || 'Verification failed') } finally { setBusy(false) }
  }
  return <div className="mx-auto max-w-5xl px-4 py-10 space-y-6">
    <h1 className="font-display text-3xl font-bold">Audit Explorer</h1>
    <p className="text-ash">Record integrity and inclusion checks compare public records with the configured blockchain. They do not prove ballot secrecy, eligibility, or correct counting.</p>
    <form className="flex gap-2" onSubmit={e => { e.preventDefault(); navigate(`/audit/${encodeURIComponent(input.trim())}`) }}><input className="w-full rounded-xl bg-charcoal p-3" aria-label="Election ID" placeholder="Election UUID" value={input} onChange={e => setInput(e.target.value)} /><Button>Inspect</Button></form>
    {busy && <p>Checking…</p>}{error && <p role="alert" className="text-red-400">{error}</p>}
    {record && <><p className="text-sm text-ash">Election {record.election_id} · {record.status}</p><Checks title="Verification" checks={checks} />
      <details className="rounded-xl border border-white/10 p-4"><summary>Public configuration, ballot commitments, transaction references and results</summary><pre className="overflow-auto whitespace-pre-wrap break-all text-xs mt-3">{JSON.stringify(record, null, 2)}</pre></details>
      <section className="rounded-xl border border-white/10 p-5 space-y-4"><h2 className="font-display text-xl">Tamper Lab</h2><p className="text-sm text-ash">Each experiment changes an in-memory copy. Both the original and the copy run through the same verifier against the chain.</p><div className="flex flex-wrap gap-2">{[['ballot','Change ballot commitment'],['remove','Remove ballot record'],['result','Change result data'],['id','Wrong election ID']].map(([k,label]) => <Button key={k} variant="secondary" disabled={busy} onClick={() => void mutate(k)}>{label}</Button>)}</div>{lab && <><Checks title="Unchanged control" checks={control}/><Checks title="Altered copy" checks={lab}/></>}</section></>}
  </div>
}
function Checks({title, checks}: {title: string; checks: AuditCheck[]}) { return <section className="space-y-2"><h2 className="font-display text-xl">{title}</h2>{checks.map((c,i) => <div key={i} className="rounded-xl border border-white/10 bg-charcoal/60 p-3 text-sm"><strong className={c.status === 'PASS' ? 'text-emerald-400' : c.status === 'FAIL' ? 'text-red-400' : 'text-amber-300'}>{c.status}</strong> <code>{c.id}</code> — {c.reason}</div>)}</section> }
