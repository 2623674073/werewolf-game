import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { GameEvent } from '../api/types'
import { usePlaybackStore } from '../store/playback'
import { usePlaybackClock } from './usePlaybackClock'

function event(
  seq: number,
  type: string,
  createdAt: string,
  payload: Record<string, unknown> = {},
): GameEvent {
  return {
    game_id: 'game-1',
    seq,
    type,
    phase: 'day',
    visibility: 'public',
    recipients: [],
    payload,
    created_at: createdAt,
  } as GameEvent
}

describe('usePlaybackClock', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    usePlaybackStore.setState({
      streamKey: 'game-1:public',
      events: [],
      cursor: -1,
      playing: true,
      speed: 1,
      draft: null,
    })
  })

  afterEach(() => vi.useRealTimers())

  it('replays durable events using their original interval', () => {
    usePlaybackStore.setState({
      events: [
        event(1, 'day_started', '2026-01-01T00:00:00Z'),
        event(2, 'vote_result', '2026-01-01T00:00:01Z'),
      ],
      cursor: 0,
      speed: 2,
    })
    renderHook(() => usePlaybackClock())

    act(() => vi.advanceTimersByTime(499))
    expect(usePlaybackStore.getState().cursor).toBe(0)
    act(() => vi.advanceTimersByTime(1))
    expect(usePlaybackStore.getState().cursor).toBe(1)
  })

  it('reconstructs a speech from its recorded stream trace', () => {
    usePlaybackStore.setState({
      events: [
        event(1, 'speaker_turn_started', '2026-01-01T00:00:00Z', { player: '刘备' }),
        event(2, 'speech', '2026-01-01T00:00:01Z', {
          player: '刘备',
          content: '曹操可疑',
          stream_started_at: '2026-01-01T00:00:00.200Z',
          stream_trace: [
            { offset_ms: 0, delta: '曹操' },
            { offset_ms: 300, delta: '可疑' },
          ],
        }),
      ],
      cursor: 0,
    })
    renderHook(() => usePlaybackClock())

    act(() => vi.advanceTimersByTime(199))
    expect(usePlaybackStore.getState().draft).toBeNull()
    act(() => vi.advanceTimersByTime(1))
    expect(usePlaybackStore.getState().draft?.content).toBe('曹操')
    act(() => vi.advanceTimersByTime(300))
    expect(usePlaybackStore.getState().draft?.content).toBe('曹操可疑')
    act(() => vi.advanceTimersByTime(500))
    expect(usePlaybackStore.getState()).toMatchObject({ cursor: 1, draft: null })
  })
})
