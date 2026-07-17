import { lazy, Suspense, type PropsWithChildren } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import { DesktopGuard } from './components/DesktopGuard'
const LoginPage = lazy(() =>
  import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })),
)
const GamesPage = lazy(() =>
  import('./pages/GamesPage').then((module) => ({ default: module.GamesPage })),
)
const GamePage = lazy(() =>
  import('./pages/GamePage').then((module) => ({ default: module.GamePage })),
)

function RequireAuth({ children }: PropsWithChildren) {
  const { authenticated } = useAuth()
  return authenticated ? children : <Navigate to="/login" replace />
}

export function App() {
  return (
    <DesktopGuard>
      <Suspense fallback={<div className="full-loading">正在展开群雄夜宴…</div>}>
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
      </Suspense>
    </DesktopGuard>
  )
}
