import { importLibrary, setOptions } from '@googlemaps/js-api-loader'

const GOOGLE_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY || ''

let configured = false
let loadPromise: Promise<void> | null = null

export function hasGoogleMapsKey() {
  return Boolean(GOOGLE_KEY)
}

export function loadGoogleMaps() {
  if (!GOOGLE_KEY) {
    return Promise.reject(new Error('VITE_GOOGLE_MAPS_KEY is not configured'))
  }

  if (!configured) {
    setOptions({
      key: GOOGLE_KEY,
      v: 'weekly',
      libraries: ['maps', 'marker'],
    })
    configured = true
  }

  if (!loadPromise) {
    loadPromise = Promise.all([
      importLibrary('maps'),
      importLibrary('marker'),
    ]).then(() => undefined)
  }

  return loadPromise
}
