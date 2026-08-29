import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

const variants: Record<Variant, string> = {
  primary:
    'bg-accent text-white hover:bg-teal-800 disabled:bg-teal-300 shadow-sm',
  secondary:
    'bg-panel text-ink border border-line hover:bg-surface disabled:opacity-50',
  ghost: 'bg-transparent text-muted hover:bg-surface hover:text-ink',
  danger:
    'bg-danger text-white hover:bg-red-800 disabled:bg-red-300 shadow-sm',
}

const sizes: Record<Size, string> = {
  sm: 'px-2.5 py-1.5 text-sm gap-1',
  md: 'px-3.5 py-2 text-sm gap-1.5',
}

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'size'> {
  variant?: Variant
  size?: Size
  children: ReactNode
  className?: string
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
