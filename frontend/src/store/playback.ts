import { create } from 'zustand'

import type { GameEvent, ViewMode } from '../api/types'

type Speed = 0.5 | 1 | 1.5 | 2

interface PlaybackState {
  streamKey: string
  events: GameEvent[]
  cursor: number
  playing: boolean
  speed: Speed
  initialize: (gameId: string, view: ViewMode) => void
  append: (event: GameEvent) => void
  setCursor: (cursor: number) => void
  setPlaying: (playing: boolean) => void
  setSpeed: (speed: Speed) => void
  restart: () => void
  jumpLatest: () => void
}

const storedSpeed = Number(localStorage.getItem('werewolf.playbackSpeed'))
const initialSpeed: Speed = [0.5, 1, 1.5, 2].includes(storedSpeed) ? (storedSpeed as Speed) : 1

export const usePlaybackStore = create<PlaybackState>((set) => ({
  streamKey: '',
  events: [],
  cursor: -1,
  playing: true,
  speed: initialSpeed,
  initialize(gameId, view) {
    const streamKey = `${gameId}:${view}`
    set((state) =>
      state.streamKey === streamKey ? state : { streamKey, events: [], cursor: -1, playing: true },
    )
  },
  append(event) {
    set((state) => {
      if (state.events.some((item) => item.seq === event.seq)) return state
      return { events: [...state.events, event].sort((a, b) => a.seq - b.seq) }
    })
  },
  setCursor(cursor) {
    set((state) => ({ cursor: Math.max(-1, Math.min(cursor, state.events.length - 1)) }))
  },
  setPlaying(playing) {
    set({ playing })
  },
  setSpeed(speed) {
    localStorage.setItem('werewolf.playbackSpeed', String(speed))
    set({ speed })
  },
  restart() {
    set({ cursor: -1, playing: true })
  },
  jumpLatest() {
    set((state) => ({ cursor: state.events.length - 1, playing: true }))
  },
}))

export function eventDelay(event: GameEvent | undefined, speed: number): number {
  if (!event) return 250
  if (event.type === 'speech') {
    const content = String(event.payload.content ?? '')
    return Math.max(1200, Math.min(6000, 700 + content.length * 32)) / speed
  }
  return 850 / speed
}
