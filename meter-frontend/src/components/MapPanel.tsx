import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MapPin } from 'lucide-react'
import { EmptyBlock } from '@/components/StateBlock'
import { useTheme } from '@/contexts/ThemeContext'

interface MapPanelProps {
  title?: string
  subtitle?: string
  name: string
  address?: string | null
  latitude?: number | null
  longitude?: number | null
  heightClassName?: string
}

export function MapPanel({
  title = 'Xarita',
  subtitle,
  name,
  address,
  latitude,
  longitude,
  heightClassName = 'h-[360px]',
}: MapPanelProps) {
  const { isDark } = useTheme()
  const hasCoords = latitude != null && longitude != null

  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<L.Map | null>(null)
  const tileRef      = useRef<L.TileLayer | null>(null)

  const tileUrl  = isDark
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'

  // Xaritani ishga tushir
  useEffect(() => {
    if (!containerRef.current || !hasCoords || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: [latitude!, longitude!],
      zoom: 17,
      zoomControl: true,
    })
    mapRef.current = map

    tileRef.current = L.tileLayer(tileUrl, {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map)

    const popupHtml = `
      <div style="font-family:system-ui;min-width:140px;padding:2px 0">
        <div style="font-weight:700;font-size:13px">${name}</div>
        ${address ? `<div style="font-size:11px;color:#64748b;margin-top:2px">${address}</div>` : ''}
        <div style="font-size:11px;color:#94a3b8;margin-top:3px;font-family:monospace">
          ${latitude!.toFixed(6)}, ${longitude!.toFixed(6)}
        </div>
      </div>`

    L.circleMarker([latitude!, longitude!], {
      radius: 10,
      color: '#fff',
      weight: 2,
      fillColor: '#3b82f6',
      fillOpacity: 1,
    }).bindPopup(popupHtml).addTo(map)

    return () => {
      map.remove()
      mapRef.current = null
      tileRef.current = null
    }
  }, [hasCoords]) // eslint-disable-line react-hooks/exhaustive-deps

  // Tema o'zgarganda faqat tile qatlamini almashtir
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (tileRef.current) tileRef.current.remove()
    tileRef.current = L.tileLayer(tileUrl, {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map)
  }, [isDark]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="glass-card rounded-2xl overflow-hidden shadow border border-gray-300/60 dark:border-gray-800/70">
      <div className="px-5 py-4 border-b border-gray-300/60 dark:border-gray-800/70">
        <h2 className="text-lg font-extrabold text-gray-950 dark:text-gray-100 flex items-center gap-2">
          <MapPin className="w-5 h-5 text-blue-500" />
          {title}
        </h2>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
          {subtitle ?? address ?? name}
        </p>
      </div>

      {hasCoords ? (
        <div className={`relative ${heightClassName}`}>
          <div ref={containerRef} className="absolute inset-0 w-full h-full" />
          <div className="pointer-events-none absolute left-4 bottom-8 rounded-xl border border-gray-300/60 dark:border-gray-700/60 bg-white/90 dark:bg-gray-950/90 px-3 py-2 shadow-xl backdrop-blur z-[1000]">
            <p className="text-xs font-black text-gray-950 dark:text-gray-100">{name}</p>
            <p className="text-[11px] font-mono text-gray-600 dark:text-gray-400">
              {latitude!.toFixed(6)}, {longitude!.toFixed(6)}
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
