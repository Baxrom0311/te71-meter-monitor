import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { disconnectWebSocket, subscribe } from '@/lib/websocket'
import type { Alert, Device, Reading, WebSocketMessage } from '@/types/api'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

export function RealtimeSync() {
  const { token } = useAuth()
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!token) {
      disconnectWebSocket()
      return
    }

    disconnectWebSocket()

    const updateDevice = (deviceId: string, patch: Partial<Device>) => {
      queryClient.setQueriesData<Device[]>({ queryKey: ['devices'] }, (old) => {
        if (!old) return old
        return old.map((device) => (device.id === deviceId ? { ...device, ...patch } : device))
      })
      queryClient.setQueryData<Device>(['device', deviceId], (old) => (old ? { ...old, ...patch } : old))
    }

    const updateReading = (message: WebSocketMessage) => {
      const data = asRecord(message.data)
      const deviceId = message.device_id || stringOrNull(data.device_id)
      if (!deviceId) return

      const ts = typeof message.ts === 'number' ? message.ts : numberOrNull(data.ts)
      updateDevice(deviceId, { online: true, last_seen: ts ?? Math.floor(Date.now() / 1000) })

      queryClient.setQueryData<Reading>(['device-latest', deviceId], (old) => ({
        ...(old ?? {}),
        ...data,
        device_id: deviceId,
        ts: ts ?? old?.ts ?? Math.floor(Date.now() / 1000),
      }) as Reading)

      queryClient.invalidateQueries({ queryKey: ['device-history', deviceId] })
      queryClient.invalidateQueries({ queryKey: ['hourly-stats'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
    }

    const unsubscribe = subscribe((message) => {
      if (message.type === 'snapshot') {
        const data = asRecord(message.data)
        const devices = Array.isArray(data.devices) ? (data.devices as Device[]) : null
        const alerts = Array.isArray(data.alerts) ? (data.alerts as Alert[]) : null
        if (devices) {
          queryClient.setQueriesData<Device[]>({ queryKey: ['devices'] }, (old) => old ?? devices)
        }
        if (alerts) {
          queryClient.setQueriesData<Alert[]>({ queryKey: ['alerts'] }, (old) => old ?? alerts)
        }
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        return
      }

      if (message.type === 'device_online' || message.type === 'device_offline' || message.type === 'status') {
        const deviceId = message.device_id
        if (!deviceId) return
        const online = message.type === 'status' ? Boolean(message.online) : message.type === 'device_online'
        updateDevice(deviceId, {
          online,
          last_seen: online ? Math.floor(Date.now() / 1000) : undefined,
        })
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        return
      }

      if (message.type === 'reading') {
        updateReading(message)
        return
      }

      if (message.type === 'readings_batch') {
        if (message.device_id) updateDevice(message.device_id, { online: true, last_seen: Math.floor(Date.now() / 1000) })
        queryClient.invalidateQueries({ queryKey: ['devices'] })
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        queryClient.invalidateQueries({ queryKey: ['hourly-stats'] })
        return
      }

      if (message.type === 'alert') {
        queryClient.invalidateQueries({ queryKey: ['alerts'] })
        queryClient.invalidateQueries({ queryKey: ['summary'] })
      }
    })

    return () => unsubscribe()
  }, [queryClient, token])

  return null
}
