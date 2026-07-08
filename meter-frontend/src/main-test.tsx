import React from 'react'
import ReactDOM from 'react-dom/client'

console.log('[v0] main-test.tsx running')

try {
  const root = document.getElementById('root')
  if (!root) throw new Error('Root not found')
  
  ReactDOM.createRoot(root).render(
    <div style={{ padding: '20px', backgroundColor: '#f0f0f0' }}>
      <h1>Test Component</h1>
      <p>Hello World!</p>
    </div>
  )
} catch (error) {
  console.error('[v0] Error:', error)
  const root = document.getElementById('root')
  if (root) {
    root.innerHTML = `<div style="color:red;padding:20px">${error instanceof Error ? error.message : String(error)}</div>`
  }
}
