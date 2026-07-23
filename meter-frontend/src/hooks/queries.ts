import { keepPreviousData, useQuery, UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import {
  Summary,
  Building,
  Device,
  Alert,
  AlertRule,
  EnergyAnalytics,
  AuditLogListResponse,
  User,
  Reading,
  DeviceHistoryResponse,
  OtaBatch,
  BuildingsEnergySummaryResponse,
  HourlyUtilityStatsResponse,
  ProvisioningTokenListResponse,
  BackupListResponse,
} from '@/types/api'

const REALTIME_FALLBACK_INTERVAL_MS = 5 * 60 * 1000
const OPERATIONS_FALLBACK_INTERVAL_MS = 60 * 1000

// ─── Query Key Factories ──────────────────────────────────────────────────────
// Hierarchical keys so that invalidating a parent key invalidates all children.
// e.g. invalidateQueries({ queryKey: ['devices'] }) covers 'all', 'list', 'detail', 'latest', 'history'
export const qk = {
  devices:      () => ['devices'] as const,
  devicesAll:   (limit?: number, offset?: number) => ['devices', 'all', limit, offset] as const,
  devicesList:  (p: DevicesListParams) => ['devices', 'list', p.page, p.pageSize, p.q, p.deviceId, p.utilityType, p.online, p.isTestDevice, p.sortBy, p.sortOrder] as const,
  deviceDetail: (id: string) => ['devices', 'detail', id] as const,
  deviceLatest: (id: string) => ['devices', 'latest', id] as const,
  deviceHistory:(id: string, hours: number, page?: number, limit?: number) =>
    page === undefined || limit === undefined
      ? ['devices', 'history', id, hours] as const
      : ['devices', 'history', id, hours, page, limit] as const,

  alerts:       () => ['alerts'] as const,
  alertsAll:    (cleared?: boolean, limit?: number) => ['alerts', 'all', cleared, limit] as const,
  alertsList:   (p: AlertsListParams) => ['alerts', 'list', p.page, p.pageSize, p.cleared, p.kind, p.deviceId] as const,
  alertRules:   () => ['alert-rules'] as const,

  users:        () => ['users'] as const,
  usersAll:     () => ['users', 'all'] as const,
  usersList:    (p: UsersListParams) => ['users', 'list', p.page, p.pageSize, p.q, p.role, p.isActive, p.sortBy, p.sortOrder] as const,

  buildings:    () => ['buildings'] as const,
  buildingsAll: () => ['buildings', 'all'] as const,
  buildingDetail: (id: string) => ['buildings', 'detail', id] as const,

  summary:      () => ['summary'] as const,
  energySummary:(days: number) => ['energy-summary', days] as const,
  hourlyStats:  (hours: number, buildingId?: number, utilityType?: string) => ['hourly-stats', hours, buildingId, utilityType] as const,
  energyAnalytics: (gran: string, from?: number, to?: number, bid?: number) => ['energy-analytics', gran, from, to, bid] as const,
  firmware:     () => ['firmware'] as const,
  otaBatches:   () => ['ota-batches'] as const,
  provisioningTokens: () => ['provisioning-tokens'] as const,
  backups:      () => ['backups'] as const,
  auditLogs:    (limit: number, page: number, filters?: object) => ['audit-logs', limit, page, filters] as const,
}

// Summary
export function useSummary(): UseQueryResult<Summary> {
  return useQuery({
    queryKey: qk.summary(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/summary')
      return data
    },
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
  })
}

export function useEnergySummary(days = 30): UseQueryResult<BuildingsEnergySummaryResponse> {
  return useQuery({
    queryKey: qk.energySummary(days),
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/analytics/energy/summary?days=${days}`)
      return data
    },
  })
}

export function useHourlyStats(
  hours = 24,
  buildingId?: number,
  utilityType?: string,
): UseQueryResult<HourlyUtilityStatsResponse> {
  return useQuery({
    queryKey: qk.hourlyStats(hours, buildingId, utilityType),
    queryFn: async () => {
      const params = new URLSearchParams({
        hours: hours.toString(),
        limit: '1000',
        ...(buildingId && { building_id: buildingId.toString() }),
        ...(utilityType && utilityType !== 'all' && { utility_type: utilityType }),
      })
      const { data } = await apiClient.get(`/api/analytics/hourly?${params}`)
      return data
    },
  })
}

// Energy Analytics
export function useEnergyAnalytics(
  granularity: 'hour' | 'day' | 'month' = 'hour',
  fromTs?: number,
  toTs?: number,
  buildingId?: number,
): UseQueryResult<EnergyAnalytics> {
  return useQuery({
    queryKey: qk.energyAnalytics(granularity, fromTs, toTs, buildingId),
    queryFn: async () => {
      const params = new URLSearchParams({
        granularity,
        ...(fromTs && { from_ts: fromTs.toString() }),
        ...(toTs && { to_ts: toTs.toString() }),
        ...(buildingId && { building_id: buildingId.toString() }),
      })
      const { data } = await apiClient.get(`/api/analytics/energy?${params}`)
      return data
    },
  })
}

// Buildings
export function useBuildings(): UseQueryResult<Building[]> {
  return useQuery({
    queryKey: qk.buildingsAll(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/buildings')
      return data.buildings
    },
  })
}

export function useBuildingById(id: string): UseQueryResult<Building> {
  return useQuery({
    queryKey: qk.buildingDetail(id),
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/buildings/${id}`)
      return data
    },
    enabled: !!id,
  })
}

// Devices
export function useDevices(limit?: number, offset?: number): UseQueryResult<Device[]> {
  return useQuery({
    queryKey: qk.devicesAll(limit, offset),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (limit) params.append('limit', limit.toString())
      if (offset) params.append('offset', offset.toString())
      const { data } = await apiClient.get(`/api/devices?${params}`)
      return data.devices
    },
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
  })
}

export function useDeviceById(id: string): UseQueryResult<Device> {
  return useQuery({
    queryKey: qk.deviceDetail(id),
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/devices/${id}`)
      return data
    },
    enabled: !!id,
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
  })
}

export function useDeviceLatest(id: string): UseQueryResult<Reading> {
  return useQuery({
    queryKey: qk.deviceLatest(id),
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/devices/${id}/latest`)
      return data
    },
    enabled: !!id,
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
  })
}

export function useDeviceHistory(id: string, hours = 24, page = 1, limit = 100): UseQueryResult<DeviceHistoryResponse> {
  return useQuery({
    queryKey: qk.deviceHistory(id, hours, page, limit),
    queryFn: async () => {
      const params = new URLSearchParams({
        hours: hours.toString(),
        page: page.toString(),
        limit: limit.toString(),
      })
      const { data } = await apiClient.get(`/api/devices/${id}/history?${params}`)
      return data
    },
    enabled: !!id,
    placeholderData: keepPreviousData,
  })
}

// Alerts
export function useAlerts(cleared?: boolean, limit?: number): UseQueryResult<Alert[]> {
  return useQuery({
    queryKey: qk.alertsAll(cleared, limit),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (cleared !== undefined) params.append('cleared', cleared.toString())
      if (limit) params.append('limit', limit.toString())
      const { data } = await apiClient.get(`/api/alerts?${params}`)
      return data.alerts
    },
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
  })
}

// Users (Admin)
export function useUsers(): UseQueryResult<User[]> {
  return useQuery({
    queryKey: qk.usersAll(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/auth/users')
      return data.users
    },
  })
}

// Audit Logs (Admin)
export function useAuditLogs(
  limit = 100,
  page = 1,
  filters?: { action?: string; entity_type?: string; username?: string },
): UseQueryResult<AuditLogListResponse> {
  return useQuery({
    queryKey: qk.auditLogs(limit, page, filters),
    queryFn: async () => {
      const params = new URLSearchParams({ limit: limit.toString(), page: page.toString() })
      if (filters?.action) params.append('action', filters.action)
      if (filters?.entity_type) params.append('entity_type', filters.entity_type)
      if (filters?.username) params.append('username', filters.username)
      const { data } = await apiClient.get(`/api/audit-logs?${params}`)
      return data as AuditLogListResponse
    },
  })
}

// Firmware
export function useFirmwareList() {
  return useQuery({
    queryKey: qk.firmware(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/ota/list')
      return data.firmware ?? data
    },
  })
}

export function useOtaBatches(enabled = true): UseQueryResult<OtaBatch[]> {
  return useQuery({
    queryKey: qk.otaBatches(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/ota/batches')
      return data.batches ?? []
    },
    enabled,
    refetchInterval: OPERATIONS_FALLBACK_INTERVAL_MS,
  })
}

// Alert Rules
export function useAlertRules(): UseQueryResult<AlertRule[]> {
  return useQuery({
    queryKey: qk.alertRules(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/alert-rules')
      return data.rules ?? data
    },
  })
}

// ── Server-side paginated list hooks ─────────────────────────────────────────

export interface DevicesListParams {
  page: number
  pageSize: number
  q?: string
  deviceId?: string
  utilityType?: string
  online?: boolean
  isTestDevice?: boolean
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export function useDevicesList(params: DevicesListParams): UseQueryResult<{ devices: Device[]; total: number }> {
  const { page, pageSize, q, deviceId, utilityType, online, isTestDevice, sortBy, sortOrder } = params
  return useQuery({
    queryKey: qk.devicesList(params),
    queryFn: async () => {
      const p = new URLSearchParams()
      p.set('limit', pageSize.toString())
      p.set('offset', ((page - 1) * pageSize).toString())
      if (q) p.set('q', q)
      if (deviceId) p.set('device_id', deviceId)
      if (utilityType) p.set('utility_type', utilityType)
      if (online !== undefined) p.set('online', online.toString())
      if (isTestDevice !== undefined) p.set('is_test_device', isTestDevice.toString())
      if (sortBy) p.set('sort_by', sortBy)
      if (sortOrder) p.set('sort_order', sortOrder)
      const { data } = await apiClient.get(`/api/devices?${p}`)
      return { devices: data.devices as Device[], total: data.total as number }
    },
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
    placeholderData: keepPreviousData,
  })
}

export interface UsersListParams {
  page: number
  pageSize: number
  q?: string
  role?: string
  isActive?: boolean
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export function useUsersList(params: UsersListParams): UseQueryResult<{ users: User[]; total: number }> {
  return useQuery({
    queryKey: qk.usersList(params),
    queryFn: async () => {
      const p = new URLSearchParams()
      p.set('limit', params.pageSize.toString())
      p.set('offset', ((params.page - 1) * params.pageSize).toString())
      if (params.q) p.set('q', params.q)
      if (params.role) p.set('role', params.role)
      if (params.isActive !== undefined) p.set('is_active', params.isActive.toString())
      if (params.sortBy) p.set('sort_by', params.sortBy)
      if (params.sortOrder) p.set('sort_order', params.sortOrder)
      const { data } = await apiClient.get(`/api/auth/users?${p}`)
      return { users: data.users as User[], total: data.total as number }
    },
    placeholderData: keepPreviousData,
  })
}

export interface AlertsListParams {
  page: number
  pageSize: number
  cleared?: boolean
  kind?: string
  deviceId?: string
}

export function useAlertsList(params: AlertsListParams): UseQueryResult<{ alerts: Alert[]; total: number }> {
  return useQuery({
    queryKey: qk.alertsList(params),
    queryFn: async () => {
      const p = new URLSearchParams()
      p.set('limit', params.pageSize.toString())
      p.set('offset', ((params.page - 1) * params.pageSize).toString())
      if (params.cleared !== undefined) p.set('cleared', params.cleared.toString())
      if (params.kind) p.set('kind', params.kind)
      if (params.deviceId) p.set('device_id', params.deviceId)
      const { data } = await apiClient.get(`/api/alerts?${p}`)
      return { alerts: data.alerts as Alert[], total: (data.total ?? data.alerts?.length ?? 0) as number }
    },
    refetchInterval: REALTIME_FALLBACK_INTERVAL_MS,
    placeholderData: keepPreviousData,
  })
}

export { useWebSocket } from '@/lib/websocket'

export function useProvisioningTokens(activeOnly = true): UseQueryResult<ProvisioningTokenListResponse> {
  return useQuery({
    queryKey: qk.provisioningTokens(),
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/devices/provisioning-tokens?active_only=${activeOnly}`)
      return data as ProvisioningTokenListResponse
    },
    refetchInterval: OPERATIONS_FALLBACK_INTERVAL_MS,
  })
}

export function useBackups(): UseQueryResult<BackupListResponse> {
  return useQuery({
    queryKey: qk.backups(),
    queryFn: async () => {
      const { data } = await apiClient.get('/api/backups')
      return data as BackupListResponse
    },
    refetchInterval: OPERATIONS_FALLBACK_INTERVAL_MS,
  })
}

