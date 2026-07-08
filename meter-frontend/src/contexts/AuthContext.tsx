import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User } from '@/types/api'
import { decodeJWT, getTokenFromStorage, setTokenInStorage, removeTokenFromStorage } from '@/lib/auth'

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (token: string, user: User) => void
  logout: () => void
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Initialize from storage
  useEffect(() => {
    const storedToken = getTokenFromStorage()
    if (storedToken) {
      try {
        const decoded = decodeJWT(storedToken)
        if (decoded && decoded.sub && decoded.username) {
          setToken(storedToken)
          setUser({ id: decoded.sub, username: decoded.username, role: decoded.role, is_active: true })
        } else {
          removeTokenFromStorage()
        }
      } catch (error) {
        console.error('[v0] Failed to decode JWT:', error)
        removeTokenFromStorage()
      }
    }
    setIsLoading(false)
  }, [])

  const login = (newToken: string, newUser: User) => {
    setTokenInStorage(newToken)
    setToken(newToken)
    setUser(newUser)
  }

  const logout = () => {
    removeTokenFromStorage()
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        isAdmin: user?.role === 'admin' ?? false,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    console.warn('[v0] useAuth called outside AuthProvider, returning default context')
    return {
      user: null,
      token: null,
      isLoading: false,
      login: () => {},
      logout: () => {},
      isAdmin: false,
    }
  }
  return context
}
