import { useEffect } from 'react'

import { eventDelay, usePlaybackStore } from '../store/playback'

export function usePlaybackClock(): void {
  const { events, cursor, playing, speed, setCursor } = usePlaybackStore()

  useEffect(() => {
    if (!playing || cursor >= events.length - 1) return
    const next = events[cursor + 1]
    const timer = window.setTimeout(() => setCursor(cursor + 1), eventDelay(next, speed))
    return () => window.clearTimeout(timer)
  }, [cursor, events, playing, setCursor, speed])
}
