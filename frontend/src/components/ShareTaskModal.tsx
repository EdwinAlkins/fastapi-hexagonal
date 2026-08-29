import {
  Listbox,
  ListboxButton,
  ListboxLabel,
  ListboxOption,
  ListboxOptions,
} from '@headlessui/react'
import { useEffect, useMemo, useState } from 'react'
import type { ShareTaskPayload, Task, User } from '../api/types'
import { useUsers } from '../hooks/useUsers'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

interface ShareTaskModalProps {
  open: boolean
  task: Task
  busy?: boolean
  onClose: () => void
  onShare: (payload: ShareTaskPayload) => Promise<unknown>
}

/**
 * Partage d'une tâche par e-mail : sélection multi-utilisateurs + sujet / message.
 */
export function ShareTaskModal({
  open,
  task,
  busy = false,
  onClose,
  onShare,
}: ShareTaskModalProps) {
  const usersQuery = useUsers()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recipients = useMemo(
    () => (usersQuery.data ?? []).filter((user) => user.id !== task.owner_id),
    [usersQuery.data, task.owner_id],
  )

  const selectedUsers = useMemo(
    () => recipients.filter((user) => selectedIds.includes(user.id)),
    [recipients, selectedIds],
  )

  useEffect(() => {
    if (!open) return
    setSelectedIds([])
    setSubject(`Partage : ${task.title}`)
    setBody('')
    setError(null)
  }, [open, task.title])

  function handleClose() {
    setSelectedIds([])
    setSubject('')
    setBody('')
    setError(null)
    onClose()
  }

  function handleSelectionChange(users: User[]) {
    setSelectedIds(users.map((user) => user.id))
    if (error) setError(null)
  }

  async function handleSend() {
    if (selectedIds.length === 0) {
      setError('Sélectionnez au moins un destinataire.')
      return
    }
    const trimmedSubject = subject.trim()
    if (!trimmedSubject) {
      setError('Le sujet est requis.')
      return
    }
    const trimmedBody = body.trim()
    if (!trimmedBody) {
      setError('Le message est requis.')
      return
    }

    try {
      await onShare({
        user_ids: selectedIds,
        subject: trimmedSubject,
        body: trimmedBody,
      })
      handleClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'envoi")
    }
  }

  const buttonLabel =
    selectedUsers.length === 0
      ? 'Choisir des destinataires…'
      : selectedUsers.length === 1
        ? selectedUsers[0].name
        : `${selectedUsers.length} destinataires sélectionnés`

  return (
    <Modal
      open={open}
      title="Partager la tâche"
      confirmLabel={busy ? 'Envoi…' : 'Envoyer'}
      busy={busy}
      onClose={handleClose}
      onConfirm={() => {
        void handleSend()
      }}
    >
      <div className="flex flex-col gap-3">
        <p>
          Partager « <strong className="text-ink">{task.title}</strong> » par
          e-mail.
        </p>

        {usersQuery.isLoading ? (
          <p className="text-sm text-muted">Chargement des utilisateurs…</p>
        ) : null}

        {usersQuery.isError ? (
          <p className="text-sm text-danger">
            Impossible de charger la liste des utilisateurs.
          </p>
        ) : null}

        {!usersQuery.isLoading && recipients.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line px-3 py-3 text-center text-sm text-muted">
            Aucun autre utilisateur disponible.
          </p>
        ) : null}

        {recipients.length > 0 ? (
          <Listbox
            value={selectedUsers}
            by="id"
            onChange={handleSelectionChange}
            multiple
            disabled={busy}
          >
            <div className="relative flex flex-col gap-1.5">
              <ListboxLabel className="text-sm font-medium text-ink">
                Destinataires
              </ListboxLabel>
              <ListboxButton className="relative w-full rounded-lg border border-line bg-panel px-3 py-2 pr-9 text-left text-sm text-ink shadow-sm transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 data-disabled:opacity-60">
                <span
                  className={`block truncate ${selectedUsers.length === 0 ? 'text-muted/70' : ''}`}
                >
                  {buttonLabel}
                </span>
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-muted">
                  <ChevronIcon />
                </span>
              </ListboxButton>

              <ListboxOptions
                anchor="bottom start"
                className="z-[60] mt-1 max-h-48 w-[var(--button-width)] overflow-auto rounded-lg border border-line bg-panel py-1 shadow-lg outline-none [--anchor-gap:4px] empty:invisible"
              >
                {recipients.map((user) => (
                  <ListboxOption
                    key={user.id}
                    value={user}
                    className="group flex cursor-pointer items-center gap-2 px-3 py-2 text-sm select-none data-focus:bg-surface data-selected:bg-accent-soft"
                  >
                    {({ selected }) => (
                      <>
                        <span
                          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${selected ? 'border-accent bg-accent text-white' : 'border-line bg-panel text-transparent'}`}
                          aria-hidden="true"
                        >
                          ✓
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-ink">
                            {user.name}
                          </span>
                          <span className="block truncate text-xs text-muted">
                            {user.email}
                          </span>
                        </span>
                      </>
                    )}
                  </ListboxOption>
                ))}
              </ListboxOptions>
            </div>
          </Listbox>
        ) : null}

        <Input
          label="Sujet"
          value={subject}
          onChange={(e) => {
            setSubject(e.currentTarget.value)
            if (error) setError(null)
          }}
          placeholder="Sujet du message"
          disabled={busy}
        />

        <label className="flex flex-col gap-1.5 text-left">
          <span className="text-sm font-medium text-ink">Message</span>
          <textarea
            value={body}
            onChange={(e) => {
              setBody(e.currentTarget.value)
              if (error) setError(null)
            }}
            rows={5}
            placeholder="Votre message…"
            disabled={busy}
            className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted/70 shadow-sm transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
          />
        </label>

        {error ? <p className="text-sm text-danger">{error}</p> : null}
      </div>
    </Modal>
  )
}

function ChevronIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M5.2 7.2a1 1 0 011.4 0L10 10.6l3.4-3.4a1 1 0 111.4 1.4l-4.1 4.1a1 1 0 01-1.4 0L5.2 8.6a1 1 0 010-1.4z"
        clipRule="evenodd"
      />
    </svg>
  )
}
