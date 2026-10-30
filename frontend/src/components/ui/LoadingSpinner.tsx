interface LoadingSpinnerProps {
  label?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingSpinner({
  label = 'Loading election data...',
  className = '',
  size = 'md',
}: LoadingSpinnerProps) {
  const sizeMap = {
    sm: 'h-4 w-4',
    md: 'h-7 w-7',
    lg: 'h-10 w-10',
  }

  return (
    <div className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
      <div
        className={`${sizeMap[size]} animate-spin rounded-full border-2 border-white/10 border-t-saffron`}
        role="status"
        aria-label={label}
      />
      {label && <p className="mt-3 font-mono text-xs tracking-wider text-ash">{label}</p>}
    </div>
  )
}
