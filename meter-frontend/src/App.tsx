import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { AuthProvider } from '@/contexts/AuthContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ToastProvider } from '@/components/ToastProvider'
import { PWAStatus } from '@/components/PWAStatus'
import { RealtimeSync } from '@/components/RealtimeSync'
import { ChartSkeleton, KPISkeletonGrid, TableSkeleton } from '@/components/Skeleton'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { getApiErrorMessage, getApiErrorStatus } from '@/lib/errors'
import { notify } from '@/lib/toast'
import { loadPage } from '@/lib/routePrefetch'

const LoginPage = lazy(() => loadPage('login'))
const DashboardPage = lazy(() => loadPage('dashboard'))
const BuildingsPage = lazy(() => loadPage('buildings'))
const BuildingDetailPage = lazy(() => loadPage('buildingDetail'))
const DevicesPage = lazy(() => loadPage('devices'))
const DeviceDetailPage = lazy(() => loadPage('deviceDetail'))
const AlertsPage = lazy(() => loadPage('alerts'))
const FirmwarePage = lazy(() => loadPage('firmware'))
const UsersPage = lazy(() => loadPage('users'))
const AuditPage = lazy(() => loadPage('audit'))
const SettingsPage = lazy(() => loadPage('settings'))
const ChatPage = lazy(() => loadPage('chat'))
const AnalyticsPage = lazy(() => loadPage('analytics'))
const DisplayPage = lazy(() => import('@/pages/DisplayPage'))

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      const status = getApiErrorStatus(error)
      if (status === 401 || status === 403 || (status && status >= 500)) return
      notify({ type: 'error', title: 'Maʼlumotlarni yuklashda xatolik', message: getApiErrorMessage(error) })
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

function PageFallback() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-4 sm:p-6 lg:p-8">
      <div className="mx-auto w-full max-w-[1600px] space-y-5">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-3">
            <div className="skeleton h-5 w-32" />
            <div className="skeleton h-8 w-56 max-w-[70vw]" />
          </div>
          <div className="skeleton h-10 w-28 rounded-xl" />
        </div>
        <KPISkeletonGrid />
        <ChartSkeleton />
        <TableSkeleton rows={5} />
      </div>
    </div>
  )
}

function RouteBoundary({ children }: { children: ReactNode }) {
  const location = useLocation()
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>
}

export default function App() {
  const [updateAvailable, setUpdateAvailable] = useState(false)

  useEffect(() => {
    const handleUpdateReady = () => setUpdateAvailable(true)
    window.addEventListener('meter:pwa-update-ready', handleUpdateReady)
    return () => window.removeEventListener('meter:pwa-update-ready', handleUpdateReady)
  }, [])

  return (
    <ThemeProvider>
      <ToastProvider>
        <PWAStatus
          updateAvailable={updateAvailable}
          onUpdate={() => window.dispatchEvent(new CustomEvent('meter:pwa-update-apply'))}
        />
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RealtimeSync />
            <BrowserRouter>
              <RouteBoundary>
                <Suspense fallback={<PageFallback />}>
                  <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
                    <Route path="/buildings" element={<ProtectedRoute><BuildingsPage /></ProtectedRoute>} />
                    <Route path="/buildings/:id" element={<ProtectedRoute><BuildingDetailPage /></ProtectedRoute>} />
                    <Route path="/devices" element={<ProtectedRoute><DevicesPage /></ProtectedRoute>} />
                    <Route path="/devices/:id" element={<ProtectedRoute><DeviceDetailPage /></ProtectedRoute>} />
                    <Route path="/alerts" element={<ProtectedRoute><AlertsPage /></ProtectedRoute>} />
                    <Route path="/firmware" element={<ProtectedRoute><FirmwarePage /></ProtectedRoute>} />
                    <Route path="/users" element={<ProtectedRoute requireAdmin><UsersPage /></ProtectedRoute>} />
                    <Route path="/audit" element={<ProtectedRoute requireAdmin><AuditPage /></ProtectedRoute>} />
                    <Route path="/settings" element={<ProtectedRoute requireAdmin><SettingsPage /></ProtectedRoute>} />
                    <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
                    <Route path="/analytics" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
                    <Route path="/display" element={<DisplayPage />} />
                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                  </Routes>
                </Suspense>
              </RouteBoundary>
            </BrowserRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
