import type { InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  className?: string
}

export function Input({
  label,
  error,
  id,
  className = '',
  ...props
}: InputProps) {
  const inputId =
    id ??
    (typeof label === 'string'
      ? label.toLowerCase().replace(/\s+/g, '-')
      : undefined)

  return (
    <label className="flex flex-col gap-1.5 text-left">
      {label ? (
        <span className="text-sm font-medium text-ink">{label}</span>
      ) : null}
      <input
        id={inputId}
        className={`w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted/70 shadow-sm transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 ${error ? 'border-danger' : ''} ${className}`}
        {...props}
      />
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </label>
  )
}
