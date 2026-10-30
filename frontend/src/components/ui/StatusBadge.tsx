import type { ElectionStatus, PublicationStatus, ResultCommitmentStatus } from '../../types'

interface StatusBadgeProps {
  status?: ElectionStatus | PublicationStatus | ResultCommitmentStatus | 'valid' | 'tampered'
  type?: 'election' | 'publication' | 'commitment'
  className?: string
}

export function StatusBadge({ status, type = 'election', className = '' }: StatusBadgeProps) {
  if (!status) return null

  // Election Status: draft, open, closed
  if (type === 'election') {
    switch (status) {
      case 'open':
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-950/40 px-2.5 py-0.5 font-mono text-[11px] font-medium text-emerald-400 ${className}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            VOTING OPEN
          </span>
        )
      case 'closed':
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-950/40 px-2.5 py-0.5 font-mono text-[11px] font-medium text-amber-400 ${className}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
            CLOSED
          </span>
        )
      case 'draft':
      default:
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/5 px-2.5 py-0.5 font-mono text-[11px] font-medium text-ash ${className}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-ash" />
            DRAFT
          </span>
        )
    }
  }

  // Publication Status: pending, confirmed, failed
  if (type === 'publication' || type === 'commitment') {
    switch (status) {
      case 'confirmed':
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-950/40 px-2.5 py-0.5 font-mono text-[11px] font-medium text-emerald-300 ${className}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            RECORDED ON BLOCKCHAIN
          </span>
        )
      case 'pending':
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-950/40 px-2.5 py-0.5 font-mono text-[11px] font-medium text-amber-300 ${className}`}
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
            PUBLICATION PENDING
          </span>
        )
      case 'failed':
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-950/40 px-2.5 py-0.5 font-mono text-[11px] font-medium text-red-400 ${className}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
            PUBLICATION FAILED
          </span>
        )
      default:
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 font-mono text-[11px] font-medium text-ash ${className}`}
          >
            UNCOMMITTED
          </span>
        )
    }
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 font-mono text-[11px] text-ash ${className}`}
    >
      {status}
    </span>
  )
}
