import { Gauge, Pause, Play, RotateCcw, SkipForward } from 'lucide-react'

import { usePlaybackStore } from '../store/playback'

export function PlaybackControls() {
  const { events, cursor, playing, speed, setCursor, setPlaying, setSpeed, restart, jumpLatest } =
    usePlaybackStore()
  const maximum = Math.max(0, events.length - 1)
  const unread = Math.max(0, events.length - cursor - 1)
  return (
    <footer className="playback-bar">
      <button
        className="icon-button"
        onClick={() => setPlaying(!playing)}
        aria-label={playing ? '暂停' : '播放'}
      >
        {playing ? <Pause size={18} /> : <Play size={18} />}
      </button>
      <button className="icon-button" onClick={restart} aria-label="重新播放">
        <RotateCcw size={17} />
      </button>
      <span className="seq-label">#{cursor >= 0 ? events[cursor]?.seq : 0}</span>
      <input
        aria-label="事件进度"
        type="range"
        min={-1}
        max={maximum}
        value={Math.min(cursor, maximum)}
        onChange={(event) => {
          setPlaying(false)
          setCursor(Number(event.target.value))
        }}
      />
      <span className="seq-label">{events.length} 卷</span>
      <label className="speed-select" title="历史回放倍速">
        <Gauge size={16} />
        <select
          value={speed}
          onChange={(event) => setSpeed(Number(event.target.value) as 0.5 | 1 | 1.5 | 2)}
        >
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={1.5}>1.5×</option>
          <option value={2}>2×</option>
        </select>
      </label>
      <button className="button compact" onClick={jumpLatest}>
        <SkipForward size={16} />
        追到最新{unread > 0 ? `（${unread}）` : ''}
      </button>
    </footer>
  )
}
