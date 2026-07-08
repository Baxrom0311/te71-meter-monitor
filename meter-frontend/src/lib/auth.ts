const TOKEN_KEY = 'mm_token'

export function decodeJWT(token: string) {
  try {
    const parts = token.split('.')
    // Standard JWT: header.payload.signature (3 parts)
    // Backend custom format: base64payload.signature (2 parts)
    if (parts.length < 2) return null
    const payloadPart = parts.length === 3 ? parts[1] : parts[0]
    // Fix base64 padding
    const padded = payloadPart.replace(/-/g, '+').replace(/_/g, '/')
    const decoded = JSON.parse(atob(padded))
    return decoded
  } catch (error) {
    console.error('[v0] Error decoding JWT:', error)
    return null
  }
}

export function getTokenFromStorage(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setTokenInStorage(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeTokenFromStorage(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function isTokenExpired(token: string): boolean {
  const decoded = decodeJWT(token)
  if (!decoded || !decoded.exp) return true

  const expirationTime = decoded.exp * 1000 // Convert to milliseconds
  return Date.now() >= expirationTime
}
