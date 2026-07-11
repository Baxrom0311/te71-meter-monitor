import { useEffect, useRef, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Building } from '@/types/api'

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
    mapRef.current.flyTo({
      center: [b.longitude, b.latitude],
      zoom: 17,
      pitch: 55,
      bearing: 20,
      duration: 1200,
    })
  }, [])

  useEffect(() => {
    if (!containerRef.current) return

    const center = buildings.find(b => b.latitude && b.longitude)
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
            maxzoom: 19,
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: center ? [center.longitude!, center.latitude!] : [60.64, 41.55],
      zoom: 13,
      pitch: 40,
      bearing: 0,
      antialias: true,
    })
    mapRef.current = map

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.addControl(new maplibregl.FullscreenControl(), 'top-right')

    map.on('load', () => {
      // Polygon qatlami — urganchshahar polygon_coordinate
      const polygonFeatures: GeoJSON.Feature[] = []
      for (const b of buildings) {
        if (!b.polygon_coordinate) continue
        try {
          const coords: number[][][] = JSON.parse(b.polygon_coordinate)[0]
          // [[lat, lon], ...] → [[lon, lat], ...] (GeoJSON format)
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
              'online', 'rgba(34,197,94,0.25)',
              'offline', 'rgba(239,68,68,0.25)',
              'rgba(234,179,8,0.18)',
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
            'line-width': 2,
            'line-opacity': 0.9,
          },
        })

        // Polygon ustiga klik
        map.on('click', 'building-polygons-fill', (e) => {
          const f = e.features?.[0]
          if (!f) return
          onSelect?.(Number(f.properties!.id))

          new maplibregl.Popup({ closeButton: false, maxWidth: '240px' })
            .setLngLat(e.lngLat)
            .setHTML(`
              <div style="font-family:system-ui;padding:4px 2px">
                <div style="font-weight:700;font-size:13px;margin-bottom:2px">${f.properties!.name}</div>
                ${f.properties!.address ? `<div style="font-size:11px;color:#64748b">${f.properties!.address}</div>` : ''}
              </div>
            `)
            .addTo(map)
        })
        map.on('mouseenter', 'building-polygons-fill', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'building-polygons-fill', () => { map.getCanvas().style.cursor = '' })
      }

      // Markerlar
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []

      for (const b of buildings) {
        if (!b.latitude || !b.longitude) continue
        const status = getBuildingStatus(b)
        const color = STATUS_COLOR[status]

        const el = document.createElement('div')
        el.style.cssText = `
          width:12px; height:12px; border-radius:50%;
          background:${color}; border:2px solid #fff;
          box-shadow:0 0 8px ${color}99;
          cursor:pointer; transition:transform .15s;
        `
        el.addEventListener('mouseenter', () => (el.style.transform = 'scale(1.7)'))
        el.addEventListener('mouseleave', () => (el.style.transform = 'scale(1)'))

        const popup = new maplibregl.Popup({ offset: 14, closeButton: false, maxWidth: '260px' }).setHTML(`
          <div style="font-family:system-ui;padding:4px 2px">
            <div style="font-weight:700;font-size:13px;margin-bottom:4px">${b.name}</div>
            ${b.address ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px">${b.address}</div>` : ''}
            <div style="display:flex;gap:8px;font-size:11px;color:#94a3b8">
              <span>${b.floors} qavat</span>
              <span>${b.entrances_count} kirish</span>
              ${b.organization_name ? `<span>${b.organization_name}</span>` : ''}
            </div>
            ${b.ext_sensor_temp_out != null ? `<div style="margin-top:4px;font-size:11px;color:#475569">🌡 ${b.ext_sensor_temp_out}°C</div>` : ''}
          </div>
        `)

        const marker = new maplibregl.Marker({ element: el })
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

  useEffect(() => {
    if (!selectedId) return
    const b = buildings.find(x => x.id === selectedId)
    if (b) flyTo(b)
  }, [selectedId, buildings, flyTo])

  return (
    <div
      ref={containerRef}
      className="rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-800 shadow-xl"
      style={{ height, width: '100%' }}
    />
  )
}
