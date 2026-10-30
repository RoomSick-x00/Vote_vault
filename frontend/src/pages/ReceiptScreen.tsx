import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ShieldCheck,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Copy,
  ExternalLink,
  ArrowRight,
  Hash,
  Database,
  Lock,
} from 'lucide-react'
import { api } from '../services/api'
import type { BallotReceipt, ApiError } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'

export default function ReceiptScreen() {
  const { receiptId } = useParams<{ receiptId: string }>()
  const [receipt, setReceipt] = useState<BallotReceipt | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchReceipt = async (isManualRefresh = false) => {
    if (!receiptId) return
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)

    try {
      const data = await api.getReceipt(receiptId)
      setReceipt(data)
    } catch (err: any) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchReceipt()

    // While pending, poll every 2 seconds until the transaction is confirmed
    const interval = setInterval(() => {
      if (receiptId && receipt?.status === 'pending') {
        api.getReceipt(receiptId).then((updated) => {
          setReceipt(updated)
        }).catch(() => {})
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [receiptId, receipt?.status])

  const handleCopy = () => {
    if (!receipt) return
    navigator.clipboard.writeText(receipt.commitment)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) {
    return <LoadingSpinner label="Retrieving cryptographic ballot receipt..." />
  }

  if (!receipt) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12 text-center">
        <ErrorMessage error={error || 'Receipt not found.'} />
        <Link to="/voter" className="mt-4 inline-block">
          <Button variant="secondary">Back to Elections</Button>
        </Link>
      </div>
    )
  }

  const isConfirmed = receipt.status === 'confirmed'
  const isPending = receipt.status === 'pending'
  const isFailed = receipt.status === 'failed'

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Top Banner */}
      <div className="mb-8 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400">
          <ShieldCheck className="h-8 w-8" />
        </div>
        <span className="mt-3 block font-mono text-[11px] tracking-[0.24em] text-saffron">
          CRYPTOGRAPHIC PROOF OF SUBMISSION
        </span>
        <h1 className="mt-1 font-display text-3xl font-bold text-paper">Ballot Receipt</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-ash">
          Your ballot has been recorded. Save this receipt identifier — you can use it to confirm your ballot is counted once results are published.
        </p>
      </div>

      {error && <ErrorMessage error={error} className="mb-6" />}

      {/* Main Receipt Certificate */}
      <div className="rounded-3xl border border-white/15 bg-charcoal/80 p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
        {/* Status Header */}
        <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center">
          <div>
            <p className="font-mono text-[10px] tracking-wider text-ash">RECEIPT IDENTIFIER</p>
            <p className="font-mono text-xl font-bold text-paper tracking-wider">{receipt.receiptId}</p>
          </div>

          <div className="flex items-center gap-3">
            <StatusBadge status={receipt.status} type="publication" />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fetchReceipt(true)}
              disabled={refreshing}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh Status
            </Button>
          </div>
        </div>

        {/* Commitment Reference */}
        <div className="mt-6 space-y-4">
          <div>
            <div className="flex items-center justify-between">
              <label className="font-mono text-xs font-semibold tracking-wider text-ash">
                BALLOT COMMITMENT REFERENCE (SHA-256)
              </label>
              <button
                type="button"
                onClick={handleCopy}
                className="flex items-center gap-1 font-mono text-[11px] text-saffron hover:underline"
              >
                <Copy className="h-3 w-3" />
                {copied ? 'Copied!' : 'Copy Hash'}
              </button>
            </div>
            <div className="mt-1.5 break-all rounded-2xl border border-white/10 bg-obsidian p-4 font-mono text-xs text-paper/90 select-all">
              {receipt.commitment}
            </div>
          </div>

          {/* Blockchain Publication State */}
          <div className="rounded-2xl border border-white/10 bg-obsidian/60 p-5 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between">
              <span className="text-ash">RELAYER PUBLICATION:</span>
              <span
                className={`font-bold ${
                  isConfirmed
                    ? 'text-emerald-400'
                    : isPending
                      ? 'text-amber-400 animate-pulse'
                      : 'text-red-400'
                }`}
              >
                {isConfirmed
                  ? 'CONFIRMED ON-CHAIN'
                  : isPending
                    ? 'PENDING BLOCK MINING...'
                    : 'TRANSACTION FAILED'}
              </span>
            </div>

            {receipt.blockNumber && (
              <div className="flex items-center justify-between">
                <span className="text-ash">BLOCK NUMBER:</span>
                <span className="text-paper">#{receipt.blockNumber}</span>
              </div>
            )}

            {receipt.txHash && (
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-ash">TRANSACTION HASH:</span>
                <code className="break-all text-[11px] text-paper/80 sm:max-w-[320px] sm:truncate">
                  {receipt.txHash}
                </code>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-ash">SUBMITTED AT:</span>
              <span className="text-paper">{new Date(receipt.createdAt).toLocaleString()}</span>
            </div>

            {receipt.confirmedAt && (
              <div className="flex items-center justify-between">
                <span className="text-ash">CONFIRMED AT:</span>
                <span className="text-emerald-300">
                  {new Date(receipt.confirmedAt).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Voter Privacy Notice (Rule: Do not display another voter's identity or ballot details) */}
        <div className="mt-6 border-t border-white/10 pt-5 text-xs text-ash leading-relaxed space-y-1">
          <p className="flex items-center gap-2 font-mono text-[11px] text-paper">
            <Lock className="h-3.5 w-3.5 text-saffron shrink-0" />
            <span>Candidate Choice Intentionally Omitted from Receipt</span>
          </p>
          <p className="text-[11px] text-ash/80">
            In compliance with secret-ballot standards, this receipt confirms that your ballot commitment was recorded on the blockchain without revealing which candidate was selected.
          </p>
        </div>
      </div>

      {/* Action Links */}
      <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Link to="/voter">
          <Button variant="secondary">← Back to Voter Hub</Button>
        </Link>

        <Link to={`/results/${receipt.electionId}`}>
          <Button variant="primary">
            <span>Check Election Results & Ledger</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </div>
  )
}
