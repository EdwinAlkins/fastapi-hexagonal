import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react'
import type { ReactNode } from 'react'
import { Button } from './Button'

interface ModalProps {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  busy?: boolean
  onClose: () => void
  onConfirm: () => void
}

export function Modal({
  open,
  title,
  children,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  danger = false,
  busy = false,
  onClose,
  onConfirm,
}: ModalProps) {
  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop className="fixed inset-0 bg-ink/40 backdrop-blur-[1px]" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel className="flex max-h-[90vh] w-full max-w-md flex-col rounded-xl border border-line bg-panel p-5 shadow-xl">
          <DialogTitle className="font-display text-lg text-ink">
            {title}
          </DialogTitle>
          <div className="mt-2 min-h-0 flex-1 overflow-y-auto text-sm text-muted">
            {children}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              {cancelLabel}
            </Button>
            <Button
              variant={danger ? 'danger' : 'primary'}
              onClick={onConfirm}
              disabled={busy}
            >
              {confirmLabel}
            </Button>
          </div>
        </DialogPanel>
      </div>
    </Dialog>
  )
}
