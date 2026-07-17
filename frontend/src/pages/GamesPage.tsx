import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { InfiniteData } from '@tanstack/react-query'
import { ArrowRight, LogOut, Play, Plus, RefreshCw, Swords, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, createGame, deleteGame, listGames, startGame } from '../api/client'
import type { Game, GameStatus } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { RuntimeBadge } from '../components/RuntimeBadge'

const PAGE_SIZE = 20

export function GamesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { logout } = useAuth()
  const [playerCount, setPlayerCount] = useState(6)
  const [filter, setFilter] = useState<GameStatus | 'all'>('all')
  const [notice, setNotice] = useState('')
  const gamesQuery = useInfiniteQuery({
    queryKey: ['games'],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listGames(pageParam, PAGE_SIZE),
    getNextPageParam: (last, pages) =>
      last.length === PAGE_SIZE ? pages.length * PAGE_SIZE : undefined,
  })
  const games = useMemo(() => gamesQuery.data?.pages.flat() ?? [], [gamesQuery.data])
  const filtered = filter === 'all' ? games : games.filter((game) => game.status === filter)

  const launch = useMutation({
    mutationFn: async () => {
      const created = await createGame(playerCount)
      try {
        return { game: await startGame(created.id), started: true }
      } catch (error) {
        return { game: created, started: false, error }
      }
    },
    onSuccess(result) {
      void queryClient.invalidateQueries({ queryKey: ['games'] })
      if (result.started) navigate(`/games/${result.game.id}`)
      else setNotice(`对局已创建，但启动失败：${errorText(result.error)}`)
    },
    onError(error) {
      setNotice(errorText(error))
    },
  })
  const deletion = useMutation({
    mutationFn: (gameId: string) => deleteGame(gameId),
    onSuccess: async (_, gameId) => {
      queryClient.setQueryData<InfiniteData<Game[]>>(['games'], (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => page.filter((game) => game.id !== gameId)),
            }
          : current,
      )
      await queryClient.invalidateQueries({ queryKey: ['games'] })
      setNotice('对局卷宗已永久删除。')
    },
    onError(error) {
      setNotice(errorText(error))
    },
  })

  async function retry(game: Game) {
    setNotice('')
    try {
      await startGame(game.id)
      await queryClient.invalidateQueries({ queryKey: ['games'] })
      navigate(`/games/${game.id}`)
    } catch (error) {
      setNotice(errorText(error))
    }
  }

  return (
    <main className="lobby-page">
      <header className="topbar">
        <div className="brand">
          <span className="seal">弈</span>
          <div>
            <strong>群雄夜宴</strong>
            <span>AI WEREWOLF OBSERVATORY</span>
          </div>
        </div>
        <RuntimeBadge />
        <button
          className="button ghost"
          onClick={() => {
            logout()
            navigate('/login')
          }}
        >
          <LogOut size={16} />
          退席
        </button>
      </header>
      <section className="lobby-hero">
        <div>
          <span className="eyebrow">对局司天台</span>
          <h1>今夜，谁在说谎？</h1>
          <p>创建一局全自动 AI 狼人杀，实时旁观每一次发言与暗中抉择。</p>
        </div>
        <div className="create-panel">
          <label>
            <span>入局人数</span>
            <select
              value={playerCount}
              onChange={(event) => setPlayerCount(Number(event.target.value))}
            >
              {Array.from({ length: 7 }, (_, index) => index + 6).map((count) => (
                <option key={count} value={count}>
                  {count} 位群雄
                </option>
              ))}
            </select>
          </label>
          <button
            className="button primary"
            disabled={launch.isPending}
            onClick={() => launch.mutate()}
          >
            <Plus size={18} />
            {launch.isPending ? '正在布阵…' : '一键开局'}
          </button>
        </div>
      </section>
      {notice && <div className="notice">{notice}</div>}
      <section className="games-section">
        <header>
          <div>
            <span className="eyebrow">历史卷宗</span>
            <h2>对局列表</h2>
          </div>
          <div className="filters">
            <select
              value={filter}
              onChange={(event) => setFilter(event.target.value as GameStatus | 'all')}
            >
              <option value="all">全部状态</option>
              <option value="running">进行中</option>
              <option value="created">待启动</option>
              <option value="completed">已完成</option>
              <option value="draw">平局</option>
              <option value="failed">异常</option>
            </select>
            <button
              className="icon-button"
              onClick={() => void gamesQuery.refetch()}
              aria-label="刷新"
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>
        {gamesQuery.isLoading ? (
          <div className="loading-state">正在展开卷宗…</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <Swords size={38} />
            <h3>尚无对局</h3>
            <p>选择人数，开启今夜第一场推演。</p>
          </div>
        ) : (
          <div className="games-grid">
            {filtered.map((game) => (
              <GameCard
                key={game.id}
                game={game}
                onOpen={() => navigate(`/games/${game.id}`)}
                onStart={() => void retry(game)}
                onDelete={() => deletion.mutate(game.id)}
                deleting={deletion.isPending && deletion.variables === game.id}
              />
            ))}
          </div>
        )}
        {gamesQuery.hasNextPage && (
          <button
            className="button ghost load-more"
            onClick={() => void gamesQuery.fetchNextPage()}
          >
            载入更多卷宗
          </button>
        )}
      </section>
    </main>
  )
}

export function GameCard({
  game,
  onOpen,
  onStart,
  onDelete,
  deleting,
}: {
  game: Game
  onOpen: () => void
  onStart: () => void
  onDelete: () => void
  deleting: boolean
}) {
  const deletable = isDeletable(game.status)
  return (
    <article className="game-card">
      <div className="game-card-art">
        <span>{game.player_count}</span>
        <small>位群雄</small>
      </div>
      <div className="game-card-copy">
        <div className="card-row">
          <span className={`status status-${game.status}`}>{statusLabel(game.status)}</span>
          <time>
            {new Date(game.created_at).toLocaleString('zh-CN', {
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </time>
        </div>
        <h3>第 {game.id.slice(0, 8)} 号推演</h3>
        <p>
          第 {game.round_number} 回合 · {phaseLabel(game.phase)}
          {game.winner ? ` · ${winnerLabel(game.winner)}` : ''}
        </p>
        <div className="card-actions">
          <button className="card-action" onClick={game.status === 'created' ? onStart : onOpen}>
            {game.status === 'created' ? (
              <>
                <Play size={16} />
                继续启动
              </>
            ) : (
              <>
                进入观战
                <ArrowRight size={16} />
              </>
            )}
          </button>
          {deletable && (
            <ConfirmDialog
              trigger={
                <button
                  className="card-delete"
                  disabled={deleting}
                  aria-label={`删除第 ${game.id.slice(0, 8)} 号推演`}
                >
                  <Trash2 size={15} />
                </button>
              }
              title="永久删除这局推演？"
              description="本局对话、身份、技能事件和史官复盘都会被永久删除，且无法恢复。"
              confirmLabel="永久删除"
              onConfirm={onDelete}
            />
          )}
        </div>
      </div>
    </article>
  )
}

function isDeletable(status: GameStatus): boolean {
  return ['completed', 'draw', 'cancelled', 'interrupted', 'failed'].includes(status)
}

function statusLabel(status: GameStatus): string {
  return {
    created: '待启动',
    running: '推演中',
    completed: '已分胜负',
    draw: '平局',
    cancelled: '已取消',
    interrupted: '已中断',
    failed: '异常',
  }[status]
}
function phaseLabel(phase: string): string {
  return { setup: '布阵', night: '夜晚', day: '白昼', finished: '终局' }[phase] ?? phase
}
function winnerLabel(winner: string): string {
  return { villagers: '好人胜', werewolves: '狼人胜', draw: '平局' }[winner] ?? winner
}
function errorText(error: unknown): string {
  return error instanceof ApiError
    ? `${error.message}${error.requestId ? `（${error.requestId}）` : ''}`
    : '服务暂时不可用'
}
