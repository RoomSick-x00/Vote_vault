import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  Search,
  Database,
  RefreshCw,
  GitCommit,
  AlertCircle,
  Hash,
  Shield,
  FileCheck2,
} from 'lucide-react'
import { api } from '../services/api'
import { useAuth } from '../context/AuthContext'
import type { ElectionResults, ReceiptLookupResult, ApiError } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'

export default function ResultsAudit() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const backTo = user ? '/organizer' : '/voter'
  const backLabel = user ? 'Dashboard' : 'Voter Hub'
  const [results, setResults] = useState<ElectionResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  // Receipt lookup states
  const [lookupCode, setLookupCode] = useState('')
  const [lookupResult, setLookupResult] = useState<ReceiptLookupResult | null>(null)
  const [searching, setSearching] = useState(false)
  const [lookupError, setLookupError] = useState<string | null>(null)

  const fetchResults = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.getResults(id)
      setResults(data)
    } catch (err: any) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchResults()
  }, [id])

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !lookupCode.trim()) return

    setSearching(true)
    setLookupError(null)
    setLookupResult(null)

    try {
      const res = await api.lookupReceipt(id, lookupCode.trim())
      setLookupResult(res)
    } catch (err: any) {
      setLookupError(err?.message || 'Lookup failed')
    } finally {
      setSearching(false)
    }
  }

  if (loading) {
    return <LoadingSpinner label="Loading results..." />
  }

  if (!results) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12 text-center">
        <ErrorMessage error={error || 'Unable to retrieve results'} />
        <p className="mt-2 text-xs text-ash">
          Results and tallies become available once the election is officially closed.
        </p>
        <Link to={backTo} className="mt-4 inline-block">
          <Button variant="secondary">Back to {backLabel}</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Navigation */}
      <div className="mb-6 flex items-center justify-between">
        <Link
          to={backTo}
          className="inline-flex items-center gap-2 font-mono text-xs text-ash transition hover:text-paper"
        >
          <ArrowLeft className="h-4 w-4" />
          BACK TO {backLabel.toUpperCase()}
        </Link>

        <Button variant="ghost" size="sm" onClick={fetchResults}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {/* Election Results Header */}
      <div className="rounded-3xl border border-white/10 bg-charcoal/60 p-6 sm:p-8 backdrop-blur-xl">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <StatusBadge status={results.status} type="election" />
              <StatusBadge
                status={results.blockchainReference.commitmentStatus}
                type="commitment"
              />
            </div>
            <h1 className="mt-2 font-display text-3xl font-bold text-paper">{results.title}</h1>
          </div>

          <div className="text-right">
            <p className="font-mono text-[10px] tracking-wider text-ash">TOTAL BALLOTS RECORDED</p>
            <p className="font-display text-3xl font-bold text-saffron">{results.totalBallots}</p>
          </div>
        </div>

        {/* Tally */}
        <div className="mt-6 space-y-4">
          <h2 className="font-mono text-xs font-semibold tracking-wider text-ash">
            FINAL TALLY
          </h2>

          <div className="space-y-4">
            {results.tally.map((cand) => (
              <div
                key={cand.candidateId}
                className="rounded-2xl border border-white/10 bg-obsidian/70 p-4"
              >
                <div className="flex items-center justify-between font-display text-sm">
                  <span className="font-bold text-paper">{cand.candidateName}</span>
                  <span className="font-mono text-xs font-bold text-saffron">
                    {cand.count} votes ({cand.percentage}%)
                  </span>
                </div>

                {/* Progress bar */}
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full bg-saffron transition-all duration-500"
                    style={{ width: `${cand.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Blockchain References */}
        <div className="mt-8 rounded-2xl border border-white/10 bg-obsidian/80 p-5 font-mono text-xs space-y-2">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-ash">BLOCKCHAIN RESULT STATUS:</span>
            <span className="font-bold text-emerald-400">RECORDED ON BLOCKCHAIN</span>
          </div>

          {results.blockchainReference.blockNumber && (
            <div className="flex items-center justify-between">
              <span className="text-ash">BLOCK HEIGHT:</span>
              <span className="text-paper">#{results.blockchainReference.blockNumber}</span>
            </div>
          )}

          {results.blockchainReference.resultTxHash && (
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-ash">TRANSACTION REF:</span>
              <code className="break-all text-[11px] text-paper/80 sm:max-w-[340px] sm:truncate">
                {results.blockchainReference.resultTxHash}
              </code>
            </div>
          )}

          {results.blockchainReference.resultCommitment && (
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-ash">RESULT COMMITMENT:</span>
              <code className="break-all text-[11px] text-saffron sm:max-w-[340px] sm:truncate">
                {results.blockchainReference.resultCommitment}
              </code>
            </div>
          )}
        </div>
      </div>

      {/* Commitment & Receipt Audit Lookup */}
      <div className="mt-8 rounded-3xl border border-white/10 bg-charcoal/40 p-6 sm:p-8 space-y-6">
        <div>
          <h2 className="font-display text-xl font-bold text-paper">
            Ballot Commitment Audit Lookup
          </h2>
          <p className="mt-1 text-xs text-ash">
            Check that a ballot receipt is recorded in this election’s ledger.
          </p>
        </div>

        <form onSubmit={handleLookup} className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ash" />
            <input
              type="text"
              value={lookupCode}
              onChange={(e) => setLookupCode(e.target.value)}
              placeholder="Enter receipt ID (e.g. VV-REC-XXXX) or 0x commitment hash"
              required
              className="w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 pl-10 font-mono text-xs text-paper focus:border-saffron focus:outline-none"
            />
          </div>
          <Button type="submit" variant="primary" isLoading={searching} loadingText="Looking up...">
            Lookup Commitment
          </Button>
        </form>

        {lookupError && <ErrorMessage error={lookupError} />}

        {lookupResult && (
          <div
            className={`rounded-2xl border p-5 font-mono text-xs ${
              lookupResult.found
                ? 'border-emerald-500/40 bg-emerald-950/20 text-emerald-200'
                : 'border-red-500/40 bg-red-950/20 text-red-200'
            }`}
          >
            <div className="flex items-center gap-2">
              {lookupResult.found ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
              ) : (
                <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
              )}
              <span className="font-bold">
                {lookupResult.found ? 'COMMITMENT MATCHED' : 'COMMITMENT NOT FOUND'}
              </span>
            </div>

            <p className="mt-2 text-xs leading-relaxed opacity-90">{lookupResult.message}</p>

            {lookupResult.found && (
              <div className="mt-4 border-t border-white/10 pt-3 space-y-1 text-[11px]">
                {lookupResult.receiptId && (
                  <div>
                    <span className="opacity-70">RECEIPT ID:</span>{' '}
                    <span className="text-paper">{lookupResult.receiptId}</span>
                  </div>
                )}
                {lookupResult.blockNumber && (
                  <div>
                    <span className="opacity-70">RECORDED BLOCK:</span>{' '}
                    <span className="text-paper">#{lookupResult.blockNumber}</span>
                  </div>
                )}
                {lookupResult.txHash && (
                  <div className="break-all">
                    <span className="opacity-70">TX HASH:</span>{' '}
                    <span className="text-paper/80">{lookupResult.txHash}</span>
                  </div>
                )}
                <div>
                  <span className="opacity-70">STATUS:</span>{' '}
                  <span className="font-bold text-emerald-300">
                    {lookupResult.recordedOnBlockchain
                      ? 'RECORDED ON BLOCKCHAIN'
                      : 'PENDING PUBLICATION'}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
