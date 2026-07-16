import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Player } from '../api/types'
import type { GameProjection } from '../game/projection'
import { PlayerBoard } from './PlayerBoard'

function players(count: number): Player[] {
  return Array.from({ length: count }, (_, index) => ({
    name: `玩家${index + 1}`,
    character: '刘备',
    is_alive: true,
    persona_tags: ['仁厚'],
  }))
}

function projection(): GameProjection {
  return {
    visibleEvents: [],
    alive: new Map(),
    roles: new Map(),
    currentSpeaker: '玩家2',
    speechPlayer: '玩家1',
    currentSpeech: '上一位玩家的完整发言仍然可见',
  }
}

describe('PlayerBoard', () => {
  it('keeps completed speech visible while the next player thinks', () => {
    render(
      <PlayerBoard
        players={players(6)}
        projection={projection()}
        phase="day"
        round={1}
        draft={null}
      />,
    )

    expect(screen.getByText('上一位玩家的完整发言仍然可见')).toBeInTheDocument()
    expect(screen.getByText(/玩家2 正在斟酌局势/)).toBeInTheDocument()
  })

  it('uses compact seats for ten to twelve players', () => {
    render(
      <PlayerBoard
        players={players(12)}
        projection={projection()}
        phase="night"
        round={2}
        draft={{ player: '玩家2', content: '真实流式文本', offsetMs: 10, failed: false }}
      />,
    )

    expect(screen.getByLabelText('玩家席位')).toHaveClass('compact-seats', 'player-count-12')
    expect(screen.getByText('真实流式文本')).toBeInTheDocument()
  })
})
