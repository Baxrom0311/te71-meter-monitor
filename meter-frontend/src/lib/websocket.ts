import { useState, useEffect, useCallback, useRef } from 'react'
import { WebSocketMessage } from '@/types/api'
import { getTokenFromStorage } from './auth'
import { API_BASE_URL } from './env'

let ws: WebSocket | null = null
let listeners: ((message: WebSocketMessage) => void)[] = []
let reconnectAttempts = 0
let manualClose = false
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_INTERVAL = 3000
export const WS_STATUS_EVENT = 'meter:ws-status'
export type WebSocketConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'failed'

let connectionStatus: WebSocketConnectionStatus = 'idle'

function emitStatus(status: WebSocketConnectionStatus) {
  connectionStatus = status
  window.dispatchEvent(new CustomEvent<WebSocketConnectionStatus>(WS_STATUS_EVENT, { detail: status }))
}

function getWebSocketURL(): string {
  const token = getTokenFromStorage()
  const protocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws'
  const host = new URL(API_BASE_URL).host
  return `${protocol}://${host}/ws?token=${token}`
}

function connect() {
  if (ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING) {
    return
  }

  try {
    manualClose = false
    emitStatus(reconnectAttempts > 0 ? 'reconnecting' : 'connecting')
    ws = new WebSocket(getWebSocketURL())

    ws.onopen = () => {
      console.log('[v0] WebSocket connected')
      reconnectAttempts = 0
      emitStatus('connected')
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        listeners.forEach((listener) => listener(message))
      } catch (error) {
        console.error('[v0] Failed to parse WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('[v0] WebSocket error:', error)
    }

    ws.onclose = () => {
      if (manualClose || listeners.length === 0) {
        emitStatus('idle')
        return
      }
      console.log('[v0] WebSocket closed, attempting to reconnect...')
      emitStatus('reconnecting')
      attemptReconnect()
    }
  } catch (error) {
    console.error('[v0] Failed to connect to WebSocket:', error)
    attemptReconnect()
  }
}

function attemptReconnect() {
  if (!manualClose && listeners.length > 0 && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
    reconnectAttempts++
    emitStatus('reconnecting')
    setTimeout(connect, RECONNECT_INTERVAL)
  } else {
    console.error('[v0] Max WebSocket reconnection attempts reached')
    emitStatus(listeners.length > 0 ? 'failed' : 'idle')
  }
}

export function subscribe(listener: (message: WebSocketMessage) => void) {
  listeners.push(listener)
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    connect()
  }

  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}

export function useWebSocket() {
  const [message, setMessage] = useState<WebSocketMessage | null>(null)
  const unsubscribeRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    unsubscribeRef.current = subscribe((msg) => {
      setMessage(msg)
    })

    return () => {
      unsubscribeRef.current?.()
    }
  }, [])

  return message
}

export function useWebSocketStatus() {
  const [status, setStatus] = useState<WebSocketConnectionStatus>(connectionStatus)

  useEffect(() => {
    const listener = (event: Event) => setStatus((event as CustomEvent<WebSocketConnectionStatus>).detail)
    window.addEventListener(WS_STATUS_EVENT, listener)
    return () => window.removeEventListener(WS_STATUS_EVENT, listener)
  }, [])

  return status
}

export function connectWebSocket() {
  connect()
}

export function disconnectWebSocket() {
  if (ws) {
    manualClose = true
    ws.close()
    ws = null
  }
  reconnectAttempts = 0
  emitStatus('idle')
}
