import { describe, expect, it } from 'vitest'

import type { Game, GameEvent } from '../api/types'
import { arrayObjects, projectGame, strings, text } from './projection'

const game: Game = {
  id: 'game-1',
  player_count: 2,
  status: 'running',
  phase: 'day',
  round_number: 1,
  players: [
    { name: '刘备', character: '刘备', is_alive: false },
    { name: '曹操', character: '曹操', is_alive: true },
  ],
  winner: null,
  error_code: null,
  created_at: '2026-01-01T00:00:00Z',
  started_at: null,
  finished_at: null,
}

function event(seq: number, type: string, payload: Record<string, unknown>): GameEvent {
  return {
    game_id: 'game-1',
    seq,
    type,
    phase: 'day',
    visibility: 'public',
    recipients: [],
    payload,
    created_at: '2026-01-01T00:00:00Z',
  } as GameEvent
}

describe('projectGame', () => {
  it('replays speakers, deaths and role reveal up to the cursor', () => {
    const events = [
      event(1, 'game_started', { players: ['刘备', '曹操'] }),
      event(2, 'speaker_turn_started', { player: '刘备' }),
      event(3, 'speech', { player: '刘备', content: '曹操可疑' }),
      event(4, 'vote_result', { voted_out: '刘备', votes: 1, hunter_shot: null }),
      event(5, 'roles_revealed', {
        players: [
          { player: '刘备', role: '预言家' },
          { player: '曹操', role: '狼人' },
        ],
      }),
    ]
    const speaking = projectGame(game, events, 2)
    expect(speaking.alive.get('刘备')).toBe(true)
    expect(speaking.currentSpeaker).toBe('刘备')
    expect(speaking.speechPlayer).toBe('刘备')
    expect(speaking.currentSpeech).toBe('曹操可疑')

    const finished = projectGame(game, events, 4)
    expect(finished.alive.get('刘备')).toBe(false)
    expect(finished.roles.get('曹操')).toBe('狼人')
    expect(finished.visibleEvents).toHaveLength(5)
  })

  it('keeps the previous completed speech while the next player is thinking', () => {
    const events = [
      event(1, 'speech', { player: '刘备', content: '先听我说' }),
      event(2, 'speaker_turn_started', { player: '曹操' }),
    ]
    const projection = projectGame(game, events, 1)
    expect(projection.currentSpeaker).toBe('曹操')
    expect(projection.speechPlayer).toBe('刘备')
    expect(projection.currentSpeech).toBe('先听我说')
  })

  it('uses snapshot state when history has no start event and applies night deaths', () => {
    const projection = projectGame(game, [event(1, 'night_result', { deaths: ['曹操'] })], 0)
    expect(projection.alive.get('刘备')).toBe(false)
    expect(projection.alive.get('曹操')).toBe(false)
  })
})

describe('projection guards', () => {
  it('normalizes unknown payload values', () => {
    expect(text('刘备')).toBe('刘备')
    expect(text('')).toBeNull()
    expect(strings(['刘备', 1, null])).toEqual(['刘备'])
    expect(arrayObjects([{ player: '刘备' }, null, 'bad'])).toEqual([{ player: '刘备' }])
  })
})
