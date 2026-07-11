import { useEffect, useRef, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Building } from '@/types/api'

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY || ''

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

export function MapboxBuildings({ buildings, selectedId, onSelect, height = '500px' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])

  const flyTo = useCallback((b: Building) => {
    if (!mapRef.current || !b.latitude || !b.longitude) return
    mapRef.current.flyTo({ center: [b.longitude, b.latitude], zoom: 17, pitch: 50, duration: 1000 })
  }, [])

  useEffect(() => {
    if (!containerRef.current || !MAPTILER_KEY) return

    const center = buildings.find(b => b.latitude && b.longitude)
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`,
      center: center ? [center.longitude!, center.latitude!] : [60.64, 41.55],
      zoom: 13,
      pitch: 40,
      antialias: true,
    })
    mapRef.current = map

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.addControl(new maplibregl.FullscreenControl(), 'top-right')

    map.on('load', () => {
      // 3D binolar (MapTiler streets-v2 da bor)
      const labelLayer = map.getStyle().layers?.find(
        l => l.type === 'symbol' && (l as any).layout?.['text-field']
      )?.id

      map.addLayer({
        id: 'smartbino-3d',
        source: 'composite',
        'source-layer': 'building',
        filter: ['==', 'extrude', 'true'],
        type: 'fill-extrusion',
        minzoom: 14,
        paint: {
          'fill-extrusion-color': '#1e3a5f',
          'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, ['get', 'height']],
          'fill-extrusion-base': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, ['get', 'min_height']],
          'fill-extrusion-opacity': 0.65,
        },
      }, labelLayer)

      // Urganchshahar polygon chegaralari
      const features: GeoJSON.Feature[] = []
      for (const b of buildings) {
        if (!b.polygon_coordinate) continue
        try {
          const coords: number[][][] = JSON.parse(b.polygon_coordinate)[0]
          const ring = coords.map(([lat, lon]) => [lon, lat])
          features.push({
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [ring] },
            properties: { id: b.id, status: getBuildingStatus(b), name: b.name, address: b.address || '' },
          })
        } catch { /* skip */ }
      }

      if (features.length > 0) {
        map.addSource('bino-polygons', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features },
        })
        map.addLayer({
          id: 'bino-fill',
          type: 'fill',
          source: 'bino-polygons',
          paint: {
            'fill-color': ['match', ['get', 'status'],
              'online', 'rgba(34,197,94,0.22)',
              'offline', 'rgba(239,68,68,0.22)',
              'rgba(234,179,8,0.16)'],
            'fill-outline-color': ['match', ['get', 'status'],
              'online', '#22c55e', 'offline', '#ef4444', '#eab308'],
          },
        })
        map.addLayer({
          id: 'bino-line',
          type: 'line',
          source: 'bino-polygons',
          paint: {
            'line-color': ['match', ['get', 'status'],
              'online', '#22c55e', 'offline', '#ef4444', '#eab308'],
            'line-width': 2,
          },
        })

        map.on('click', 'bino-fill', e => {
          const f = e.features?.[0]
          if (!f) return
          onSelect?.(Number(f.properties!.id))
          new maplibregl.Popup({ closeButton: false, maxWidth: '220px' })
            .setLngLat(e.lngLat)
            .setHTML(`<div style="font-family:system-ui;padding:2px">
              <b style="font-size:13px">${f.properties!.name}</b>
              ${f.properties!.address ? `<div style="font-size:11px;color:#64748b;margin-top:2px">${f.properties!.address}</div>` : ''}
            </div>`)
            .addTo(map)
        })
        map.on('mouseenter', 'bino-fill', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'bino-fill', () => { map.getCanvas().style.cursor = '' })
      }

      // Markerlar
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []
      for (const b of buildings) {
        if (!b.latitude || !b.longitude) continue
        const color = STATUS_COLOR[getBuildingStatus(b)]
        const el = document.createElement('div')
        el.style.cssText = `width:11px;height:11px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 7px ${color}aa;cursor:pointer;transition:transform .15s`
        el.onmouseenter = () => (el.style.transform = 'scale(1.7)')
        el.onmouseleave = () => (el.style.transform = 'scale(1)')

        const popup = new maplibregl.Popup({ offset: 12, closeButton: false, maxWidth: '240px' }).setHTML(`
          <div style="font-family:system-ui;padding:2px">
            <b style="font-size:13px">${b.name}</b>
            ${b.address ? `<div style="font-size:11px;color:#64748b;margin-top:2px">${b.address}</div>` : ''}
            <div style="font-size:11px;color:#94a3b8;margin-top:4px;display:flex;gap:8px">
              <span>${b.floors} qavat</span><span>${b.entrances_count} kirish</span>
              ${b.organization_name ? `<span>${b.organization_name}</span>` : ''}
            </div>
            ${b.ext_sensor_temp_out != null ? `<div style="font-size:11px;color:#475569;margin-top:3px">🌡 ${b.ext_sensor_temp_out}°C</div>` : ''}
          </div>
        `)
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([b.longitude, b.latitude])
          .setPopup(popup)
          .addTo(map)
        el.onclick = () => onSelect?.(b.id)
        markersRef.current.push(marker)
      }
    })

    return () => {
      markersRef.current.forEach(m => m.remove())
      map.remove()
      mapRef.current = null
    }
  }, [buildings]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId) return
    const b = buildings.find(x => x.id === selectedId)
    if (b) flyTo(b)
  }, [selectedId, buildings, flyTo])

  if (!MAPTILER_KEY) {
    return (
      <div className="flex items-center justify-center bg-gray-900/50 rounded-b-2xl text-sm text-gray-400 p-8" style={{ height }}>
        <div className="text-center">
          <p className="font-bold text-yellow-400 mb-2">MapTiler API key kerak</p>
          <p className="text-xs text-gray-500 mb-2">cloud.maptiler.com → bepul ro'yxat → API Keys</p>
          <code className="text-xs bg-gray-800 px-2 py-1 rounded text-gray-300">VITE_MAPTILER_KEY=...</code>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="rounded-b-2xl overflow-hidden" style={{ height, width: '100%' }} />
  )
}
