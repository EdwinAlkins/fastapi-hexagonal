import { useEffect, useRef, useState } from 'react'
import type { User } from '../api/types'
import { Button } from './ui/Button'

interface UserNameEditorProps {
  user: User
  busy?: boolean
  onRename: (name: string) => Promise<unknown>
}

/** Renomme un utilisateur (édition inline). Miroir de l'édition du titre d'une
 *  tâche : voir `TaskCard`. */
export function UserNameEditor({ user, busy = false, onRename }: UserNameEditorProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(user.name)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(user.name)
  }, [user.name])

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  function cancel() {
    setDraft(user.name)
    setError(null)
    setEditing(false)
  }

  async function commit() {
    const next = draft.trim()
    if (!next || next === user.name) {
      cancel()
      return
    }
    try {
      await onRename(next)
      setError(null)
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Renommage impossible')
    }
  }

  if (!editing) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted">
        <span>
          Utilisateur : <span className="font-medium text-ink">{user.name}</span>
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setEditing(true)}
          disabled={busy}
        >
          Renommer
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void commit()
            if (e.key === 'Escape') cancel()
          }}
          className="rounded-md border border-accent bg-panel px-2 py-1 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
          disabled={busy}
          aria-label="Nom de l'utilisateur"
        />
        <Button size="sm" onClick={() => void commit()} disabled={busy}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
        <Button variant="ghost" size="sm" onClick={cancel} disabled={busy}>
          Annuler
        </Button>
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </div>
  )
}
