import { create } from 'zustand'

import type { GameEvent, SpeechStreamFrame, ViewMode } from '../api/types'

type Speed = 0.5 | 1 | 1.5 | 2

interface PlaybackState {
  streamKey: string
  events: GameEvent[]
  cursor: number
  playing: boolean
  speed: Speed
  draft: SpeechDraft | null
  initialize: (gameId: string, view: ViewMode) => void
  append: (event: GameEvent) => void
  applyStreamFrame: (frame: SpeechStreamFrame) => void
  setReplayDraft: (draft: SpeechDraft | null) => void
  setCursor: (cursor: number) => void
  setPlaying: (playing: boolean) => void
  setSpeed: (speed: Speed) => void
  restart: () => void
  jumpLatest: () => void
}

export interface SpeechDraft {
  player: string
  content: string
  offsetMs: number
  failed: boolean
}

const storedSpeed = Number(localStorage.getItem('werewolf.playbackSpeed'))
const initialSpeed: Speed = [0.5, 1, 1.5, 2].includes(storedSpeed) ? (storedSpeed as Speed) : 1

export const usePlaybackStore = create<PlaybackState>((set) => ({
  streamKey: '',
  events: [],
  cursor: -1,
  playing: true,
  speed: initialSpeed,
  draft: null,
  initialize(gameId, view) {
    const streamKey = `${gameId}:${view}`
    set((state) =>
      state.streamKey === streamKey
        ? state
        : { streamKey, events: [], cursor: -1, playing: true, draft: null },
    )
  },
  append(event) {
    set((state) => {
      if (state.events.some((item) => item.seq === event.seq)) return state
      const wasFollowing = state.cursor === state.events.length - 1 && state.playing
      const events = [...state.events, event].sort((a, b) => a.seq - b.seq)
      return {
        events,
        cursor: wasFollowing ? events.length - 1 : state.cursor,
        draft:
          wasFollowing &&
          (event.type === 'speech' ||
            (event.type === 'speaker_turn_started' && state.draft?.failed && !state.draft.content))
            ? null
            : state.draft,
      }
    })
  },
  applyStreamFrame(frame) {
    set((state) => {
      if (!state.playing || state.cursor !== state.events.length - 1) return state
      const player = String(frame.payload.player ?? '')
      if (!player) return state
      return {
        draft: {
          player,
          content: String(frame.payload.content_so_far ?? ''),
          offsetMs: Number(frame.payload.offset_ms ?? state.draft?.offsetMs ?? 0),
          failed: frame.type === 'speech_failed',
        },
      }
    })
  },
  setReplayDraft(draft) {
    set({ draft })
  },
  setCursor(cursor) {
    set((state) => ({
      cursor: Math.max(-1, Math.min(cursor, state.events.length - 1)),
      draft: null,
    }))
  },
  setPlaying(playing) {
    set({ playing })
  },
  setSpeed(speed) {
    localStorage.setItem('werewolf.playbackSpeed', String(speed))
    set({ speed })
  },
  restart() {
    set({ cursor: -1, playing: true, draft: null })
  },
  jumpLatest() {
    set((state) => ({ cursor: state.events.length - 1, playing: true, draft: null }))
  },
}))

export function recordedDelay(
  current: GameEvent | undefined,
  next: GameEvent | undefined,
  speed: number,
): number {
  if (!next || !current) return 0
  const delta = Date.parse(next.created_at) - Date.parse(current.created_at)
  return Math.max(0, Number.isFinite(delta) ? delta / speed : 0)
}
