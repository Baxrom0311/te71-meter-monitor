import { AlertTriangle, X } from 'lucide-react'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  tone?: 'default' | 'danger'
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Tasdiqlash',
  tone = 'default',
  pending = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  const danger = tone === 'danger'

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="glass-card rounded-xl max-w-md w-full p-5 shadow-2xl animate-modal-pop">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={`p-2 rounded-lg border ${danger ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-blue-500/10 text-blue-500 border-blue-500/20'}`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-gray-950 dark:text-gray-100">{title}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{message}</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={pending}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={pending}
            className="px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-250 text-sm font-semibold transition disabled:opacity-50"
          >
            Bekor
          </button>
          <button
            onClick={onConfirm}
            disabled={pending}
            className={`px-4 py-2 rounded-lg text-white text-sm font-bold transition disabled:opacity-50 ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}
          >
            {pending ? 'Bajarilmoqda...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
