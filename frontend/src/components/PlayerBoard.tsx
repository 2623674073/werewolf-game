import { motion } from 'motion/react'
import { useState } from 'react'

import type { Player } from '../api/types'
import { characterAssets, portraitFor, roleTheme } from '../assets/manifest'
import type { GameProjection } from '../game/projection'
import { seatPosition } from '../game/seatGeometry'
import { TypewriterText } from './TypewriterText'

interface Props {
  players: Player[]
  projection: GameProjection
  phase: string
  round: number
}

export function PlayerBoard({ players, projection, phase, round }: Props) {
  return (
    <section className={`game-board phase-${phase}`} aria-label="玩家席位">
      <div className="moon-disc" />
      <div className="board-ring" />
      {players.map((player, index) => {
        const position = seatPosition(index, players.length)
        const alive = projection.alive.get(player.name) ?? player.is_alive
        const role = projection.roles.get(player.name)
        const active = projection.currentSpeaker === player.name
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
      <motion.div className="center-stage" layout>
        <span className="eyebrow">
          第 {round || '—'} 回合 · {phaseLabel(phase)}
        </span>
        {projection.currentSpeaker ? (
          <>
            <h2>{projection.currentSpeaker}</h2>
            <blockquote>
              {projection.currentSpeech ? (
                <TypewriterText text={projection.currentSpeech} />
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
