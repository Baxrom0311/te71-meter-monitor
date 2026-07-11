import { useEffect, useRef, useCallback } from 'react'
import { hasGoogleMapsKey, loadGoogleMaps } from '@/lib/googleMaps'
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

export function GoogleBuildingsMap({ buildings, selectedId, onSelect, height = '500px' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markersRef = useRef<google.maps.marker.AdvancedMarkerElement[]>([])
  const polygonsRef = useRef<google.maps.Polygon[]>([])
  const infoRef = useRef<google.maps.InfoWindow | null>(null)

  const flyTo = useCallback((b: Building) => {
    if (!mapRef.current || !b.latitude || !b.longitude) return
    mapRef.current.panTo({ lat: b.latitude, lng: b.longitude })
    mapRef.current.setZoom(17)
  }, [])

  function infoHtml(b: Building) {
    return `<div style="font-family:system-ui;min-width:180px;padding:4px 2px">
      <b style="font-size:13px">${b.name}</b>
      ${b.address ? `<div style="font-size:11px;color:#64748b;margin-top:2px">${b.address}</div>` : ''}
      <div style="font-size:11px;color:#94a3b8;margin-top:4px;display:flex;gap:8px">
        <span>${b.floors} qavat</span><span>${b.entrances_count} kirish</span>
        ${b.organization_name ? `<span>${b.organization_name}</span>` : ''}
      </div>
      ${b.ext_sensor_temp_out != null ? `<div style="font-size:11px;color:#475569;margin-top:3px">${b.ext_sensor_temp_out}°C</div>` : ''}
    </div>`
  }

  useEffect(() => {
    if (!containerRef.current || !hasGoogleMapsKey()) return
    const center = buildings.find((b) => b.latitude && b.longitude)
    let cancelled = false

    loadGoogleMaps().then(() => {
      const container = containerRef.current
      if (!container || cancelled) return

      const map = new google.maps.Map(container, {
        center: center ? { lat: center.latitude!, lng: center.longitude! } : { lat: 41.55, lng: 60.64 },
        zoom: 13,
        mapId: 'smartbino_map',
        gestureHandling: 'greedy',
        disableDefaultUI: false,
        mapTypeControl: true,
        streetViewControl: false,
      })
      mapRef.current = map
      infoRef.current = new google.maps.InfoWindow()

      polygonsRef.current.forEach((p) => p.setMap(null))
      polygonsRef.current = []

      for (const b of buildings) {
        if (!b.polygon_coordinate) continue
        try {
          const coords = JSON.parse(b.polygon_coordinate)[0] as number[][]
          const paths = coords.map(([lat, lng]) => ({ lat, lng }))
          const color = STATUS_COLOR[getBuildingStatus(b)]

          const poly = new google.maps.Polygon({
            paths,
            map,
            strokeColor: color,
            strokeOpacity: 0.9,
            strokeWeight: 2,
            fillColor: color,
            fillOpacity: 0.15,
          })
          poly.addListener('click', (e: google.maps.PolyMouseEvent) => {
            onSelect?.(b.id)
            infoRef.current?.setContent(infoHtml(b))
            infoRef.current?.setPosition(e.latLng)
            infoRef.current?.open(map)
          })
          polygonsRef.current.push(poly)
        } catch {
          // Ignore invalid polygon data from imported records.
        }
      }

      markersRef.current.forEach((m) => {
        m.map = null
      })
      markersRef.current = []

      for (const b of buildings) {
        if (!b.latitude || !b.longitude) continue
        const color = STATUS_COLOR[getBuildingStatus(b)]
        const dot = document.createElement('div')
        dot.style.cssText = `width:11px;height:11px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 8px ${color}aa;cursor:pointer;transition:transform .15s`
        dot.onmouseenter = () => (dot.style.transform = 'scale(1.7)')
        dot.onmouseleave = () => (dot.style.transform = 'scale(1)')

        const marker = new google.maps.marker.AdvancedMarkerElement({
          map,
          position: { lat: b.latitude, lng: b.longitude },
          content: dot,
          title: b.name,
        })
        marker.addListener('click', () => {
          onSelect?.(b.id)
          infoRef.current?.setContent(infoHtml(b))
          infoRef.current?.open({ map, anchor: marker })
        })
        markersRef.current.push(marker)
      }
    })

    return () => {
      cancelled = true
      markersRef.current.forEach((m) => {
        m.map = null
      })
      polygonsRef.current.forEach((p) => p.setMap(null))
      markersRef.current = []
      polygonsRef.current = []
      mapRef.current = null
    }
  }, [buildings]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId) return
    const b = buildings.find((x) => x.id === selectedId)
    if (b) flyTo(b)
  }, [selectedId, buildings, flyTo])

  if (!hasGoogleMapsKey()) {
    return (
      <div className="flex items-center justify-center bg-gray-900/50 rounded-b-2xl text-sm text-gray-400 p-8" style={{ height }}>
        <div className="text-center">
          <p className="font-bold text-yellow-400 mb-1">VITE_GOOGLE_MAPS_KEY kerak</p>
          <code className="text-xs bg-gray-800 px-2 py-1 rounded text-gray-300">VITE_GOOGLE_MAPS_KEY=AIza...</code>
        </div>
      </div>
    )
  }

  return <div ref={containerRef} className="rounded-b-2xl overflow-hidden" style={{ height, width: '100%' }} />
}
