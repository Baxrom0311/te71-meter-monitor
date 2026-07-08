import { ReactNode, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import clsx from 'clsx'
import { TOAST_EVENT, ToastPayload, ToastType } from '@/lib/toast'

interface ToastItem extends Required<Omit<ToastPayload, 'message'>> {
  id: number
  message?: string
}

const styles: Record<ToastType, string> = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-500',
  error: 'border-red-500/30 bg-red-500/10 text-red-500',
  warning: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-500',
  info: 'border-blue-500/30 bg-blue-500/10 text-blue-500',
}

const icons: Record<ToastType, ReactNode> = {
  success: <CheckCircle2 className="w-5 h-5" />,
  error: <XCircle className="w-5 h-5" />,
  warning: <AlertTriangle className="w-5 h-5" />,
  info: <Info className="w-5 h-5" />,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  useEffect(() => {
    const push = (payload: ToastPayload) => {
      const item: ToastItem = {
        id: Date.now() + Math.random(),
        type: payload.type ?? 'info',
        title: payload.title,
        message: payload.message,
        durationMs: payload.durationMs ?? 4500,
      }
      setItems((current) => [item, ...current].slice(0, 4))
      window.setTimeout(() => {
        setItems((current) => current.filter((toast) => toast.id !== item.id))
      }, item.durationMs)
    }

    const pending = window.sessionStorage.getItem('meter-toast')
    if (pending) {
      window.sessionStorage.removeItem('meter-toast')
      try {
        push(JSON.parse(pending))
      } catch {
        push({ type: 'info', title: pending })
      }
    }

    const listener = (event: Event) => push((event as CustomEvent<ToastPayload>).detail)
    window.addEventListener(TOAST_EVENT, listener)
    return () => window.removeEventListener(TOAST_EVENT, listener)
  }, [])

  return (
    <>
      {children}
      <div className="fixed right-4 top-4 z-[100] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-3 pointer-events-none">
        {items.map((item) => (
          <div
            key={item.id}
            className="toast-card pointer-events-auto rounded-xl border bg-white/90 dark:bg-gray-950/90 backdrop-blur-xl shadow-2xl p-4 animate-toast-in"
          >
            <div className="flex gap-3">
              <div className={clsx('h-10 w-10 rounded-lg border flex items-center justify-center shrink-0', styles[item.type])}>
                {icons[item.type]}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-gray-950 dark:text-gray-100">{item.title}</p>
                {item.message && <p className="mt-1 text-xs leading-5 text-gray-600 dark:text-gray-400">{item.message}</p>}
              </div>
              <button
                onClick={() => setItems((current) => current.filter((toast) => toast.id !== item.id))}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition"
                aria-label="Yopish"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
