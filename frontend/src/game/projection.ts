import type { Game, GameEvent } from '../api/types'

export interface GameProjection {
  visibleEvents: GameEvent[]
  alive: Map<string, boolean>
  roles: Map<string, string>
  currentSpeaker: string | null
  currentSpeech: string | null
}

export function projectGame(game: Game, events: GameEvent[], cursor: number): GameProjection {
  const visibleEvents = events.slice(0, cursor + 1)
  const hasTimelineStart = visibleEvents.some((event) => event.type === 'game_started')
  const alive = new Map(
    game.players.map((player) => [player.name, hasTimelineStart || player.is_alive]),
  )
  const roles = new Map<string, string>()

  for (const player of game.players) {
    if (player.role) roles.set(player.name, player.role)
  }
  let currentSpeaker: string | null = null
  let currentSpeech: string | null = null

  for (const event of visibleEvents) {
    if (event.type === 'roles_revealed') {
      for (const item of arrayObjects(event.payload.players)) {
        if (typeof item.player === 'string' && typeof item.role === 'string') {
          roles.set(item.player, item.role)
        }
      }
    }
    if (event.type === 'speaker_turn_started') {
      currentSpeaker = text(event.payload.player)
      currentSpeech = null
    }
    if (event.type === 'speech') {
      currentSpeaker = text(event.payload.player)
      currentSpeech = text(event.payload.content)
    }
    if (event.type === 'night_result') {
      for (const name of strings(event.payload.deaths)) alive.set(name, false)
      currentSpeaker = null
      currentSpeech = null
    }
    if (event.type === 'vote_result') {
      const votedOut = text(event.payload.voted_out)
      const hunterShot = text(event.payload.hunter_shot)
      if (votedOut) alive.set(votedOut, false)
      if (hunterShot) alive.set(hunterShot, false)
      currentSpeaker = null
      currentSpeech = null
    }
  }
  return { visibleEvents, alive, roles, currentSpeaker, currentSpeech }
}

export function text(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

export function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

export function arrayObjects(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => typeof item === 'object' && item !== null,
      )
    : []
}
