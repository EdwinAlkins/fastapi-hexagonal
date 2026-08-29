import type { User } from '../api/types'
import { Card } from './ui/Card'

interface UserCardProps {
  user: User
  onSelect: (user: User) => void
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function UserCard({ user, onSelect }: UserCardProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(user)}
      className="group w-full cursor-pointer rounded-xl border border-line bg-panel p-0 text-left shadow-sm transition hover:border-accent hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      <Card className="border-0 shadow-none">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent transition group-hover:bg-accent group-hover:text-white">
            {initials(user.name)}
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium text-ink">{user.name}</p>
            <p className="truncate text-sm text-muted">{user.email}</p>
          </div>
        </div>
      </Card>
    </button>
  )
}
