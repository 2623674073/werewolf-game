import { beforeEach, describe, expect, it } from 'vitest'

import type { GameEvent } from '../api/types'
import { eventDelay, usePlaybackStore } from './playback'

function event(
  seq: number,
  type = 'day_started',
  payload: Record<string, unknown> = {},
): GameEvent {
  return {
    game_id: 'g',
    seq,
    type,
    phase: 'day',
    visibility: 'public',
    recipients: [],
    payload,
    created_at: '',
  } as GameEvent
}

describe('playback store', () => {
  beforeEach(() =>
    usePlaybackStore.setState({
      streamKey: '',
      events: [],
      cursor: -1,
      playing: true,
      speed: 1,
    }),
  )

  it('initializes per view, sorts and deduplicates events', () => {
    const store = usePlaybackStore.getState()
    store.initialize('g', 'public')
    store.append(event(2))
    store.append(event(1))
    store.append(event(2))
    expect(usePlaybackStore.getState().events.map((item) => item.seq)).toEqual([1, 2])
    usePlaybackStore.getState().setCursor(99)
    expect(usePlaybackStore.getState().cursor).toBe(1)
    usePlaybackStore.getState().initialize('g', 'god')
    expect(usePlaybackStore.getState().events).toEqual([])
  })

  it('supports speed, restart and jump-to-latest controls', () => {
    const store = usePlaybackStore.getState()
    store.append(event(1))
    store.append(event(2))
    store.jumpLatest()
    expect(usePlaybackStore.getState().cursor).toBe(1)
    usePlaybackStore.getState().setSpeed(2)
    expect(localStorage.getItem('werewolf.playbackSpeed')).toBe('2')
    usePlaybackStore.getState().restart()
    expect(usePlaybackStore.getState()).toMatchObject({ cursor: -1, playing: true })
    usePlaybackStore.getState().setPlaying(false)
    expect(usePlaybackStore.getState().playing).toBe(false)
  })
})

describe('eventDelay', () => {
  it('uses bounded speech duration and scales by speed', () => {
    expect(eventDelay(undefined, 1)).toBe(250)
    expect(eventDelay(event(1), 1)).toBe(850)
    expect(eventDelay(event(1, 'speech', { content: '短句' }), 2)).toBe(600)
    expect(eventDelay(event(1, 'speech', { content: '字'.repeat(500) }), 1)).toBe(6000)
  })
})
