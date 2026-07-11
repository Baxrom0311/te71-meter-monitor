import { useEffect, useRef, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { MAPBOX_TOKEN } from '@/lib/env'
import type { Building } from '@/types/api'

mapboxgl.accessToken = MAPBOX_TOKEN

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
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const markersRef = useRef<mapboxgl.Marker[]>([])
  const popupRef = useRef<mapboxgl.Popup | null>(null)

  const flyTo = useCallback((b: Building) => {
    if (!mapRef.current || !b.latitude || !b.longitude) return
    mapRef.current.flyTo({
      center: [b.longitude, b.latitude],
      zoom: 17,
      pitch: 55,
      bearing: 20,
      duration: 1200,
    })
  }, [])

  useEffect(() => {
    if (!containerRef.current || !MAPBOX_TOKEN) return

    const center = buildings.find(b => b.latitude && b.longitude)
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: center ? [center.longitude!, center.latitude!] : [60.64, 41.55],
      zoom: 13,
      pitch: 45,
      bearing: 0,
      antialias: true,
    })
    mapRef.current = map

    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    map.addControl(new mapboxgl.FullscreenControl(), 'top-right')

    map.on('load', () => {
      // 3D binolar qatlami (Mapbox built-in)
      const layers = map.getStyle().layers
      const labelLayerId = layers?.find(
        l => l.type === 'symbol' && (l.layout as any)?.['text-field']
      )?.id

      map.addLayer(
        {
          id: 'add-3d-buildings',
          source: 'composite',
          'source-layer': 'building',
          filter: ['==', 'extrude', 'true'],
          type: 'fill-extrusion',
          minzoom: 14,
          paint: {
            'fill-extrusion-color': '#1e3a5f',
            'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, ['get', 'height']],
            'fill-extrusion-base': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, ['get', 'min_height']],
            'fill-extrusion-opacity': 0.7,
          },
        },
        labelLayerId,
      )

      // Polygon qatlami — urganchshahar polygon_coordinate
      const polygonFeatures: GeoJSON.Feature[] = []
      for (const b of buildings) {
        if (!b.polygon_coordinate) continue
        try {
          const coords: number[][][] = JSON.parse(b.polygon_coordinate)[0]
          // [[lat, lon], ...] → [[lon, lat], ...] (GeoJSON)
          const ring = coords.map(([lat, lon]) => [lon, lat])
          const status = getBuildingStatus(b)
          polygonFeatures.push({
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [ring] },
            properties: { id: b.id, status, name: b.name, address: b.address },
          })
        } catch { /* skip */ }
      }

      if (polygonFeatures.length > 0) {
        map.addSource('building-polygons', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: polygonFeatures },
        })
        map.addLayer({
          id: 'building-polygons-fill',
          type: 'fill',
          source: 'building-polygons',
          paint: {
            'fill-color': [
              'match', ['get', 'status'],
              'online', 'rgba(34,197,94,0.20)',
              'offline', 'rgba(239,68,68,0.20)',
              'rgba(234,179,8,0.15)',
            ],
            'fill-outline-color': [
              'match', ['get', 'status'],
              'online', '#22c55e',
              'offline', '#ef4444',
              '#eab308',
            ],
          },
        })
        map.addLayer({
          id: 'building-polygons-line',
          type: 'line',
          source: 'building-polygons',
          paint: {
            'line-color': [
              'match', ['get', 'status'],
              'online', '#22c55e',
              'offline', '#ef4444',
              '#eab308',
            ],
            'line-width': 1.5,
            'line-opacity': 0.8,
          },
        })

        map.on('click', 'building-polygons-fill', (e) => {
          const f = e.features?.[0]
          if (!f) return
          onSelect?.(f.properties!.id)
        })
        map.on('mouseenter', 'building-polygons-fill', () => {
          map.getCanvas().style.cursor = 'pointer'
        })
        map.on('mouseleave', 'building-polygons-fill', () => {
          map.getCanvas().style.cursor = ''
        })
      }

      // Markerlar — koordinatali binolar
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []

      for (const b of buildings) {
        if (!b.latitude || !b.longitude) continue
        const status = getBuildingStatus(b)
        const color = STATUS_COLOR[status]

        const el = document.createElement('div')
        el.className = 'mapbox-building-marker'
        el.style.cssText = `
          width:14px; height:14px; border-radius:50%;
          background:${color}; border:2px solid #fff;
          box-shadow:0 0 6px ${color}88;
          cursor:pointer; transition:transform .15s;
        `
        el.addEventListener('mouseenter', () => (el.style.transform = 'scale(1.5)'))
        el.addEventListener('mouseleave', () => (el.style.transform = 'scale(1)'))

        const popup = new mapboxgl.Popup({ offset: 14, closeButton: false, maxWidth: '260px' }).setHTML(`
          <div style="font-family:system-ui;padding:4px">
            <div style="font-weight:700;font-size:13px;margin-bottom:4px">${b.name}</div>
            ${b.address ? `<div style="font-size:11px;color:#94a3b8;margin-bottom:4px">${b.address}</div>` : ''}
            <div style="display:flex;gap:8px;font-size:11px">
              <span style="color:#94a3b8">${b.floors} qavat</span>
              <span style="color:#94a3b8">${b.entrances_count} kirish</span>
              ${b.organization_name ? `<span style="color:#94a3b8">${b.organization_name}</span>` : ''}
            </div>
            ${b.ext_sensor_temp_out != null ? `<div style="margin-top:4px;font-size:11px;color:#cbd5e1">🌡 Tashqi: ${b.ext_sensor_temp_out}°C</div>` : ''}
          </div>
        `)

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([b.longitude, b.latitude])
          .setPopup(popup)
          .addTo(map)

        el.addEventListener('click', () => onSelect?.(b.id))
        markersRef.current.push(marker)
      }
    })

    return () => {
      markersRef.current.forEach(m => m.remove())
      map.remove()
      mapRef.current = null
    }
  }, [buildings]) // eslint-disable-line react-hooks/exhaustive-deps

  // Tanlangan bino ga fly
  useEffect(() => {
    if (!selectedId) return
    const b = buildings.find(x => x.id === selectedId)
    if (b) flyTo(b)
  }, [selectedId, buildings, flyTo])

  if (!MAPBOX_TOKEN) {
    return (
      <div className="flex items-center justify-center rounded-2xl bg-gray-900 border border-gray-800" style={{ height }}>
        <div className="text-center text-sm text-gray-400 p-6">
          <p className="font-bold text-yellow-400 mb-1">VITE_MAPBOX_TOKEN sozlanmagan</p>
          <p>.env.local ga qo'shing:<br /><code className="text-xs text-gray-300">VITE_MAPBOX_TOKEN=pk.eyJ...</code></p>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="rounded-2xl overflow-hidden border border-gray-800 shadow-xl"
      style={{ height, width: '100%' }}
    />
  )
}
