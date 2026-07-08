export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastPayload {
  type?: ToastType
  title: string
  message?: string
  durationMs?: number
}

export const TOAST_EVENT = 'meter:toast'

export function notify(payload: ToastPayload) {
  window.dispatchEvent(new CustomEvent<ToastPayload>(TOAST_EVENT, { detail: payload }))
}

export function notifySuccess(title: string, message?: string) {
  notify({ type: 'success', title, message })
}

export function notifyError(title: string, message?: string) {
  notify({ type: 'error', title, message })
}
