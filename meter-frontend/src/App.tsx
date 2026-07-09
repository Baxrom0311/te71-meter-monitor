import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { AuthProvider } from '@/contexts/AuthContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ToastProvider } from '@/components/ToastProvider'
import { PWAStatus } from '@/components/PWAStatus'
import { RealtimeSync } from '@/components/RealtimeSync'
import { getApiErrorMessage, getApiErrorStatus } from '@/lib/errors'
import { notify } from '@/lib/toast'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import BuildingsPage from '@/pages/BuildingsPage'
import BuildingDetailPage from '@/pages/BuildingDetailPage'
import DevicesPage from '@/pages/DevicesPage'
import DeviceDetailPage from '@/pages/DeviceDetailPage'
import AlertsPage from '@/pages/AlertsPage'
import FirmwarePage from '@/pages/FirmwarePage'
import UsersPage from '@/pages/UsersPage'
import AuditPage from '@/pages/AuditPage'
import SettingsPage from '@/pages/SettingsPage'
import ChatPage from '@/pages/ChatPage'
import InstallGuidePage from '@/pages/InstallGuidePage'
import AnalyticsPage from '@/pages/AnalyticsPage'

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
                <Route path="/guide" element={<ProtectedRoute><InstallGuidePage /></ProtectedRoute>} />
                <Route path="/analytics" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </BrowserRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
