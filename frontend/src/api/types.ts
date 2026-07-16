import type { components } from './generated'

export type Game = components['schemas']['GameResponse']
export type Player = components['schemas']['PlayerResponse']
export type Session = components['schemas']['SessionResponse']
export type GameReview = components['schemas']['GameReviewResponse']
export type ViewMode = 'public' | 'god'
export type GameStatus = Game['status']

export type GameEvent = Omit<components['schemas']['EventResponse'], 'payload'> & {
  payload: Record<string, unknown>
}

export interface ApiErrorBody {
  error?: { code?: string; message?: string; request_id?: string }
}
