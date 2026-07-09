import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { disconnectWebSocket, subscribe } from '@/lib/websocket'
import { notify } from '@/lib/toast'
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
  const lastToastAt = useRef<Record<string, number>>({})

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

    const notifyRealtime = (
      key: string,
      payload: { type?: 'success' | 'error' | 'warning' | 'info'; title: string; message?: string },
      throttleMs = 4000,
    ) => {
      const now = Date.now()
      if ((lastToastAt.current[key] ?? 0) + throttleMs > now) return
      lastToastAt.current[key] = now
      notify({ type: payload.type ?? 'info', title: payload.title, message: payload.message, durationMs: 3500 })
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

      if (message.type === 'device_updated') {
        if (message.device_id) {
          queryClient.invalidateQueries({ queryKey: ['device', message.device_id] })
        }
        queryClient.invalidateQueries({ queryKey: ['devices'] })
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        notifyRealtime(
          `device_updated:${message.device_id ?? 'unknown'}`,
          {
            type: message.event === 'created' ? 'success' : 'info',
            title: message.event === 'created' ? 'Qurilma yaratildi' : 'Qurilma sozlamasi yangilandi',
            message: message.device_id,
          },
          6000,
        )
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
        if (message.event === 'created') {
          queryClient.invalidateQueries({ queryKey: ['devices'] })
        }
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        notifyRealtime(
          `device:${deviceId}:${online ? 'online' : 'offline'}`,
          {
            type: online ? 'success' : 'warning',
            title: online ? 'Qurilma online' : 'Qurilma offline',
            message: deviceId,
          },
          15_000,
        )
        return
      }

      if (message.type === 'reading') {
        updateReading(message)
        notifyRealtime(
          'reading',
          {
            type: 'info',
            title: 'Yangi o‘lchov keldi',
            message: message.device_id ? `Qurilma: ${message.device_id}` : undefined,
          },
          30_000,
        )
        return
      }

      if (message.type === 'readings_batch') {
        if (message.device_id) updateDevice(message.device_id, { online: true, last_seen: Math.floor(Date.now() / 1000) })
        queryClient.invalidateQueries({ queryKey: ['devices'] })
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        queryClient.invalidateQueries({ queryKey: ['hourly-stats'] })
        notifyRealtime(
          'readings_batch',
          {
            type: 'info',
            title: 'O‘lchovlar paketi qabul qilindi',
            message: message.device_id ? `Qurilma: ${message.device_id}` : undefined,
          },
          20_000,
        )
        return
      }

      if (message.type === 'alert' || message.type === 'alert_notification') {
        queryClient.invalidateQueries({ queryKey: ['alerts'] })
        queryClient.invalidateQueries({ queryKey: ['summary'] })
        const notification = asRecord(message.notification)
        const event = message.event
        const severity = stringOrNull(notification.severity) ?? stringOrNull(message.data?.severity)
        const isCleared = event === 'cleared' || event === 'cleared_all'
        notifyRealtime(
          `alert:${event ?? message.type}:${message.device_id ?? notification.device_id ?? 'all'}`,
          {
            type: isCleared ? 'success' : severity === 'critical' ? 'error' : 'warning',
            title: isCleared ? 'Ogohlantirish yopildi' : 'Ogohlantirish yangilandi',
            message: stringOrNull(notification.message) ?? stringOrNull(message.data?.message) ?? message.device_id,
          },
          6000,
        )
        return
      }

      if (message.type === 'ota_batch') {
        queryClient.invalidateQueries({ queryKey: ['ota-batches'] })
        queryClient.invalidateQueries({ queryKey: ['firmware'] })
        const eventLabels: Record<string, string> = {
          created: 'OTA batch yaratildi',
          processed: 'OTA batch ishga tushdi',
          cancelled: 'OTA batch bekor qilindi',
          reported: 'OTA batch yangilandi',
        }
        notifyRealtime(
          `ota_batch:${message.event ?? 'updated'}:${message.batch_id ?? 'unknown'}`,
          {
            type: message.event === 'cancelled' ? 'warning' : 'info',
            title: eventLabels[message.event ?? ''] ?? 'OTA batch yangilandi',
            message: message.batch_id ? `Batch #${message.batch_id}` : undefined,
          },
          6000,
        )
        return
      }

      if (message.type === 'firmware') {
        queryClient.invalidateQueries({ queryKey: ['firmware'] })
        queryClient.invalidateQueries({ queryKey: ['ota-batches'] })
        notifyRealtime(
          `firmware:${message.event ?? 'updated'}:${message.firmware_id ?? 'unknown'}`,
          {
            type: message.event === 'deleted' ? 'warning' : 'success',
            title: message.event === 'deleted' ? 'Firmware o‘chirildi' : 'Firmware yangilandi',
            message: message.firmware_id ? `Firmware #${message.firmware_id}` : undefined,
          },
          6000,
        )
        return
      }

      if (message.type === 'ota_report') {
        queryClient.invalidateQueries({ queryKey: ['ota-batches'] })
        queryClient.invalidateQueries({ queryKey: ['firmware'] })
        if (message.device_id) {
          queryClient.invalidateQueries({ queryKey: ['devices'] })
          queryClient.invalidateQueries({ queryKey: ['device', message.device_id] })
        }
        notifyRealtime(
          `ota_report:${message.device_id ?? 'unknown'}:${message.status ?? 'updated'}`,
          {
            type: message.status === 'success' ? 'success' : message.status === 'failed' ? 'error' : 'info',
            title: 'OTA hisoboti keldi',
            message: message.device_id ? `${message.device_id}: ${message.status ?? 'updated'}` : undefined,
          },
          6000,
        )
      }
    })

    return () => unsubscribe()
  }, [queryClient, token])

  return null
}
