// VITE_API_URL must be set at build time (see .env.production)
const rawUrl = import.meta.env.VITE_API_URL
if (!rawUrl && import.meta.env.PROD) {
  console.error('[config] VITE_API_URL environment variable is not set!')
}
export const API_BASE_URL = (rawUrl || '').replace(/\/+$/, '')
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
