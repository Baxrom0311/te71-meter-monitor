import { useEffect, useRef } from 'react'
import { ExternalLink, MapPin } from 'lucide-react'
import { EmptyBlock } from '@/components/StateBlock'
import { hasGoogleMapsKey, loadGoogleMaps } from '@/lib/googleMaps'
import { resolveCoordinates } from '@/lib/map'

interface MapPanelProps {
  title?: string
  subtitle?: string
  name: string
  address?: string | null
  mapsUrl?: string | null
  latitude?: number | null
  longitude?: number | null
  heightClassName?: string
}

export function MapPanel({
  title = 'Xarita',
  subtitle,
  name,
  address,
  mapsUrl,
  latitude,
  longitude,
  heightClassName = 'h-[360px]',
}: MapPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const coordinates = resolveCoordinates(latitude, longitude, mapsUrl)

  useEffect(() => {
    if (!containerRef.current || !coordinates || !hasGoogleMapsKey()) return
    let cancelled = false

    loadGoogleMaps().then(() => {
      const container = containerRef.current
      if (!container || cancelled) return

      const map = new google.maps.Map(container, {
        center: { lat: coordinates.latitude, lng: coordinates.longitude },
        zoom: 17,
        mapId: 'smartbino_detail',
        gestureHandling: 'greedy',
        streetViewControl: false,
        mapTypeControl: false,
      })
      new google.maps.marker.AdvancedMarkerElement({
        map,
        position: { lat: coordinates.latitude, lng: coordinates.longitude },
        title: name,
      })
    })

    return () => {
      cancelled = true
    }
  }, [coordinates?.latitude, coordinates?.longitude]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="glass-card rounded-2xl overflow-hidden shadow border border-gray-300/60 dark:border-gray-800/70">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-5 py-4 border-b border-gray-300/60 dark:border-gray-800/70">
        <div className="min-w-0">
          <h2 className="text-lg font-extrabold text-gray-950 dark:text-gray-100 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-blue-500" />
            {title}
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
            {subtitle ?? address ?? name}
          </p>
        </div>
        {mapsUrl && !mapsUrl.startsWith('ext://') && (
          <a href={mapsUrl} target="_blank" rel="noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700 transition">
            <ExternalLink className="w-3.5 h-3.5" /> Google Maps
          </a>
        )}
      </div>

      {coordinates ? (
        <div className={`relative ${heightClassName}`}>
          <div ref={containerRef} className="absolute inset-0 w-full h-full" />
          <div className="pointer-events-none absolute left-4 bottom-4 rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/90 dark:bg-gray-950/90 px-3 py-2 shadow-xl backdrop-blur z-10">
            <p className="text-xs font-black text-gray-950 dark:text-gray-100">{name}</p>
            <p className="text-[11px] font-mono text-gray-600 dark:text-gray-400">
              {coordinates.latitude.toFixed(6)}, {coordinates.longitude.toFixed(6)}
            </p>
          </div>
        </div>
      ) : (
        <div className={heightClassName}>
          <EmptyBlock title="Koordinata topilmadi" message="Xaritada ko'rsatish uchun latitude/longitude kiriting." />
        </div>
      )}
    </section>
  )
}
