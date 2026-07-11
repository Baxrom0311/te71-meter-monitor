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
  mode?: '2d' | '3d'
  onModeChange?: (mode: '2d' | '3d') => void
}

function applyMapMode(map: google.maps.Map, mode: '2d' | '3d') {
  if (mode === '3d') {
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE)
    map.setTilt(45)
    map.setHeading(map.getHeading() || 55)
    map.setZoom(Math.max(map.getZoom() || 18, 18))
    return
  }

  map.setMapTypeId(google.maps.MapTypeId.ROADMAP)
  map.setTilt(0)
  map.setHeading(0)
}

export function GoogleBuildingsMap({
  buildings,
  selectedId,
  onSelect,
  height = '500px',
  mode = '2d',
  onModeChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markersRef = useRef<google.maps.marker.AdvancedMarkerElement[]>([])
  const polygonsRef = useRef<google.maps.Polygon[]>([])
  const infoRef = useRef<google.maps.InfoWindow | null>(null)

  const flyTo = useCallback((b: Building) => {
    if (!mapRef.current || !b.latitude || !b.longitude) return
    mapRef.current.panTo({ lat: b.latitude, lng: b.longitude })
    mapRef.current.setZoom(mode === '3d' ? 18 : 17)
  }, [mode])

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
        zoom: mode === '3d' ? 18 : 13,
        mapId: 'smartbino_map',
        gestureHandling: 'greedy',
        disableDefaultUI: false,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        rotateControl: true,
      })
      applyMapMode(map, mode)
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
    if (!mapRef.current) return
    applyMapMode(mapRef.current, mode)
    if (mode !== '3d') return

    const target =
      (selectedId ? buildings.find((b) => b.id === selectedId) : null) ??
      buildings.find((b) => b.latitude && b.longitude)
    if (target?.latitude && target.longitude) {
      mapRef.current.panTo({ lat: target.latitude, lng: target.longitude })
      mapRef.current.setZoom(18)
      window.setTimeout(() => {
        mapRef.current?.setTilt(45)
        mapRef.current?.setHeading(mapRef.current.getHeading() || 55)
      }, 250)
    }
  }, [mode, selectedId, buildings])

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

  const rotate = (delta: number) => {
    const map = mapRef.current
    if (!map) return
    map.setHeading(((map.getHeading() || 0) + delta + 360) % 360)
  }

  const pitch = (tilt: number) => {
    const map = mapRef.current
    if (!map) return
    map.setTilt(tilt)
  }

  return (
    <div className="relative rounded-b-2xl overflow-hidden" style={{ height, width: '100%' }}>
      <div ref={containerRef} className="absolute inset-0" />

      <div className="absolute left-4 top-4 z-10 flex items-center overflow-hidden rounded-xl border border-gray-800/70 bg-gray-950/90 p-1 shadow-2xl backdrop-blur">
        <button
          type="button"
          onClick={() => onModeChange?.('2d')}
          className={`px-3 py-1.5 text-xs font-black transition ${mode === '2d' ? 'rounded-lg bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
        >
          2D
        </button>
        <button
          type="button"
          onClick={() => onModeChange?.('3d')}
          className={`px-3 py-1.5 text-xs font-black transition ${mode === '3d' ? 'rounded-lg bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
        >
          3D
        </button>
      </div>

      {mode === '3d' && (
        <div className="absolute right-4 top-4 z-10 flex flex-col gap-2">
          <div className="flex overflow-hidden rounded-xl border border-gray-800/70 bg-gray-950/90 p-1 shadow-2xl backdrop-blur">
            <button type="button" onClick={() => rotate(-35)} className="px-3 py-1.5 text-xs font-black text-gray-200 hover:bg-gray-800 rounded-lg">
              Chap
            </button>
            <button type="button" onClick={() => rotate(35)} className="px-3 py-1.5 text-xs font-black text-gray-200 hover:bg-gray-800 rounded-lg">
              O'ng
            </button>
          </div>
          <div className="flex overflow-hidden rounded-xl border border-gray-800/70 bg-gray-950/90 p-1 shadow-2xl backdrop-blur">
            <button type="button" onClick={() => pitch(0)} className="px-3 py-1.5 text-xs font-black text-gray-200 hover:bg-gray-800 rounded-lg">
              Tekis
            </button>
            <button type="button" onClick={() => pitch(45)} className="px-3 py-1.5 text-xs font-black text-gray-200 hover:bg-gray-800 rounded-lg">
              Qiya
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
