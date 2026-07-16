/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useMemo, useState, type PropsWithChildren } from 'react'

import { clearToken, getToken, setToken as persistToken } from '../api/client'

interface AuthValue {
  authenticated: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [authenticated, setAuthenticated] = useState(() => Boolean(getToken()))
  const value = useMemo<AuthValue>(
    () => ({
      authenticated,
      login(token) {
        persistToken(token)
        setAuthenticated(true)
      },
      logout() {
        clearToken()
        setAuthenticated(false)
      },
    }),
    [authenticated],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is missing')
  return value
}
