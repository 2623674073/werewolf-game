import { gameReviewSchema, gameSchema, sessionSchema } from './schemas'
import type { ApiErrorBody, Game, GameReview, Session, ViewMode } from './types'

export const TOKEN_KEY = 'werewolf.apiToken'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message)
  }
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    let body: ApiErrorBody = {}
    try {
      body = (await response.json()) as ApiErrorBody
    } catch {
      // Non-JSON proxy errors are normalized here.
    }
    throw new ApiError(
      response.status,
      body.error?.code ?? 'request_failed',
      body.error?.message ?? `请求失败（${response.status}）`,
      body.error?.request_id,
    )
  }
  return (await response.json()) as T
}

export async function validateSession(): Promise<Session> {
  return sessionSchema.parse(await request<unknown>('/api/v1/session'))
}

export async function listGames(offset = 0, limit = 20): Promise<Game[]> {
  return gameSchema
    .array()
    .parse(await request<unknown>(`/api/v1/games?offset=${offset}&limit=${limit}`))
}

export async function createGame(playerCount: number): Promise<Game> {
  return gameSchema.parse(
    await request<unknown>('/api/v1/games', {
      method: 'POST',
      body: JSON.stringify({ player_count: playerCount }),
    }),
  )
}

export async function startGame(gameId: string): Promise<Game> {
  return gameSchema.parse(
    await request<unknown>(`/api/v1/games/${gameId}/start`, { method: 'POST' }),
  )
}

export async function cancelGame(gameId: string): Promise<Game> {
  return gameSchema.parse(
    await request<unknown>(`/api/v1/games/${gameId}/cancel`, { method: 'POST' }),
  )
}

export async function getGame(gameId: string, view: ViewMode): Promise<Game> {
  return gameSchema.parse(await request<unknown>(`/api/v1/games/${gameId}?view=${view}`))
}

export async function getGameReview(gameId: string): Promise<GameReview> {
  return gameReviewSchema.parse(
    await request<unknown>(`/api/v1/games/${gameId}/review`),
  ) as GameReview
}

export async function createGameReview(gameId: string): Promise<GameReview> {
  return gameReviewSchema.parse(
    await request<unknown>(`/api/v1/games/${gameId}/review`, {
      method: 'POST',
    }),
  ) as GameReview
}
