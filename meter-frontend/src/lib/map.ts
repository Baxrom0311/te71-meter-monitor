export interface Coordinates {
  latitude: number
  longitude: number
}

function validCoordinates(latitude: number, longitude: number): Coordinates | null {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
  return { latitude, longitude }
}

export function coordinatesFromMapsUrl(url?: string | null): Coordinates | null {
  if (!url) return null
  const value = url.trim()
  const patterns = [
    /@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/,
    /[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/,
    /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/,
    /\/place\/(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/,
  ]
  for (const pattern of patterns) {
    const match = value.match(pattern)
    if (!match) continue
    const coordinates = validCoordinates(Number(match[1]), Number(match[2]))
    if (coordinates) return coordinates
  }
  return null
}

export function resolveCoordinates(
  latitude?: number | null,
  longitude?: number | null,
  mapsUrl?: string | null,
): Coordinates | null {
  if (latitude != null && longitude != null) {
    return validCoordinates(latitude, longitude)
  }
  return coordinatesFromMapsUrl(mapsUrl)
}

export function osmEmbedUrl(coordinates: Coordinates, zoom = 17) {
  const delta = zoom >= 17 ? 0.004 : 0.01
  const left = coordinates.longitude - delta
  const right = coordinates.longitude + delta
  const bottom = coordinates.latitude - delta
  const top = coordinates.latitude + delta
  const marker = `${coordinates.latitude},${coordinates.longitude}`
  return `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${marker}`
}
