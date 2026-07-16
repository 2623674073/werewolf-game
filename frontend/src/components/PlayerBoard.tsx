import { motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'

import type { Player } from '../api/types'
import { characterAssets, portraitFor, roleTheme } from '../assets/manifest'
import type { GameProjection } from '../game/projection'
import { seatPosition } from '../game/seatGeometry'
import type { SpeechDraft } from '../store/playback'

interface Props {
  players: Player[]
  projection: GameProjection
  phase: string
  round: number
  draft: SpeechDraft | null
}

export function PlayerBoard({ players, projection, phase, round, draft }: Props) {
  const activeSpeaker = draft && !draft.failed ? draft.player : projection.currentSpeaker
  const speechPlayer = draft?.content ? draft.player : projection.speechPlayer
  const speech = draft?.content || projection.currentSpeech
  return (
    <section
      className={`game-board phase-${phase} player-count-${players.length} ${players.length >= 10 ? 'compact-seats' : ''}`}
      aria-label="玩家席位"
    >
      <div className="moon-disc" />
      <div className="board-ring" />
      {players.map((player, index) => {
        const position = seatPosition(index, players.length)
        const alive = projection.alive.get(player.name) ?? player.is_alive
        const role = projection.roles.get(player.name)
        const active = activeSpeaker === player.name
        return (
          <motion.article
            layout
            key={player.name}
            className={`player-seat ${active ? 'active' : ''} ${alive ? '' : 'eliminated'}`}
            style={
              {
                left: `${position.x}%`,
                top: `${position.y}%`,
                x: '-50%',
                y: '-50%',
                '--accent': characterAssets[player.character]?.accent,
              } as React.CSSProperties
            }
            animate={{ scale: active ? 1.08 : 1 }}
          >
            <Portrait player={player} />
            <div className="seat-copy">
              <strong>{player.name}</strong>
              <span>{alive ? (active ? '正在发言' : '静候局势') : '已离席'}</span>
              {(player.persona_tags ?? []).length > 0 && (
                <small>{(player.persona_tags ?? []).slice(0, 2).join(' · ')}</small>
              )}
            </div>
            {role && (
              <span
                className="role-mark"
                style={{ '--role-color': roleTheme[role]?.color } as React.CSSProperties}
              >
                {roleTheme[role]?.mark ?? role.slice(0, 1)}
              </span>
            )}
          </motion.article>
        )
      })}
      <motion.div className="center-stage" aria-live="polite">
        <span className="eyebrow">
          第 {round || '—'} 回合 · {phaseLabel(phase)}
        </span>
        {speechPlayer && speech ? (
          <>
            <h2>{speechPlayer}</h2>
            <DialogueText text={speech} />
            {draft?.failed && <small className="speech-failed">本次发言未能完整送达</small>}
            {projection.currentSpeaker &&
              projection.currentSpeaker !== speechPlayer &&
              (!draft || draft.failed) && (
                <span className="next-speaker thinking">
                  {projection.currentSpeaker} 正在斟酌局势
                </span>
              )}
          </>
        ) : activeSpeaker ? (
          <>
            <h2>{activeSpeaker}</h2>
            <blockquote>
              {draft?.failed ? (
                <span className="speech-failed">本次发言未能完整送达</span>
              ) : (
                <span className="thinking">正在斟酌局势</span>
              )}
            </blockquote>
          </>
        ) : (
          <>
            <h2>
              {phase === 'night' ? '夜幕低垂' : phase === 'finished' ? '尘埃落定' : '群雄会盟'}
            </h2>
            <p>事件将随 AI 决策实时抵达</p>
          </>
        )}
      </motion.div>
    </section>
  )
}

function DialogueText({ text }: { text: string }) {
  const ref = useRef<HTMLQuoteElement>(null)
  const followEnd = useRef(true)

  useEffect(() => {
    if (followEnd.current && ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [text])

  return (
    <blockquote
      ref={ref}
      onScroll={() => {
        const element = ref.current
        if (!element) return
        followEnd.current = element.scrollHeight - element.scrollTop - element.clientHeight < 24
      }}
    >
      {text}
    </blockquote>
  )
}

function Portrait({ player }: { player: Player }) {
  const [failed, setFailed] = useState(false)
  return failed ? (
    <span className="portrait fallback">{player.character.slice(0, 1)}</span>
  ) : (
    <img
      className="portrait"
      src={portraitFor(player.character)}
      alt={`${player.character}立绘`}
      onError={() => setFailed(true)}
    />
  )
}

function phaseLabel(phase: string): string {
  return { setup: '布阵', night: '入夜', day: '白昼', finished: '终局' }[phase] ?? phase
}
