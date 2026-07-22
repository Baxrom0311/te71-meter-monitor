import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Building } from '@/types/api'
import { useTheme } from '@/contexts/ThemeContext'

const TILE_LIGHT = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'
const TILE_DARK  = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const TILE_SAT   = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const ATTR_CARTO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
const ATTR_ESRI  = 'Tiles &copy; Esri'

function getBuildingStatus(b: Building): 'online' | 'offline' | 'unknown' {
  if (!b.is_active) return 'offline'
  if (b.ext_sensor_online === true) return 'online'
  if (b.ext_sensor_online === false) return 'offline'
  return 'unknown'
}

const STATUS_COLOR: Record<string, string> = {
  online: '#22c55e',
  unknown: '#eab308',
  offline: '#ef4444',
}

interface Props {
  buildings: Building[]
  selectedId?: number | null
  onSelect?: (id: number) => void
  height?: string
}

export function BuildingsMap({ buildings, selectedId, onSelect, height = '500px' }: Props) {
  const { isDark } = useTheme()
  const [satellite, setSatellite] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<L.Map | null>(null)
  const tileRef      = useRef<L.TileLayer | null>(null)
  const layersRef    = useRef<L.Layer[]>([])

  const getTileUrl  = () => satellite ? TILE_SAT  : (isDark ? TILE_DARK : TILE_LIGHT)
  const getTileAttr = () => satellite ? ATTR_ESRI : ATTR_CARTO

  // Xaritani bir marta ishga tushir
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const center = buildings.find((b) => b.latitude && b.longitude)
    const map = L.map(containerRef.current, {
      center: center ? [center.latitude!, center.longitude!] : [41.55, 60.64],
      zoom: 13,
      zoomControl: true,
    })
    mapRef.current = map

    tileRef.current = L.tileLayer(getTileUrl(), {
      attribution: getTileAttr(),
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map)

    return () => {
      map.remove()
      mapRef.current = null
      tileRef.current = null
      layersRef.current = []
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Tile URL o'zgarganda faqat tile qatlamini almashtir
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (tileRef.current) {
      tileRef.current.remove()
    }
    tileRef.current = L.tileLayer(getTileUrl(), {
      attribution: getTileAttr(),
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map)
  }, [isDark, satellite]) // eslint-disable-line react-hooks/exhaustive-deps

  // Binolar o'zgarganda markerlarni yangilash
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Eski layerlarni tozala
    layersRef.current.forEach((l) => l.remove())
    layersRef.current = []

    const isDarkNow = isDark

    for (const b of buildings) {
      const color = STATUS_COLOR[getBuildingStatus(b)]

      // Polygon
      if (b.polygon_coordinate) {
        try {
          const coords = JSON.parse(b.polygon_coordinate)[0] as number[][]
          const positions = coords.map(([lat, lng]) => [lat, lng] as L.LatLngTuple)
          const poly = L.polygon(positions, {
            color,
            fillColor: color,
            fillOpacity: selectedId === b.id ? 0.35 : 0.15,
            weight: selectedId === b.id ? 3 : 2,
            opacity: 0.9,
          })
          poly.on('click', () => onSelect?.(b.id))
          poly.addTo(map)
          layersRef.current.push(poly)
        } catch { /* malformed data */ }
      }

      // CircleMarker
      if (b.latitude != null && b.longitude != null) {
        const popupHtml = `
          <div style="
            background:${isDarkNow ? '#1e293b' : '#fff'};
            color:${isDarkNow ? '#e2e8f0' : '#1e293b'};
            border-radius:8px;min-width:160px;padding:2px 0;font-family:system-ui
          ">
            <div style="font-weight:700;font-size:13px">${b.name}</div>
            ${b.address ? `<div style="font-size:11px;color:${isDarkNow ? '#94a3b8' : '#64748b'};margin-top:2px">${b.address}</div>` : ''}
            <div style="font-size:11px;color:${isDarkNow ? '#64748b' : '#94a3b8'};margin-top:4px;display:flex;gap:8px">
              <span>${b.floors} qavat</span><span>${b.entrances_count} kirish</span>
            </div>
            ${b.ext_sensor_temp_out != null ? `<div style="font-size:11px;color:${isDarkNow ? '#94a3b8' : '#475569'};margin-top:3px">${b.ext_sensor_temp_out}°C</div>` : ''}
          </div>`

        const marker = L.circleMarker([b.latitude, b.longitude], {
          radius: selectedId === b.id ? 9 : 6,
          color: '#fff',
          weight: 2,
          fillColor: color,
          fillOpacity: 1,
        }).bindPopup(popupHtml, { className: isDarkNow ? 'leaflet-popup-dark' : '' })
        marker.on('click', () => onSelect?.(b.id))
        marker.addTo(map)
        layersRef.current.push(marker)
      }
    }
  }, [buildings, selectedId, isDark]) // eslint-disable-line react-hooks/exhaustive-deps

  // Tanlanganiga uchib bor
  useEffect(() => {
    if (!selectedId || !mapRef.current) return
    const b = buildings.find((x) => x.id === selectedId)
    if (b?.latitude && b.longitude) {
      mapRef.current.flyTo([b.latitude, b.longitude], Math.max(mapRef.current.getZoom(), 16), { duration: 0.8 })
    }
  }, [selectedId, buildings])

  return (
    <div style={{ height, width: '100%' }} className="relative rounded-b-2xl overflow-hidden">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Tile toggle */}
      <div className="absolute left-4 top-4 z-[1000] flex items-center overflow-hidden rounded-xl border border-gray-300/60 dark:border-gray-700/60 bg-white/90 dark:bg-gray-950/90 p-1 shadow-xl backdrop-blur">
        <button
          type="button"
          onClick={() => setSatellite(false)}
          className={`px-3 py-1.5 text-xs font-bold transition rounded-lg ${
            !satellite
              ? 'bg-blue-600 text-white'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          Xarita
        </button>
        <button
          type="button"
          onClick={() => setSatellite(true)}
          className={`px-3 py-1.5 text-xs font-bold transition rounded-lg ${
            satellite
              ? 'bg-blue-600 text-white'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          Satellite
        </button>
      </div>
    </div>
  )
}
