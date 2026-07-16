import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { PropsWithChildren } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthContext'
import { usePlaybackStore } from '../store/playback'
import { parseStreamEvent, useGameStream } from './useGameStream'

const fetchEventSourceMock = vi.hoisted(() => vi.fn())

vi.mock('@microsoft/fetch-event-source', () => ({
  fetchEventSource: fetchEventSourceMock,
}))

const event = {
  game_id: 'game-1',
  seq: 1,
  type: 'day_started',
  phase: 'day',
  visibility: 'public',
  recipients: [],
  payload: { round: 1 },
  created_at: '2026-07-16T00:00:00Z',
}

const delta = {
  game_id: 'game-1',
  type: 'speech_delta',
  phase: 'day',
  visibility: 'public',
  recipients: [],
  payload: { player: '刘备', content_so_far: '曹操', offset_ms: 120 },
  created_at: '2026-07-16T00:00:00Z',
}

beforeEach(() => vi.restoreAllMocks())

describe('parseStreamEvent', () => {
  it('ignores empty SSE heartbeat frames without parsing JSON', () => {
    const parseSpy = vi.spyOn(JSON, 'parse')

    expect(parseStreamEvent('')).toBeNull()
    expect(parseStreamEvent('   ')).toBeNull()
    expect(parseSpy).not.toHaveBeenCalled()
  })

  it('parses valid events and ignores malformed frames without exposing their data', () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)

    expect(parseStreamEvent(JSON.stringify(event))).toEqual(event)
    expect(parseStreamEvent(JSON.stringify(delta))).toEqual(delta)
    expect(parseStreamEvent('{invalid')).toBeNull()
    expect(parseStreamEvent(JSON.stringify({ seq: 1 }))).toBeNull()
    expect(warning).toHaveBeenNthCalledWith(1, '忽略无法解析的 SSE 消息')
    expect(warning).toHaveBeenNthCalledWith(2, '忽略不符合事件格式的 SSE 消息')
  })
})

describe('useGameStream', () => {
  let options: FetchEventSourceInit

  beforeEach(() => {
    fetchEventSourceMock.mockReset()
    fetchEventSourceMock.mockImplementation(
      (_input: RequestInfo, nextOptions: FetchEventSourceInit) => {
        options = nextOptions
        return new Promise<void>(() => undefined)
      },
    )
    usePlaybackStore.setState({
      streamKey: '',
      events: [],
      cursor: -1,
      playing: true,
      draft: null,
    })
  })

  it('keeps the connection live for heartbeat and malformed message frames', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const { result } = renderHook(() => useGameStream('game-1', 'public'), {
      wrapper: createWrapper(),
    })

    await act(async () => options.onopen?.(new Response(null, { status: 200 })))
    expect(result.current).toBe('live')

    act(() => options.onmessage?.({ data: '', event: '', id: '', retry: undefined }))
    act(() => options.onmessage?.({ data: '{invalid', event: '', id: '', retry: undefined }))

    expect(result.current).toBe('live')
    expect(usePlaybackStore.getState().events).toEqual([])
    expect(warning).toHaveBeenCalledTimes(1)
  })

  it('appends valid events and reconnects only after a real stream error', async () => {
    const { result } = renderHook(() => useGameStream('game-1', 'god'), {
      wrapper: createWrapper(),
    })

    await act(async () => options.onopen?.(new Response(null, { status: 200 })))
    act(() =>
      options.onmessage?.({
        data: JSON.stringify(event),
        event: event.type,
        id: String(event.seq),
        retry: undefined,
      }),
    )
    expect(usePlaybackStore.getState().events).toEqual([event])
    expect(result.current).toBe('live')

    let retryDelay: number | null | undefined | void
    act(() => {
      retryDelay = options.onerror?.(new TypeError('network disconnected'))
    })
    expect(result.current).toBe('reconnecting')
    expect(retryDelay).toBe(1000)
  })

  it('applies transient speech without persisting it or advancing the event id', async () => {
    renderHook(() => useGameStream('game-1', 'public'), { wrapper: createWrapper() })
    await act(async () => options.onopen?.(new Response(null, { status: 200 })))
    act(() =>
      options.onmessage?.({
        data: JSON.stringify(delta),
        event: delta.type,
        id: '',
        retry: undefined,
      }),
    )
    expect(usePlaybackStore.getState().events).toEqual([])
    expect(usePlaybackStore.getState().draft).toMatchObject({
      player: '刘备',
      content: '曹操',
      offsetMs: 120,
    })
  })

  it('marks a normally completed event stream as closed', async () => {
    const { result } = renderHook(() => useGameStream('game-1', 'public'), {
      wrapper: createWrapper(),
    })

    await act(async () => options.onopen?.(new Response(null, { status: 200 })))
    act(() => options.onclose?.())

    expect(result.current).toBe('closed')
  })
})

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    )
  }
}
