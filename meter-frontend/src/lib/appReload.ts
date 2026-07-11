const RELOAD_MARKER = 'meter:fresh-reload-attempt'
const SW_CLEAN_MARKER = 'meter:sw-cleaned'

async function clearBrowserCaches() {
  if ('caches' in window) {
    const keys = await caches.keys()
    await Promise.all(keys.map((key) => caches.delete(key)))
  }
}

async function unregisterServiceWorkers() {
  if (!('serviceWorker' in navigator)) return false
  const registrations = await navigator.serviceWorker.getRegistrations()
  await Promise.all(registrations.map((registration) => registration.unregister()))
  return registrations.length > 0 || Boolean(navigator.serviceWorker.controller)
}

function cacheBustedUrl() {
  const url = new URL(window.location.href)
  url.searchParams.set('app_v', Date.now().toString())
  return url.toString()
}

export function isChunkLoadError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return /chunk|import|module|fetch|failed to fetch dynamically imported module/i.test(message)
}

export async function reloadAppFresh(reason = 'manual') {
  try {
    sessionStorage.setItem(RELOAD_MARKER, `${Date.now()}:${reason}`)
    await unregisterServiceWorkers()
    await clearBrowserCaches()
  } finally {
    window.location.replace(cacheBustedUrl())
  }
}

export async function cleanupLegacyServiceWorkersOnBoot() {
  if (!('serviceWorker' in navigator)) return
  if (sessionStorage.getItem(SW_CLEAN_MARKER)) return

  const hadServiceWorker = await unregisterServiceWorkers()
  if (!hadServiceWorker) return

  sessionStorage.setItem(SW_CLEAN_MARKER, '1')
  await clearBrowserCaches()

  if (navigator.serviceWorker.controller) {
    window.location.replace(cacheBustedUrl())
  }
}

