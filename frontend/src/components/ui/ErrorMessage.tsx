import { AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import type { ApiError } from '../../types'

interface ErrorMessageProps {
  error?: string | ApiError | null
  onRetry?: () => void
  className?: string
}

export function ErrorMessage({ error, onRetry, className = '' }: ErrorMessageProps) {
  if (!error) return null

  const errorObj = typeof error === 'string' ? { error: 'ERROR', message: error } : error

  return (
    <div
      role="alert"
      className={`rounded-2xl border border-red-500/40 bg-red-950/25 p-4 text-red-200 backdrop-blur-sm ${className}`}
    >
      <div className="flex items-start gap-3">
        <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold tracking-wider text-red-400">
              [{errorObj.error}]
            </span>
          </div>
          <p className="mt-1 text-sm leading-relaxed text-red-200/90">{errorObj.message}</p>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1.5 rounded-lg border border-red-400/30 bg-red-900/40 px-3 py-1.5 font-mono text-xs font-semibold text-red-200 transition hover:bg-red-800/50"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        )}
      </div>
    </div>
  )
}
