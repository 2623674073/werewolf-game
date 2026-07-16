import { Navigate, Route, Routes } from 'react-router-dom'
import type { PropsWithChildren } from 'react'

import { useAuth } from './auth/AuthContext'
import { DesktopGuard } from './components/DesktopGuard'
import { GamePage } from './pages/GamePage'
import { GamesPage } from './pages/GamesPage'
import { LoginPage } from './pages/LoginPage'

function RequireAuth({ children }: PropsWithChildren) {
  const { authenticated } = useAuth()
  return authenticated ? children : <Navigate to="/login" replace />
}

export function App() {
  return (
    <DesktopGuard>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/games"
          element={
            <RequireAuth>
              <GamesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/games/:gameId"
          element={
            <RequireAuth>
              <GamePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/games" replace />} />
      </Routes>
    </DesktopGuard>
  )
}
