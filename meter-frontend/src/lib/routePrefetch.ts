type PageKey =
  | 'login'
  | 'dashboard'
  | 'buildings'
  | 'buildingDetail'
  | 'devices'
  | 'deviceDetail'
  | 'alerts'
  | 'firmware'
  | 'users'
  | 'audit'
  | 'settings'
  | 'chat'
  | 'analytics'

const pageLoaders = {
  login: () => import('@/pages/LoginPage'),
  dashboard: () => import('@/pages/DashboardPage'),
  buildings: () => import('@/pages/BuildingsPage'),
  buildingDetail: () => import('@/pages/BuildingDetailPage'),
  devices: () => import('@/pages/DevicesPage'),
  deviceDetail: () => import('@/pages/DeviceDetailPage'),
  alerts: () => import('@/pages/AlertsPage'),
  firmware: () => import('@/pages/FirmwarePage'),
  users: () => import('@/pages/UsersPage'),
  audit: () => import('@/pages/AuditPage'),
  settings: () => import('@/pages/SettingsPage'),
  chat: () => import('@/pages/ChatPage'),
  analytics: () => import('@/pages/AnalyticsPage'),
} satisfies Record<PageKey, () => Promise<{ default: ComponentType }>>

const preloaded = new Set<PageKey>()

export function loadPage(key: PageKey) {
  return pageLoaders[key]()
}

function routeToPageKey(path: string): PageKey {
  if (path === '/login') return 'login'
  if (path === '/dashboard' || path === '/') return 'dashboard'
  if (path.startsWith('/buildings/')) return 'buildingDetail'
  if (path === '/buildings') return 'buildings'
  if (path.startsWith('/devices/')) return 'deviceDetail'
  if (path === '/devices') return 'devices'
  if (path === '/alerts') return 'alerts'
  if (path === '/firmware') return 'firmware'
  if (path === '/users') return 'users'
  if (path === '/audit') return 'audit'
  if (path === '/settings') return 'settings'
  if (path === '/chat') return 'chat'
  if (path === '/analytics') return 'analytics'
  return 'dashboard'
}

export function preloadRoute(path: string) {
  const key = routeToPageKey(path)
  if (preloaded.has(key)) return
  preloaded.add(key)
  void pageLoaders[key]().catch(() => {
    preloaded.delete(key)
  })
}
import type { ComponentType } from 'react'
