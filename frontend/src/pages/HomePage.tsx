import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { User } from '../api/types'
import { UserCard } from '../components/UserCard'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useCurrentUser } from '../contexts/CurrentUser'
import { useCreateUser, useUsers } from '../hooks/useUsers'

export function HomePage() {
  const navigate = useNavigate()
  const { setCurrentUser } = useCurrentUser()
  const { data: users, isLoading, isError, error, refetch } = useUsers()
  const createUser = useCreateUser()

  const [formOpen, setFormOpen] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const [exportState, setExportState] = useState<'idle' | 'running' | 'error'>('idle')
  const [exported, setExported] = useState(0)

  /**
   * Export global : on consomme le flux NDJSON, puis on propose le fichier.
   *
   * Le comptage préalable n'est pas décoratif : il permet d'afficher une
   * progression réelle, ce que le streaming rend possible et qu'un `await
   * response.json()` interdirait.
   */
  async function handleExport() {
    setExportState('running')
    setExported(0)
    try {
      const { count } = await api.countExportableTasks()
      const items = await api.exportTasks(setExported)

      if (items.length !== count) {
        // Le statut HTTP est parti avec le premier octet : une coupure en cours
        // de flux ne se voit que sur le nombre de lignes reçues.
        throw new Error(`export incomplet : ${items.length} lignes sur ${count}`)
      }

      const blob = new Blob([JSON.stringify(items, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `taches-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      setExportState('idle')
    } catch {
      setExportState('error')
    }
  }

  function selectUser(user: User) {
    setCurrentUser(user)
    void navigate(`/users/${user.id}/tasks`)
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    const trimmedName = name.trim()
    const trimmedEmail = email.trim()
    if (!trimmedName || !trimmedEmail) {
      setFormError('Nom et email sont requis.')
      return
    }

    try {
      const user = await createUser.mutateAsync({
        name: trimmedName,
        email: trimmedEmail,
      })
      setName('')
      setEmail('')
      setFormOpen(false)
      selectUser(user)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Création impossible')
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl text-ink sm:text-4xl">Utilisateurs</h1>
          <p className="mt-1 text-muted">
            Sélectionnez un utilisateur pour ouvrir son tableau de bord.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => void handleExport()}
            disabled={exportState === 'running'}
            title="Télécharge toutes les tâches avec leur propriétaire"
          >
            {exportState === 'running'
              ? `Export… ${exported}`
              : exportState === 'error'
                ? 'Export échoué — réessayer'
                : 'Exporter'}
          </Button>
          <Button onClick={() => setFormOpen((open) => !open)}>
            {formOpen ? 'Fermer' : 'Nouvel utilisateur'}
          </Button>
        </div>
      </div>

      {formOpen ? (
        <form
          onSubmit={handleCreate}
          className="grid gap-3 rounded-xl border border-line bg-panel p-4 shadow-sm sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        >
          <Input
            label="Nom"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            placeholder="Ada Lovelace"
            required
          />
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
            placeholder="ada@example.com"
            required
          />
          <Button type="submit" disabled={createUser.isPending}>
            {createUser.isPending ? 'Création…' : 'Créer'}
          </Button>
          {formError ? (
            <p className="text-sm text-danger sm:col-span-3">{formError}</p>
          ) : null}
        </form>
      ) : null}

      {isLoading ? (
        <p className="text-muted">Chargement des utilisateurs…</p>
      ) : null}

      {isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-danger">
          <p>{error instanceof Error ? error.message : 'Erreur de chargement'}</p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => void refetch()}
          >
            Réessayer
          </Button>
        </div>
      ) : null}

      {!isLoading && !isError && users?.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line bg-panel/60 px-4 py-10 text-center text-muted">
          Aucun utilisateur pour l’instant. Créez-en un pour commencer.
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {users?.map((user) => (
          <UserCard key={user.id} user={user} onSelect={selectUser} />
        ))}
      </div>
    </div>
  )
}
