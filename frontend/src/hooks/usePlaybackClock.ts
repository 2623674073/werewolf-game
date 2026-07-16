import { useEffect } from 'react'

import type { GameEvent } from '../api/types'
import { recordedDelay, usePlaybackStore } from '../store/playback'

interface TraceChunk {
  offsetMs: number
  delta: string
}

export function usePlaybackClock(): void {
  const { events, cursor, playing, speed, draft, setCursor, setReplayDraft } = usePlaybackStore()

  useEffect(() => {
    if (!playing || cursor >= events.length - 1) return
    if (cursor < 0) {
      const timer = window.setTimeout(() => setCursor(0), 0)
      return () => window.clearTimeout(timer)
    }

    const current = events[cursor]
    const next = events[cursor + 1]
    if (!current || !next) return
    const trace = next.type === 'speech' ? speechTrace(next) : []
    if (trace.length === 0) {
      const timer = window.setTimeout(
        () => setCursor(cursor + 1),
        recordedDelay(current, next, speed),
      )
      return () => window.clearTimeout(timer)
    }

    const timers: number[] = []
    const player = String(next.payload.player ?? '')
    const continuing = draft?.player === player && !draft.failed
    const resumeOffset = continuing ? draft.offsetMs : -streamLeadIn(current, next)
    let content = continuing ? draft.content : ''

    for (const chunk of trace) {
      if (chunk.offsetMs <= resumeOffset) continue
      timers.push(
        window.setTimeout(
          () => {
            content += chunk.delta
            setReplayDraft({ player, content, offsetMs: chunk.offsetMs, failed: false })
          },
          Math.max(0, (chunk.offsetMs - resumeOffset) / speed),
        ),
      )
    }

    const finalOffset = Math.max(trace.at(-1)?.offsetMs ?? 0, speechDuration(next))
    timers.push(
      window.setTimeout(
        () => {
          setReplayDraft(null)
          setCursor(cursor + 1)
        },
        Math.max(0, (finalOffset - resumeOffset) / speed),
      ),
    )
    return () => timers.forEach(window.clearTimeout)
  }, [cursor, draft, events, playing, setCursor, setReplayDraft, speed])
}

function speechTrace(event: GameEvent): TraceChunk[] {
  const value = event.payload.stream_trace
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const offsetMs = Number((item as Record<string, unknown>).offset_ms)
    const delta = (item as Record<string, unknown>).delta
    return Number.isFinite(offsetMs) && typeof delta === 'string'
      ? [{ offsetMs: Math.max(0, offsetMs), delta }]
      : []
  })
}

function streamLeadIn(current: GameEvent, speech: GameEvent): number {
  const started = Date.parse(String(speech.payload.stream_started_at ?? ''))
  const currentAt = Date.parse(current.created_at)
  return Number.isFinite(started) && Number.isFinite(currentAt)
    ? Math.max(0, started - currentAt)
    : 0
}

function speechDuration(speech: GameEvent): number {
  const started = Date.parse(String(speech.payload.stream_started_at ?? ''))
  const completed = Date.parse(speech.created_at)
  return Number.isFinite(started) && Number.isFinite(completed)
    ? Math.max(0, completed - started)
    : 0
}
