import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, Copy, Lock, RefreshCw, ShieldCheck } from 'lucide-react'
import { api, getVoterToken } from '../services/api'
import type { ApiError, BallotReceipt } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import VoterSignIn from '../components/voter/VoterSignIn'

/**
 * Ballot receipt: cryptographic commitment + nonce + on-chain publication
 * status. Visible only to the submitting voter (backend enforces it), so a
 * fresh tab asks for sign-in again.
 */
export default function ReceiptScreen() {
  const { electionId, receiptId } = useParams<{ electionId: string; receiptId: string }>()
  const [receipt, setReceipt] = useState<BallotReceipt | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [needsSignIn, setNeedsSignIn] = useState(false)
  const [copied, setCopied] = useState<'commitment' | 'nonce' | null>(null)

  const fetchReceipt = useCallback(
    async (isManualRefresh = false) => {
      if (!electionId || !receiptId) return
      if (isManualRefresh) setRefreshing(true)
      else setLoading(true)
      setError(null)
      try {
        setReceipt(await api.getReceipt(electionId, receiptId))
      } catch (err) {
        const apiErr = err as ApiError
        setNeedsSignIn(apiErr.error === 'UNAUTHENTICATED')
        setError(apiErr)
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [electionId, receiptId]
  )

  useEffect(() => {
    if (getVoterToken()) fetchReceipt()
    else {
      setNeedsSignIn(true)
      setLoading(false)
    }
  }, [fetchReceipt])

  // Poll while pending until the publication job confirms or fails.
  useEffect(() => {
    if (receipt?.status !== 'pending') return
    const timer = setInterval(() => fetchReceipt(true), 2500)
    return () => clearInterval(timer)
  }, [receipt?.status, fetchReceipt])

  const copy = async (kind: 'commitment' | 'nonce') => {
    if (!receipt) return
    try {
      await navigator.clipboard.writeText(kind === 'commitment' ? receipt.commitment : receipt.nonce)
      setCopied(kind)
      setTimeout(() => setCopied(null), 2000)
    } catch {
      /* clipboard unavailable */
    }
  }

  if (loading) return <LoadingSpinner label="Retrieving cryptographic ballot receipt..." />

  if (needsSignIn) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-140px)] max-w-md flex-col justify-center px-4 py-10">
        <div className="rounded-3xl border border-white/10 bg-charcoal/70 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
          <p className="mb-4 text-sm text-ash">
            Receipts are visible only to the voter who submitted them. Sign in with the account you voted with.
          </p>
          <VoterSignIn onSignedIn={() => fetchReceipt()} />
        </div>
      </div>
    )
  }

  if (!receipt) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12 text-center">
        <ErrorMessage error={error || 'Receipt not found.'} />
        <Link to="/voter" className="mt-4 inline-block">
          <Button variant="secondary">Back to Voter Hub</Button>
        </Link>
      </div>
    )
  }

  const isConfirmed = receipt.status === 'confirmed'
  const isPending = receipt.status === 'pending'

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
          Keep the commitment and nonce — together they let you recompute your ballot commitment and confirm it was
          counted once results are published.
        </p>
      </div>

      {error && <ErrorMessage error={error} className="mb-6" />}

      {/* Main Receipt Certificate */}
      <div className="rounded-3xl border border-white/15 bg-charcoal/80 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
        {/* Status Header */}
        <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center">
          <div className="min-w-0">
            <p className="font-mono text-[10px] tracking-wider text-ash">RECEIPT ID</p>
            <p className="truncate font-mono text-sm font-bold tracking-wider text-paper">{receipt.receipt_id}</p>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <StatusBadge status={receipt.status} type="publication" />
            <Button variant="secondary" size="sm" onClick={() => fetchReceipt(true)} disabled={refreshing}>
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="mt-6 space-y-4">
          {/* Commitment */}
          <div>
            <div className="flex items-center justify-between">
              <label className="font-mono text-xs font-semibold tracking-wider text-ash">BALLOT COMMITMENT</label>
              <button
                type="button"
                onClick={() => copy('commitment')}
                className="flex items-center gap-1 font-mono text-[11px] text-saffron hover:underline"
              >
                <Copy className="h-3 w-3" />
                {copied === 'commitment' ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <div className="mt-1.5 break-all rounded-2xl border border-white/10 bg-obsidian p-4 font-mono text-xs text-paper/90 select-all">
              {receipt.commitment}
            </div>
          </div>

          {/* Nonce */}
          <div>
            <div className="flex items-center justify-between">
              <label className="font-mono text-xs font-semibold tracking-wider text-ash">
                COMMITMENT NONCE (KEEP PRIVATE)
              </label>
              <button
                type="button"
                onClick={() => copy('nonce')}
                className="flex items-center gap-1 font-mono text-[11px] text-saffron hover:underline"
              >
                <Copy className="h-3 w-3" />
                {copied === 'nonce' ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <div className="mt-1.5 break-all rounded-2xl border border-white/10 bg-obsidian p-4 font-mono text-xs text-paper/90 select-all">
              {receipt.nonce}
            </div>
          </div>

          {/* Blockchain Publication State */}
          <div className="space-y-3 rounded-2xl border border-white/10 bg-obsidian/60 p-5 font-mono text-xs">
            <div className="flex items-center justify-between">
              <span className="text-ash">CHAIN PUBLICATION:</span>
              <span
                className={`font-bold ${
                  isConfirmed ? 'text-emerald-400' : isPending ? 'animate-pulse text-amber-400' : 'text-red-400'
                }`}
              >
                {isConfirmed ? 'CONFIRMED ON-CHAIN' : isPending ? 'PENDING PUBLICATION…' : 'PUBLICATION FAILED'}
              </span>
            </div>

            {receipt.block_number != null && (
              <div className="flex items-center justify-between">
                <span className="text-ash">BLOCK NUMBER:</span>
                <span className="text-paper">#{receipt.block_number}</span>
              </div>
            )}

            {receipt.transaction_hash && (
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-ash">TRANSACTION HASH:</span>
                <code className="break-all text-[11px] text-paper/80 sm:max-w-[320px] sm:truncate">
                  {receipt.transaction_hash}
                </code>
              </div>
            )}

            {receipt.submitted_at && (
              <div className="flex items-center justify-between">
                <span className="text-ash">SUBMITTED AT:</span>
                <span className="text-paper">{new Date(receipt.submitted_at).toLocaleString()}</span>
              </div>
            )}

            {receipt.confirmed_at && (
              <div className="flex items-center justify-between">
                <span className="text-ash">CONFIRMED AT:</span>
                <span className="text-emerald-300">{new Date(receipt.confirmed_at).toLocaleString()}</span>
              </div>
            )}

            {receipt.error && (
              <p className="break-all rounded-lg border border-red-500/20 bg-red-950/20 p-2 text-[10px] text-red-300">
                {receipt.error}
              </p>
            )}
          </div>
        </div>

        {/* Voter Privacy Notice */}
        <div className="mt-6 space-y-1 border-t border-white/10 pt-5 text-xs leading-relaxed text-ash">
          <p className="flex items-center gap-2 font-mono text-[11px] text-paper">
            <Lock className="h-3.5 w-3.5 shrink-0 text-saffron" />
            <span>Secret ballot preserved</span>
          </p>
          <p className="text-[11px] text-ash/80">
            The receipt records a commitment to your choice — never the choice itself. Even this screen shows only
            the candidate ID, not the name you selected.
          </p>
        </div>
      </div>

      {/* Action Links */}
      <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Link to="/voter">
          <Button variant="secondary">← Back to Voter Hub</Button>
        </Link>

        <Link to={`/results/${electionId}`}>
          <Button>
            <span>Check election results</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </div>
  )
}
