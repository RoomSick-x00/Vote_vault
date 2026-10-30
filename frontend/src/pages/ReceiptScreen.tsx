import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, RefreshCw, ShieldCheck } from 'lucide-react'
import { api, getVoterToken } from '../services/api'
import type { ApiError, VoterReceipt } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'

export default function ReceiptScreen() {
  const { electionId, receiptId } = useParams<{ electionId: string; receiptId: string }>()
  const [receipt, setReceipt] = useState<VoterReceipt | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const fetchReceipt = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const current = await api.getVoterReceipt()
      if (current.electionId !== electionId || current.receiptId !== receiptId) {
        throw { error: 'NOT_FOUND', message: 'This receipt does not match the active voter session.' } satisfies ApiError
      }
      setReceipt(current)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [electionId, receiptId])

  useEffect(() => {
    if (getVoterToken()) void fetchReceipt()
    else {
      setError({ error: 'UNAUTHENTICATED', message: 'The voter session has expired. Return to the election code to verify again.' })
      setLoading(false)
    }
  }, [fetchReceipt])

  useEffect(() => {
    if (receipt?.status !== 'pending') return
    const timer = setInterval(() => void fetchReceipt(true), 2500)
    return () => clearInterval(timer)
  }, [receipt?.status, fetchReceipt])

  if (loading) return <LoadingSpinner label="Checking ballot publication..." />

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

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 text-center">
        <ShieldCheck className="mx-auto h-12 w-12 text-emerald-400" />
        <p className="mt-3 font-mono text-[11px] tracking-[0.24em] text-saffron">BALLOT RECEIPT</p>
        <h1 className="mt-1 font-display text-3xl font-bold text-paper">Submission status</h1>
      </div>

      {error && <ErrorMessage error={error} className="mb-6" />}

      <section className="rounded-3xl border border-white/15 bg-charcoal/80 p-6 shadow-2xl sm:p-8">
        <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center">
          <div className="min-w-0">
            <p className="font-mono text-[10px] tracking-wider text-ash">RECEIPT ID</p>
            <p className="truncate font-mono text-sm font-bold text-paper">{receipt.receiptId}</p>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={receipt.status} type="publication" />
            <Button variant="secondary" size="sm" onClick={() => void fetchReceipt(true)} disabled={refreshing}>
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="mt-6 space-y-4 font-mono text-xs">
          <div>
            <p className="text-ash">BALLOT COMMITMENT</p>
            <p className="mt-1 break-all rounded-xl border border-white/10 bg-obsidian p-4 text-paper">{receipt.commitment}</p>
          </div>
          {receipt.blockNumber != null && <p className="text-ash">BLOCK NUMBER: <span className="text-paper">#{receipt.blockNumber}</span></p>}
          {receipt.txHash && (
            <p className="break-all text-ash">TRANSACTION: <span className="text-paper">{receipt.txHash}</span></p>
          )}
          <p className="text-ash">SUBMITTED: <span className="text-paper">{new Date(receipt.createdAt).toLocaleString()}</span></p>
          {receipt.confirmedAt && (
            <p className="text-ash">CONFIRMED: <span className="text-emerald-300">{new Date(receipt.confirmedAt).toLocaleString()}</span></p>
          )}
        </div>

        <div className="mt-6 border-t border-white/10 pt-5 text-xs leading-relaxed text-ash">
          The public chain contains the commitment, not the selected candidate. This receipt confirms submission and
          publication status; it is not an independent proof of ballot secrecy or tally correctness.
        </div>
      </section>

      <div className="mt-8 flex justify-between">
        <Link to="/voter"><Button variant="secondary"><ArrowLeft className="h-4 w-4" /> Voter Hub</Button></Link>
        <Link to={`/results/${electionId}`}><Button>Election results</Button></Link>
      </div>
    </div>
  )
}
