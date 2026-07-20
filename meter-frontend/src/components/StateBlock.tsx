import { AlertCircle, Inbox, Loader2, RefreshCw } from 'lucide-react'

interface StateBlockProps {
  title?: string
  message?: string
  onRetry?: () => void
}

export function LoadingBlock({ title = 'Yuklanmoqda...', message = 'Maʼlumotlar serverdan olinmoqda.' }: StateBlockProps) {
  return (
    <div className="state-block">
      <Loader2 className="w-7 h-7 text-blue-500 animate-spin" />
      <div>
        <p className="font-bold text-gray-950 dark:text-gray-100">{title}</p>
        <p className="text-sm text-gray-600 dark:text-gray-400">{message}</p>
      </div>
    </div>
  )
}

export function EmptyBlock({ title = 'Maʼlumot topilmadi', message = "Hozircha ko'rsatish uchun yozuv yo'q." }: StateBlockProps) {
  return (
    <div className="state-block">
      <Inbox className="w-7 h-7 text-gray-400" />
      <div>
        <p className="font-bold text-gray-950 dark:text-gray-100">{title}</p>
        <p className="text-sm text-gray-600 dark:text-gray-400">{message}</p>
      </div>
    </div>
  )
}

export function ErrorBlock({ title = 'Xatolik yuz berdi', message = "So'rov bajarilmadi.", onRetry }: StateBlockProps) {
  return (
    <div className="state-block border-red-500/25 bg-red-500/5">
      <AlertCircle className="w-7 h-7 text-red-500" />
      <div className="flex-1">
        <p className="font-bold text-gray-950 dark:text-gray-100">{title}</p>
        <p className="text-sm text-gray-600 dark:text-gray-400">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-xs font-bold text-red-500 hover:bg-red-500/15 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Qayta urinish
        </button>
      )}
    </div>
  )
}
