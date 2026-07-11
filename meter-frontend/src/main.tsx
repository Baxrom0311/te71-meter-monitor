import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/globals.css'
import { cleanupLegacyServiceWorkersOnBoot } from '@/lib/appReload'

void cleanupLegacyServiceWorkersOnBoot()

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
