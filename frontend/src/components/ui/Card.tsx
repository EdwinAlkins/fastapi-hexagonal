import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  className?: string
}

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-line bg-panel p-4 text-left shadow-sm transition ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
