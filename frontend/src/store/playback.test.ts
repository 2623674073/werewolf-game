import { beforeEach, describe, expect, it } from 'vitest'

import type { GameEvent } from '../api/types'
import { recordedDelay, usePlaybackStore } from './playback'

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
    created_at: `2026-01-01T00:00:0${seq}Z`,
  } as GameEvent
}

beforeEach(() =>
  usePlaybackStore.setState({
    streamKey: '',
    events: [],
    cursor: -1,
    playing: true,
    speed: 1,
    draft: null,
  }),
)

describe('playback store', () => {
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

describe('recordedDelay', () => {
  it('uses the original event interval and only scales historical playback', () => {
    expect(recordedDelay(undefined, event(1), 1)).toBe(0)
    expect(recordedDelay(event(1), event(2), 1)).toBe(1000)
    expect(recordedDelay(event(1), event(2), 2)).toBe(500)
  })

  it('keeps transient speech outside the durable event list', () => {
    const store = usePlaybackStore.getState()
    store.applyStreamFrame({
      game_id: 'g',
      type: 'speech_delta',
      phase: 'day',
      visibility: 'public',
      recipients: [],
      payload: { player: '刘备', content_so_far: '曹操可疑', offset_ms: 80 },
      created_at: '',
    })
    expect(usePlaybackStore.getState().draft?.content).toBe('曹操可疑')
    expect(usePlaybackStore.getState().events).toEqual([])

    store.append(event(1, 'speech', { player: '刘备', content: '曹操可疑' }))
    expect(usePlaybackStore.getState()).toMatchObject({ cursor: 0, draft: null })
  })

  it('freezes the visible draft while paused as durable events continue arriving', () => {
    const store = usePlaybackStore.getState()
    store.append(event(1, 'speaker_turn_started', { player: '刘备' }))
    store.applyStreamFrame({
      game_id: 'g',
      type: 'speech_delta',
      phase: 'day',
      visibility: 'public',
      recipients: [],
      payload: { player: '刘备', content_so_far: '半句', offset_ms: 100 },
      created_at: '',
    })
    store.setPlaying(false)
    store.append(event(2, 'speech', { player: '刘备', content: '完整发言' }))

    expect(usePlaybackStore.getState()).toMatchObject({
      cursor: 0,
      playing: false,
      draft: { content: '半句', offsetMs: 100 },
    })
  })
})
