import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ShareTaskPayload, Task, TaskStatus } from '../api/types'
import { ShareTaskModal } from './ShareTaskModal'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { Modal } from './ui/Modal'

const statusStyles: Record<TaskStatus, string> = {
  todo: 'bg-amber-50 text-todo ring-amber-200',
  in_progress: 'bg-sky-50 text-progress ring-sky-200',
  done: 'bg-emerald-50 text-done ring-emerald-200',
}

const statusLabels: Record<TaskStatus, string> = {
  todo: 'À faire',
  in_progress: 'En cours',
  done: 'Terminée',
}

interface TaskCardProps {
  task: Task
  busy?: boolean
  shareBusy?: boolean
  onRename: (taskId: string, title: string) => Promise<unknown>
  onStart: (taskId: string) => Promise<unknown>
  onComplete: (taskId: string) => Promise<unknown>
  onDelete: (taskId: string) => Promise<unknown>
  onShare: (taskId: string, payload: ShareTaskPayload) => Promise<unknown>
}

export function TaskCard({
  task,
  busy = false,
  shareBusy = false,
  onRename,
  onStart,
  onComplete,
  onDelete,
  onShare,
}: TaskCardProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(task.title)
  const [pendingAction, setPendingAction] = useState<'start' | 'complete' | null>(
    null,
  )
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(task.title)
  }, [task.title])

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  async function commitRename() {
    const next = draft.trim()
    if (!next || next === task.title) {
      setDraft(task.title)
      setEditing(false)
      return
    }
    await onRename(task.id, next)
    setEditing(false)
  }

  async function confirmAction() {
    if (pendingAction === 'start') await onStart(task.id)
    if (pendingAction === 'complete') await onComplete(task.id)
    setPendingAction(null)
  }

  return (
    <>
      <Card className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            {editing ? (
              <input
                ref={inputRef}
                value={draft}
                onChange={(e: FormEvent<HTMLInputElement>) =>
                  setDraft((e.target as HTMLInputElement).value)
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void commitRename()
                  if (e.key === 'Escape') {
                    setDraft(task.title)
                    setEditing(false)
                  }
                }}
                onBlur={() => void commitRename()}
                className="w-full rounded-md border border-accent bg-panel px-2 py-1 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
                disabled={busy}
              />
            ) : (
              <h3
                className="cursor-text text-base font-medium text-ink"
                onDblClick={() => setEditing(true)}
                title="Double-clic pour renommer"
              >
                {task.title}
              </h3>
            )}
            {task.description ? (
              <p className="mt-1 text-sm text-muted">{task.description}</p>
            ) : null}
          </div>
          <span
            className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${statusStyles[task.status]}`}
          >
            {statusLabels[task.status]}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!editing ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditing(true)}
              disabled={busy}
            >
              Éditer
            </Button>
          ) : null}

          {pendingAction ? (
            <>
              <Button size="sm" onClick={() => void confirmAction()} disabled={busy}>
                Confirmer
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPendingAction(null)}
                disabled={busy}
              >
                Annuler
              </Button>
            </>
          ) : (
            <>
              {task.status === 'todo' ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPendingAction('start')}
                  disabled={busy}
                  title="Démarrer"
                >
                  <PlayIcon />
                  Démarrer
                </Button>
              ) : null}

              {task.status !== 'done' ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPendingAction('complete')}
                  disabled={busy}
                  title="Terminer"
                >
                  <CheckIcon />
                  Terminer
                </Button>
              ) : null}
            </>
          )}

          <Button
            variant="secondary"
            size="sm"
            className="ml-auto"
            onClick={() => setShareOpen(true)}
            disabled={busy || shareBusy}
            title="Partager"
          >
            <ShareIcon />
            Partager
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-danger hover:bg-red-50"
            onClick={() => setDeleteOpen(true)}
            disabled={busy}
            title="Supprimer"
          >
            <TrashIcon />
          </Button>
        </div>
      </Card>

      <Modal
        open={deleteOpen}
        title="Supprimer la tâche"
        danger
        busy={busy}
        confirmLabel="Supprimer"
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => {
          void onDelete(task.id).then(() => setDeleteOpen(false))
        }}
      >
        <p>
          Supprimer « <strong className="text-ink">{task.title}</strong> » ? Cette
          action est définitive.
        </p>
      </Modal>

      <ShareTaskModal
        open={shareOpen}
        task={task}
        busy={shareBusy}
        onClose={() => setShareOpen(false)}
        onShare={(payload) => onShare(task.id, payload)}
      />
    </>
  )
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M6.5 4.5v11l9-5.5-9-5.5z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0l-3.5-3.5a1 1 0 011.4-1.4L8.5 12l6.8-6.7a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  )
}

function ShareIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M13 4.5a2.5 2.5 0 11.7 1.71l-5.12 2.56a2.5 2.5 0 010 1.46l5.12 2.56a2.5 2.5 0 11-.7 1.32l-5.12-2.56a2.5 2.5 0 110-4.1l5.12-2.56A2.5 2.5 0 0113 4.5z" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M7 3a1 1 0 011-1h4a1 1 0 011 1v1h4a1 1 0 110 2h-1v10a2 2 0 01-2 2H6a2 2 0 01-2-2V6H3a1 1 0 110-2h4V3zm2 1v0h2V4H9zm-3 3v9h8V7H6z" />
    </svg>
  )
}
