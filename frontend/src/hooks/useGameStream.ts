import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { getToken } from '../api/client'
import { eventSchema } from '../api/schemas'
import type { GameEvent, ViewMode } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { usePlaybackStore } from '../store/playback'

export type ConnectionState = 'connecting' | 'live' | 'reconnecting' | 'closed' | 'error'

class FatalStreamError extends Error {}

export function parseStreamEvent(data: string): GameEvent | null {
  if (!data.trim()) return null

  let content: unknown
  try {
    content = JSON.parse(data)
  } catch {
    console.warn('忽略无法解析的 SSE 消息')
    return null
  }

  const parsed = eventSchema.safeParse(content)
  if (!parsed.success) {
    console.warn('忽略不符合事件格式的 SSE 消息')
    return null
  }
  return parsed.data as GameEvent
}

export function useGameStream(gameId: string, view: ViewMode): ConnectionState {
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const queryClient = useQueryClient()
  const { logout } = useAuth()
  const initialize = usePlaybackStore((state) => state.initialize)
  const append = usePlaybackStore((state) => state.append)

  useEffect(() => {
    initialize(gameId, view)
    const controller = new AbortController()
    let retryAttempt = 0
    let lastEventId = '0'

    void fetchEventSource(`/api/v1/games/${gameId}/stream?view=${view}`, {
      signal: controller.signal,
      openWhenHidden: true,
      headers: {
        Authorization: `Bearer ${getToken() ?? ''}`,
        'Last-Event-ID': lastEventId,
      },
      async onopen(response) {
        if (response.status === 401) {
          logout()
          throw new FatalStreamError('unauthorized')
        }
        if (!response.ok) throw new Error(`stream_${response.status}`)
        retryAttempt = 0
        setConnection('live')
      },
      onmessage(message) {
        const event = parseStreamEvent(message.data)
        if (!event) return
        lastEventId = String(event.seq)
        append(event)
        if (
          [
            'game_started',
            'night_result',
            'vote_result',
            'roles_revealed',
            'game_finished',
          ].includes(event.type)
        ) {
          void queryClient.invalidateQueries({ queryKey: ['game', gameId, view] })
          void queryClient.invalidateQueries({ queryKey: ['games'] })
        }
      },
      onclose() {
        setConnection('closed')
      },
      onerror(error) {
        if (error instanceof FatalStreamError) throw error
        retryAttempt += 1
        setConnection('reconnecting')
        return Math.min(15_000, 1000 * 2 ** Math.min(retryAttempt - 1, 4))
      },
    }).catch((error: unknown) => {
      if (!controller.signal.aborted && !(error instanceof FatalStreamError)) {
        setConnection('error')
      }
    })

    return () => controller.abort()
  }, [append, gameId, initialize, logout, queryClient, view])

  return connection
}
