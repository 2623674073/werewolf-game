import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { GameEvent, GameReview } from '../api/types'
import { GameReviewPanel } from './GameReviewPanel'

const event: GameEvent = {
  game_id: 'game-1',
  seq: 7,
  type: 'speech',
  phase: 'day',
  visibility: 'public',
  recipients: [],
  payload: { player: '刘备', content: '曹操可疑' },
  created_at: new Date().toISOString(),
}

const completed: GameReview = {
  game_id: 'game-1',
  status: 'completed',
  created_at: new Date().toISOString(),
  result: {
    title: '群雄终局',
    overview: '好人阵营把握住关键线索。',
    turning_points: [
      { title: '关键发言', analysis: '刘备指出矛盾。', event_seqs: [7] },
      { title: '胜负落定', analysis: '投票形成多数。', event_seqs: [7] },
    ],
    winning_factors: ['公开信息得到利用'],
    player_reviews: [
      {
        player: '刘备',
        character: '刘备',
        role: '预言家',
        score: 9,
        role_completion: '完成查验职责。',
        highlights: ['推动讨论'],
        mistakes: [],
        evidence_event_seqs: [7],
      },
    ],
    mvp: '刘备',
    closing_comment: '忠奸既辨，此局可记。',
  },
}

describe('GameReviewPanel', () => {
  it('requests a review when no result exists', () => {
    const onRequest = vi.fn()
    render(
      <GameReviewPanel
        review={null}
        loading={false}
        requesting={false}
        events={[event]}
        onRequest={onRequest}
        onSeek={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '请史官复盘' }))
    fireEvent.click(screen.getByRole('button', { name: '生成复盘' }))
    expect(onRequest).toHaveBeenCalledOnce()
  })

  it('renders completed analysis and seeks to cited events', () => {
    const onSeek = vi.fn()
    render(
      <GameReviewPanel
        review={completed}
        loading={false}
        requesting={false}
        events={[event]}
        onRequest={vi.fn()}
        onSeek={onSeek}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '查看史官复盘' }))
    expect(screen.getByText('群雄终局')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: /#7/ })[0]!)
    expect(onSeek).toHaveBeenCalledWith(0)
  })
})
