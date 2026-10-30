import type { InputHTMLAttributes } from 'react'

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
}

export function Field({ label, hint, id, className = '', ...props }: FieldProps) {
  const inputId = id || `f-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <div>
      <label htmlFor={inputId} className="block font-mono text-[11px] font-medium tracking-wide text-ash">
        {label.toUpperCase()}
        {props.required && ' *'}
      </label>
      <input
        id={inputId}
        {...props}
        className={`mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-2.5 text-sm text-paper placeholder:text-ash/50 focus:border-saffron focus:outline-none ${className}`}
      />
      {hint && <p className="mt-1 text-[11px] text-ash/80">{hint}</p>}
    </div>
  )
}
