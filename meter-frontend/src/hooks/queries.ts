import { useQuery, UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import {
  Summary,
  Building,
  Device,
  Alert,
  AlertRule,
  EnergyAnalytics,
  AuditLog,
  AuditLogListResponse,
  User,
  Reading,
  DeviceHistoryResponse,
  OtaBatch,
  BuildingsEnergySummaryResponse,
  HourlyUtilityStatsResponse,
} from '@/types/api'

// Summary
export function useSummary(): UseQueryResult<Summary> {
  return useQuery({
    queryKey: ['summary'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/summary')
      return data
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  })
}

export function useEnergySummary(days = 30): UseQueryResult<BuildingsEnergySummaryResponse> {
  return useQuery({
    queryKey: ['energy-summary', days],
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
    queryKey: ['hourly-stats', hours, buildingId, utilityType],
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
    queryKey: ['energy-analytics', granularity, fromTs, toTs, buildingId],
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
    queryKey: ['buildings'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/buildings')
      return data.buildings
    },
  })
}

export function useBuildingById(id: string): UseQueryResult<Building> {
  return useQuery({
    queryKey: ['building', id],
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
    queryKey: ['devices', limit, offset],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (limit) params.append('limit', limit.toString())
      if (offset) params.append('offset', offset.toString())
      const { data } = await apiClient.get(`/api/devices?${params}`)
      return data.devices
    },
    refetchInterval: 20000, // Refetch every 20 seconds
  })
}

export function useDeviceById(id: string): UseQueryResult<Device> {
  return useQuery({
    queryKey: ['device', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/devices/${id}`)
      return data
    },
    enabled: !!id,
    refetchInterval: 20000,
  })
}

export function useDeviceLatest(id: string): UseQueryResult<Reading> {
  return useQuery({
    queryKey: ['device-latest', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/devices/${id}/latest`)
      return data
    },
    enabled: !!id,
    refetchInterval: 15000,
  })
}

export function useDeviceHistory(id: string, hours = 24): UseQueryResult<DeviceHistoryResponse> {
  return useQuery({
    queryKey: ['device-history', id, hours],
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/devices/${id}/history?hours=${hours}`)
      return data
    },
    enabled: !!id,
  })
}

// Alerts
export function useAlerts(cleared?: boolean, limit?: number): UseQueryResult<Alert[]> {
  return useQuery({
    queryKey: ['alerts', cleared, limit],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (cleared !== undefined) params.append('cleared', cleared.toString())
      if (limit) params.append('limit', limit.toString())
      const { data } = await apiClient.get(`/api/alerts?${params}`)
      return data.alerts
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  })
}

// Users (Admin)
export function useUsers(): UseQueryResult<User[]> {
  return useQuery({
    queryKey: ['users'],
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
    queryKey: ['audit-logs', limit, page, filters],
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
    queryKey: ['firmware'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/ota/list')
      return data.firmware ?? data
    },
  })
}

export function useOtaBatches(enabled = true): UseQueryResult<OtaBatch[]> {
  return useQuery({
    queryKey: ['ota-batches'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/ota/batches')
      return data.batches ?? []
    },
    enabled,
    refetchInterval: 10000,
  })
}

// Alert Rules
export function useAlertRules(): UseQueryResult<AlertRule[]> {
  return useQuery({
    queryKey: ['alert-rules'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/alert-rules')
      return data.rules ?? data
    },
  })
}

export { useWebSocket } from '@/lib/websocket'
