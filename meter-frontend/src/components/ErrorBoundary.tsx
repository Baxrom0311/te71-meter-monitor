import React, { ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { isChunkLoadError } from '@/lib/appReload'

interface Props {
  children: ReactNode
  resetKey?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error) {
    if (isChunkLoadError(error)) {
      this.setState({ hasError: false, error: null })
      return
    }
    console.error('[ErrorBoundary]', error)
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null })
    }
  }

  render() {
    if (this.state.hasError && !isChunkLoadError(this.state.error)) {
      const message = this.state.error?.message ?? "Noma'lum xatolik"
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-6">
          <div className="glass-card w-full max-w-md rounded-2xl p-8 shadow-2xl text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
              <AlertTriangle className="h-7 w-7" />
            </div>
            <h1 className="text-xl font-black text-gray-950 dark:text-gray-100">Xatolik yuz berdi</h1>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{message}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 transition"
            >
              <RefreshCw className="h-4 w-4" /> Qayta urinish
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
