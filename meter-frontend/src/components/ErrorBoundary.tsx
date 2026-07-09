import React, { ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

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
    console.error('[v0] Error caught:', error)
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null })
    }
  }

  private reload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      const message = this.state.error?.message ?? 'Nomaʼlum xatolik'
      const isChunkError = /chunk|import|module|fetch/i.test(message)

      return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-4 sm:p-6 lg:p-8 flex items-center justify-center">
          <div className="glass-card w-full max-w-lg rounded-2xl p-6 sm:p-8 shadow-2xl text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
              <AlertTriangle className="h-7 w-7" />
            </div>
            <h1 className="text-xl font-black text-gray-950 dark:text-gray-100">
              {isChunkError ? 'Ilova yangilangan' : 'Sahifani ochishda xatolik'}
            </h1>
            <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-400">
              {isChunkError
                ? 'Brauzer eski faylni ochmoqchi bo‘ldi. Sahifani yangilasangiz yangi versiya yuklanadi.'
                : message}
            </p>
            <button
              onClick={this.reload}
              className="mt-6 inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 transition"
            >
              <RefreshCw className="h-4 w-4" />
              Yangilash
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
