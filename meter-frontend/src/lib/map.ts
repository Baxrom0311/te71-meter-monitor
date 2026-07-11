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

