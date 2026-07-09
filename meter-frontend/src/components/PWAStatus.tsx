import { useEffect, useState } from 'react'
import { RefreshCw, ServerCrash, WifiOff } from 'lucide-react'
import { useWebSocketStatus } from '@/lib/websocket'

interface PWAStatusProps {
  onUpdate?: () => void
  updateAvailable?: boolean
}

export function PWAStatus({ onUpdate, updateAvailable = false }: PWAStatusProps) {
  const [isOnline, setIsOnline] = useState(() => navigator.onLine)
  const [lastSyncedAt, setLastSyncedAt] = useState(() => new Date())
  const wsStatus = useWebSocketStatus()
  const realtimeProblem = isOnline && (wsStatus === 'reconnecting' || wsStatus === 'failed')

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      setLastSyncedAt(new Date())
    }
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  if (isOnline && !updateAvailable && !realtimeProblem) return null

  const title = !isOnline ? 'Offline rejim' : updateAvailable ? 'Yangi versiya tayyor' : 'Real-time kanal uzildi'
  const message = !isOnline
    ? `Internet uzildi. Oxirgi sinxron: ${lastSyncedAt.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })}`
    : updateAvailable
      ? 'Ilovani yangilash uchun sahifani qayta yuklang.'
      : wsStatus === 'failed'
        ? 'Server WebSocket kanaliga ulanib bo‘lmadi. Maʼlumotlar fallback refresh orqali yangilanadi.'
        : 'Server bilan real-time kanal qayta ulanmoqda.'

  return (
    <div className="fixed inset-x-3 top-3 z-[70] mx-auto max-w-3xl">
      <div className="glass-card rounded-xl px-4 py-3 shadow-2xl border border-blue-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          {!isOnline ? (
            <WifiOff className="w-5 h-5 text-yellow-500 shrink-0 mt-0.5" />
          ) : realtimeProblem ? (
            <ServerCrash className="w-5 h-5 text-orange-500 shrink-0 mt-0.5" />
          ) : (
            <RefreshCw className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
          )}
          <div>
            <p className="text-sm font-bold text-gray-950 dark:text-gray-100">{title}</p>
            <p className="text-xs text-gray-600 dark:text-gray-400">{message}</p>
          </div>
        </div>
        {updateAvailable && onUpdate && (
          <button
            onClick={onUpdate}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Yangilash
          </button>
        )}
      </div>
    </div>
  )
}
