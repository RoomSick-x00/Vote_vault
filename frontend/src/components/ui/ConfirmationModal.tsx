import { useEffect, useRef } from 'react'
import { AlertCircle, X } from 'lucide-react'
import { Button } from './Button'

interface ConfirmationModalProps {
  isOpen: boolean
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'primary'
  isLoading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmationModal({
  isOpen,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'primary',
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmationModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoading) {
        onCancel()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isLoading, onCancel])

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity"
        onClick={() => !isLoading && onCancel()}
      />

      {/* Modal Dialog */}
      <div
        ref={modalRef}
        className="relative w-full max-w-md rounded-3xl border border-white/15 bg-charcoal p-6 shadow-2xl transition-all"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${
                variant === 'danger'
                  ? 'bg-red-500/10 text-red-400'
                  : 'bg-saffron/10 text-saffron'
              }`}
            >
              <AlertCircle className="h-5 w-5" />
            </div>
            <h3 id="modal-title" className="font-display text-lg font-bold text-paper">
              {title}
            </h3>
          </div>
          <button
            type="button"
            disabled={isLoading}
            onClick={onCancel}
            aria-label="Close dialog"
            className="rounded-lg p-1 text-ash hover:text-paper"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-ash">{description}</p>

        <div className="mt-6 flex items-center justify-end gap-3">
          <Button variant="ghost" size="sm" disabled={isLoading} onClick={onCancel}>
            {cancelText}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            size="sm"
            isLoading={isLoading}
            onClick={onConfirm}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  )
}
