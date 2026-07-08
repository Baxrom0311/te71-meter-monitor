import React from 'react'
import ReactDOM from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import App from './App'
import './styles/globals.css'

const updateServiceWorker = registerSW({
  immediate: true,
  onNeedRefresh() {
    window.dispatchEvent(new CustomEvent('meter:pwa-update-ready'))
  },
})

window.addEventListener('meter:pwa-update-apply', () => {
  updateServiceWorker(true)
})

try {
  const root = document.getElementById('root')
  if (!root) throw new Error('Root not found')
  
  ReactDOM.createRoot(root).render(
    <App />,
  )
} catch (error) {
  console.error('[v0] Error:', error)
  const root = document.getElementById('root')
  if (root) {
    root.innerHTML = `<div style="color:red;padding:20px;font-family:monospace">${error instanceof Error ? error.message : String(error)}<br>${error instanceof Error ? error.stack : ''}</div>`
  }
}
