import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { GameEvent } from '../api/types'
import { EventTimeline } from './EventTimeline'

function event(
  seq: number,
  type: string,
  payload: Record<string, unknown>,
  visibility: 'public' | 'private' = 'public',
): GameEvent {
  return {
    game_id: 'g',
    seq,
    type,
    phase: 'day',
    visibility,
    recipients: [],
    payload,
    created_at: '',
  } as GameEvent
}

describe('EventTimeline', () => {
  it('renders public dialogue and structured god-view actions', () => {
    render(
      <EventTimeline
        events={[
          event(1, 'speech', { player: '刘备', content: '曹操可疑' }),
          event(
            2,
            'day_vote',
            { player: '曹操', vote: '刘备', reason: '锋芒太盛', suspicion_level: 8 },
            'private',
          ),
          event(3, 'roles_revealed', {
            players: [{ player: '曹操', role: '狼人' }],
          }),
        ]}
      />,
    )
    expect(screen.getByText('刘备发言')).toBeInTheDocument()
    expect(screen.getByText('曹操可疑')).toBeInTheDocument()
    expect(screen.getByText(/怀疑值 8\/10/)).toBeInTheDocument()
    expect(screen.getByText(/曹操·狼人/)).toBeInTheDocument()
  })
})
