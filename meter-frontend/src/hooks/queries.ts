import { useQuery, UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import {
  Summary,
  Building,
  Device,
  Alert,
  EnergyAnalytics,
  AuditLog,
  User,
  OtaBatch,
  BuildingsEnergySummaryResponse,
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

// Energy Analytics
export function useEnergyAnalytics(
  granularity: 'hour' | 'day' = 'hour',
  fromTs?: number,
  toTs?: number,
): UseQueryResult<EnergyAnalytics> {
  return useQuery({
    queryKey: ['energy-analytics', granularity, fromTs, toTs],
    queryFn: async () => {
      const params = new URLSearchParams({
        granularity,
        ...(fromTs && { from_ts: fromTs.toString() }),
        ...(toTs && { to_ts: toTs.toString() }),
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

export function useDeviceLatest(id: string) {
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

export function useDeviceHistory(id: string, hours = 24) {
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
export function useAuditLogs(limit?: number, offset?: number): UseQueryResult<AuditLog[]> {
  return useQuery({
    queryKey: ['audit-logs', limit, offset],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (limit) params.append('limit', limit.toString())
      if (offset) params.append('offset', offset.toString())
      const { data } = await apiClient.get(`/api/audit-logs?${params}`)
      return data.logs ?? data.audit_logs ?? data
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
export function useAlertRules() {
  return useQuery({
    queryKey: ['alert-rules'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/alert-rules')
      return data.rules ?? data
    },
  })
}

export { useWebSocket } from '@/lib/websocket'
