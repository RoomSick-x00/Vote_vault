import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  loadingText?: string
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loadingText,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs font-medium',
    md: 'px-4 py-2.5 text-sm font-semibold',
    lg: 'px-6 py-3 text-base font-semibold',
  }

  const variantClasses = {
    primary:
      'bg-saffron text-obsidian font-display hover:bg-[#ffa94d] active:translate-y-px shadow-sm shadow-saffron/20 disabled:bg-saffron/40 disabled:text-obsidian/60',
    secondary:
      'bg-charcoal text-paper border border-white/15 hover:border-white/30 hover:bg-white/5 active:translate-y-px disabled:opacity-50',
    danger:
      'bg-red-950/40 text-red-300 border border-red-500/30 hover:bg-red-900/40 active:translate-y-px disabled:opacity-40',
    outline:
      'border border-white/20 text-paper hover:border-saffron hover:text-saffron active:translate-y-px disabled:opacity-40',
    ghost:
      'text-ash hover:text-paper hover:bg-white/5 disabled:opacity-40',
  }

  return (
    <button
      disabled={disabled || isLoading}
      className={`relative inline-flex items-center justify-center gap-2 rounded-xl transition-all duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-saffron cursor-pointer disabled:cursor-not-allowed ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <>
          <svg
            className="h-4 w-4 animate-spin text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>{loadingText || children}</span>
        </>
      ) : (
        children
      )}
    </button>
  )
}
