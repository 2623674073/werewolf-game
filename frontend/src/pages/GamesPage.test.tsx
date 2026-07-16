import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Game } from '../api/types'
import { GameCard } from './GamesPage'

const baseGame: Game = {
  id: '12345678-1234-1234-1234-123456789012',
  player_count: 6,
  status: 'completed',
  phase: 'finished',
  round_number: 3,
  players: [],
  winner: 'villagers',
  created_at: '2026-07-16T00:00:00Z',
}

describe('GameCard deletion', () => {
  it('shows permanent deletion only for terminal games and requires confirmation', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    render(
      <GameCard
        game={baseGame}
        onOpen={vi.fn()}
        onStart={vi.fn()}
        onDelete={onDelete}
        deleting={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: '删除第 12345678 号推演' }))
    expect(
      screen.getByText('本局对话、身份、技能事件和史官复盘都会被永久删除，且无法恢复。'),
    ).toBeInTheDocument()
    expect(onDelete).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '永久删除' }))
    expect(onDelete).toHaveBeenCalledOnce()
  })

  it('does not offer deletion for created or running games', () => {
    const { rerender } = render(
      <GameCard
        game={{ ...baseGame, status: 'created', phase: 'setup' }}
        onOpen={vi.fn()}
        onStart={vi.fn()}
        onDelete={vi.fn()}
        deleting={false}
      />,
    )
    expect(screen.queryByRole('button', { name: /删除第/ })).not.toBeInTheDocument()

    rerender(
      <GameCard
        game={{ ...baseGame, status: 'running', phase: 'day' }}
        onOpen={vi.fn()}
        onStart={vi.fn()}
        onDelete={vi.fn()}
        deleting={false}
      />,
    )
    expect(screen.queryByRole('button', { name: /删除第/ })).not.toBeInTheDocument()
  })
})
