import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { TaskStatus } from '../api/types'
import { TaskCard } from '../components/TaskCard'
import { UserNameEditor } from '../components/UserNameEditor'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useCurrentUser } from '../contexts/CurrentUser'
import {
  useCompleteTask,
  useCreateTask,
  useDeleteTask,
  useRenameTask,
  useShareTask,
  useStartTask,
  useTasks,
} from '../hooks/useTasks'
import { useRenameUser, useUser } from '../hooks/useUsers'

const PAGE_SIZE = 10

const filters: { value: TaskStatus | 'all'; label: string; className: string }[] = [
  {
    value: 'all',
    label: 'Toutes',
    className: 'bg-slate-100 text-ink ring-slate-200',
  },
  {
    value: 'todo',
    label: 'À faire',
    className: 'bg-amber-100 text-todo ring-amber-200',
  },
  {
    value: 'in_progress',
    label: 'En cours',
    className: 'bg-sky-100 text-progress ring-sky-200',
  },
  {
    value: 'done',
    label: 'Terminées',
    className: 'bg-emerald-100 text-done ring-emerald-200',
  },
]

export function DashboardPage() {
  const { userId = '' } = useParams()
  const { currentUser, setCurrentUser } = useCurrentUser()
  const userQuery = useUser(userId)

  const [page, setPage] = useState(0)
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [descOpen, setDescOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const offset = page * PAGE_SIZE
  const tasksQuery = useTasks(userId, PAGE_SIZE, offset)
  const createTask = useCreateTask(userId)
  const renameTask = useRenameTask(userId)
  const renameUser = useRenameUser()
  const startTask = useStartTask(userId)
  const completeTask = useCompleteTask(userId)
  const deleteTask = useDeleteTask(userId)
  const shareTask = useShareTask()

  useEffect(() => {
    if (userQuery.data) setCurrentUser(userQuery.data)
  }, [userQuery.data, setCurrentUser])

  useEffect(() => {
    setPage(0)
  }, [statusFilter, userId])

  const filteredTasks = useMemo(() => {
    const tasks = tasksQuery.data ?? []
    if (statusFilter === 'all') return tasks
    return tasks.filter((task) => task.status === statusFilter)
  }, [tasksQuery.data, statusFilter])

  const hasPrev = page > 0
  const hasNext = (tasksQuery.data?.length ?? 0) >= PAGE_SIZE
  const busy =
    createTask.isPending ||
    renameTask.isPending ||
    startTask.isPending ||
    completeTask.isPending ||
    deleteTask.isPending

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    const trimmed = title.trim()
    if (!trimmed) {
      setFormError('Le titre est requis.')
      return
    }
    try {
      await createTask.mutateAsync({
        title: trimmed,
        description: description.trim() || null,
      })
      setTitle('')
      setDescription('')
      setDescOpen(false)
      setPage(0)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Création impossible')
    }
  }

  const pageUser =
    userQuery.data ?? (currentUser?.id === userId ? currentUser : null)
  const displayName = pageUser?.name

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-muted">
          <Link to="/" className="text-accent no-underline hover:underline">
            Utilisateurs
          </Link>
          <span className="mx-1.5">/</span>
          Tableau de bord
        </p>
        <h1 className="mt-1 text-3xl text-ink sm:text-4xl">
          {displayName ? `Tâches de ${displayName}` : 'Tâches'}
        </h1>
        {pageUser ? (
          <div className="mt-2">
            <UserNameEditor
              user={pageUser}
              busy={renameUser.isPending}
              onRename={(name) => renameUser.mutateAsync({ userId, name })}
            />
          </div>
        ) : null}
      </div>

      {userQuery.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-danger">
          Utilisateur introuvable.
        </div>
      ) : null}

      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-line bg-panel p-4 shadow-sm"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Input
              label="Nouvelle tâche"
              value={title}
              onChange={(e) => setTitle(e.currentTarget.value)}
              placeholder="Titre de la tâche"
              required
            />
          </div>
          <Button type="submit" disabled={createTask.isPending || !userId}>
            {createTask.isPending ? 'Ajout…' : 'Ajouter'}
          </Button>
        </div>

        <button
          type="button"
          className="mt-3 inline-flex items-center gap-1 text-sm text-muted transition hover:text-ink"
          onClick={() => setDescOpen((open) => !open)}
        >
          <Chevron open={descOpen} />
          Description optionnelle
        </button>

        {descOpen ? (
          <textarea
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
            rows={3}
            placeholder="Détails…"
            className="mt-2 w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm text-ink shadow-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        ) : null}

        {formError ? <p className="mt-2 text-sm text-danger">{formError}</p> : null}
      </form>

      <div className="flex flex-wrap gap-2">
        {filters.map((filter) => {
          const active = statusFilter === filter.value
          return (
            <button
              key={filter.value}
              type="button"
              onClick={() => setStatusFilter(filter.value)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ring-1 ring-inset transition ${filter.className} ${active ? 'ring-2 ring-offset-1 ring-offset-surface' : 'opacity-70 hover:opacity-100'}`}
            >
              {filter.label}
            </button>
          )
        })}
      </div>

      {tasksQuery.isLoading ? (
        <p className="text-muted">Chargement des tâches…</p>
      ) : null}

      {tasksQuery.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-danger">
          {tasksQuery.error instanceof Error
            ? tasksQuery.error.message
            : 'Erreur de chargement'}
        </div>
      ) : null}

      {!tasksQuery.isLoading && filteredTasks.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line bg-panel/60 px-4 py-10 text-center text-muted">
          Aucune tâche{statusFilter !== 'all' ? ' pour ce filtre' : ''}.
        </p>
      ) : null}

      <div className="grid gap-3">
        {filteredTasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            busy={busy}
            shareBusy={shareTask.isPending}
            onRename={(taskId, nextTitle) =>
              renameTask.mutateAsync({ taskId, title: nextTitle })
            }
            onStart={(taskId) => startTask.mutateAsync(taskId)}
            onComplete={(taskId) => completeTask.mutateAsync(taskId)}
            onDelete={(taskId) => deleteTask.mutateAsync(taskId)}
            onShare={(taskId, payload) =>
              shareTask.mutateAsync({ taskId, payload })
            }
          />
        ))}
      </div>

      <div className="flex items-center justify-between gap-3">
        <Button
          variant="secondary"
          size="sm"
          disabled={!hasPrev || tasksQuery.isFetching}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
        >
          ← Précédent
        </Button>
        <span className="text-sm text-muted">Page {page + 1}</span>
        <Button
          variant="secondary"
          size="sm"
          disabled={!hasNext || tasksQuery.isFetching}
          onClick={() => setPage((p) => p + 1)}
        >
          Suivant →
        </Button>
      </div>
    </div>
  )
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className={`h-4 w-4 transition ${open ? 'rotate-90' : ''}`}
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M7.2 4.8a1 1 0 011.4 0l5 5a1 1 0 010 1.4l-5 5a1 1 0 11-1.4-1.4L11.6 10 7.2 6.2a1 1 0 010-1.4z"
        clipRule="evenodd"
      />
    </svg>
  )
}
