import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Eye, EyeOff, LogOut, Radio, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { cancelGame, getGame } from '../api/client'
import type { ViewMode } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EventTimeline } from '../components/EventTimeline'
import { PlaybackControls } from '../components/PlaybackControls'
import { PlayerBoard } from '../components/PlayerBoard'
import { projectGame } from '../game/projection'
import { useGameStream } from '../hooks/useGameStream'
import { usePlaybackClock } from '../hooks/usePlaybackClock'
import { usePlaybackStore } from '../store/playback'

export function GamePage() {
  const { gameId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { logout } = useAuth()
  const [view, setViewState] = useState<ViewMode>(() =>
    localStorage.getItem('werewolf.view') === 'god' ? 'god' : 'public',
  )
  const gameQuery = useQuery({
    queryKey: ['game', gameId, view],
    queryFn: () => getGame(gameId, view),
    refetchInterval: 15_000,
  })
  const connection = useGameStream(gameId, view)
  usePlaybackClock()
  const { events, cursor } = usePlaybackStore()
  const projection = useMemo(
    () => (gameQuery.data ? projectGame(gameQuery.data, events, cursor) : null),
    [cursor, events, gameQuery.data],
  )
  const cancellation = useMutation({
    mutationFn: () => cancelGame(gameId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['game', gameId] })
      await queryClient.invalidateQueries({ queryKey: ['games'] })
    },
  })

  function setView(next: ViewMode) {
    localStorage.setItem('werewolf.view', next)
    setViewState(next)
  }
  if (gameQuery.isLoading) return <div className="full-loading">正在推开观战席的大门…</div>
  if (!gameQuery.data || !projection)
    return (
      <div className="full-loading error">
        未能找到这局推演。
        <button className="button ghost" onClick={() => navigate('/games')}>
          返回大厅
        </button>
      </div>
    )
  const game = gameQuery.data
  return (
    <main className={`game-page scene-${game.phase}`}>
      <header className="game-topbar">
        <button className="icon-button" onClick={() => navigate('/games')} aria-label="返回大厅">
          <ArrowLeft size={18} />
        </button>
        <div className="game-title">
          <span className="eyebrow">第 {game.id.slice(0, 8)} 号推演</span>
          <strong>
            {game.player_count} 人局 · 第 {game.round_number} 回合
          </strong>
        </div>
        <div className={`connection connection-${connection}`}>
          <Radio size={14} />
          {connectionLabel(connection)}
        </div>
        <div className="view-toggle" role="group" aria-label="观战视角">
          <button className={view === 'public' ? 'active' : ''} onClick={() => setView('public')}>
            <Eye size={15} />
            公开
          </button>
          <button className={view === 'god' ? 'active' : ''} onClick={() => setView('god')}>
            <EyeOff size={15} />
            全知
          </button>
        </div>
        {game.status === 'running' && (
          <ConfirmDialog
            trigger={
              <button className="button danger compact">
                <XCircle size={15} />
                取消对局
              </button>
            }
            title="终止本局推演？"
            description="运行中的 Agent 会话将被释放，对局会被标记为已取消。"
            confirmLabel="确认终止"
            onConfirm={() => cancellation.mutate()}
          />
        )}
        <button
          className="icon-button"
          onClick={() => {
            logout()
            navigate('/login')
          }}
          aria-label="退出"
        >
          <LogOut size={17} />
        </button>
      </header>
      <div className="game-workspace">
        <PlayerBoard
          players={game.players}
          projection={projection}
          phase={game.phase}
          round={game.round_number}
        />
        <EventTimeline events={projection.visibleEvents} />
      </div>
      <PlaybackControls />
    </main>
  )
}

function connectionLabel(state: string): string {
  return (
    {
      connecting: '正在接入',
      live: '实时连接',
      reconnecting: '正在重连',
      closed: '卷宗完整',
      error: '连接异常',
    }[state] ?? state
  )
}
