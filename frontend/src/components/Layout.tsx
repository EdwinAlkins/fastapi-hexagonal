import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useCurrentUser } from '../contexts/CurrentUser'
import { Button } from './ui/Button'

const MAIL_UI_URL = import.meta.env.VITE_MAIL_UI_URL ?? 'http://localhost:8025'
const REDIS_INSIGHT_URL = import.meta.env.VITE_REDIS_INSIGHT_URL ?? 'http://localhost:5540'
const RABBITMQ_INSIGHT_URL = import.meta.env.VITE_RABBITMQ_INSIGHT_URL ?? 'http://localhost:15672'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function Layout({ children }: { children: ReactNode }) {
  const { currentUser } = useCurrentUser()

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b border-line/80 bg-panel/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to="/" className="group flex items-baseline gap-2 no-underline">
            <span className="font-display text-xl text-ink transition group-hover:text-accent">
              Task Manager
            </span>
            <span className="hidden text-xs text-muted sm:inline">POC full-stack</span>
          </Link>

          <div className="flex items-center gap-3">
            {currentUser ? (
              <Link
                to={`/users/${currentUser.id}/tasks`}
                className="flex items-center gap-2 rounded-full border border-line bg-surface px-2 py-1 pr-3 text-sm no-underline transition hover:border-accent"
                title="Tableau de bord"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white">
                  {initials(currentUser.name)}
                </span>
                <span className="max-w-[10rem] truncate text-ink">
                  {currentUser.name}
                </span>
              </Link>
            ) : null}

            <Button
              variant="secondary"
              size="sm"
              onClick={() => window.open(MAIL_UI_URL, '_blank', 'noopener,noreferrer')}
            >
              Boîte mail
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => window.open(REDIS_INSIGHT_URL, '_blank', 'noopener,noreferrer')}
            >
              Redis Insight
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => window.open(RABBITMQ_INSIGHT_URL, '_blank', 'noopener,noreferrer')}
            >
              RabbitMQ Insight
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
        {children}
      </main>

      <footer className="border-t border-line/80 py-4 text-center text-xs text-muted">
        API · Preact · Tailwind · Mailpit
      </footer>
    </div>
  )
}
