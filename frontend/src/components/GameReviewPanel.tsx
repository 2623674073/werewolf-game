import { Award, BookOpen, ChevronRight, LoaderCircle, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'

import type { GameEvent, GameReview } from '../api/types'

interface Props {
  review: GameReview | null
  loading: boolean
  requesting: boolean
  requestError?: string
  events: GameEvent[]
  onRequest: () => void
  onSeek: (cursor: number) => void
}

export function GameReviewPanel({
  review,
  loading,
  requesting,
  requestError,
  events,
  onRequest,
  onSeek,
}: Props) {
  const [open, setOpen] = useState(false)
  const pending = review?.status === 'pending' || requesting
  const failed = review?.status === 'failed'

  function seek(seq: number) {
    const cursor = events.findIndex((event) => event.seq === seq)
    if (cursor >= 0) {
      onSeek(cursor)
      setOpen(false)
    }
  }

  return (
    <>
      <button className="review-trigger" onClick={() => setOpen(true)}>
        <BookOpen size={17} />
        {review?.status === 'completed' ? '查看史官复盘' : '请史官复盘'}
      </button>
      {open && (
        <div className="review-overlay" role="dialog" aria-modal="true" aria-label="终局史官复盘">
          <section className="review-panel">
            <header>
              <div>
                <span className="eyebrow">终局卷宗</span>
                <h2>{review?.result?.title ?? '史官评局'}</h2>
              </div>
              <button className="icon-button" onClick={() => setOpen(false)} aria-label="关闭复盘">
                <X size={18} />
              </button>
            </header>
            {loading && <p className="review-state">正在查阅复盘状态……</p>}
            {!loading && !review && (
              <div className="review-empty">
                <BookOpen size={38} />
                <p>胜负已定，可请史官翻阅全知卷宗，评点本局得失。</p>
                <button className="button primary" onClick={onRequest}>
                  生成复盘
                </button>
                {requestError && <small className="review-error">{requestError}</small>}
              </div>
            )}
            {pending && (
              <div className="review-empty">
                <LoaderCircle className="review-spinner" size={38} />
                <p>史官正在翻阅卷宗，按回合梳理关键转折……</p>
              </div>
            )}
            {failed && (
              <div className="review-empty">
                <p>本次复盘未能完成，游戏记录不受影响。</p>
                <button className="button primary" onClick={onRequest}>
                  <RotateCcw size={15} />
                  重新生成
                </button>
                {requestError && <small className="review-error">{requestError}</small>}
              </div>
            )}
            {review?.status === 'completed' && review.result && (
              <div className="review-content">
                <p className="review-overview">{review.result.overview}</p>
                <section>
                  <h3>胜负关键</h3>
                  <ul className="factor-list">
                    {review.result.winning_factors.map((factor) => (
                      <li key={factor}>{factor}</li>
                    ))}
                  </ul>
                </section>
                <section>
                  <h3>关键转折</h3>
                  <div className="turning-points">
                    {review.result.turning_points.map((point) => (
                      <article key={point.title}>
                        <strong>{point.title}</strong>
                        <p>{point.analysis}</p>
                        <div>
                          {point.event_seqs.map((seq) => (
                            <button key={seq} onClick={() => seek(seq)}>
                              #{seq}
                              <ChevronRight size={12} />
                            </button>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
                <section>
                  <h3>群雄评定</h3>
                  <div className="player-review-grid">
                    {[...review.result.player_reviews]
                      .sort((a, b) => b.score - a.score)
                      .map((player) => (
                        <article
                          key={player.player}
                          className={player.player === review.result?.mvp ? 'mvp' : ''}
                        >
                          <div className="player-review-title">
                            <strong>
                              {player.player} · {player.role}
                            </strong>
                            <span>{player.score.toFixed(1)}</span>
                          </div>
                          {player.player === review.result?.mvp && (
                            <div className="mvp-mark">
                              <Award size={13} /> 本局 MVP
                            </div>
                          )}
                          <p>{player.role_completion}</p>
                          {(player.highlights ?? []).length > 0 && (
                            <small>亮点：{(player.highlights ?? []).join('；')}</small>
                          )}
                          {(player.mistakes ?? []).length > 0 && (
                            <small>失误：{(player.mistakes ?? []).join('；')}</small>
                          )}
                        </article>
                      ))}
                  </div>
                </section>
                <blockquote className="review-closing">{review.result.closing_comment}</blockquote>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  )
}
