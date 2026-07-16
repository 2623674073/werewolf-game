import { Eye, EyeOff, Vote } from 'lucide-react'

import type { GameEvent } from '../api/types'
import { arrayObjects, strings, text } from '../game/projection'

export function EventTimeline({ events }: { events: GameEvent[] }) {
  const visible = events.filter((event) => !['speaker_turn_started'].includes(event.type))
  return (
    <aside className="timeline-panel">
      <header>
        <div>
          <span className="eyebrow">卷宗</span>
          <h2>对局纪事</h2>
        </div>
        <span className="event-count">{visible.length}</span>
      </header>
      <div className="timeline-scroll" aria-live="polite">
        {visible.length === 0 && <p className="empty-copy">等待第一封战报……</p>}
        {visible.map((event) => (
          <EventCard key={event.seq} event={event} />
        ))}
      </div>
    </aside>
  )
}

function EventCard({ event }: { event: GameEvent }) {
  const privateEvent = event.visibility !== 'public'
  return (
    <article className={`event-card ${privateEvent ? 'private' : ''} type-${event.type}`}>
      <div className="event-meta">
        <span>#{event.seq}</span>
        <span>
          {privateEvent ? <EyeOff size={13} /> : <Eye size={13} />}
          {privateEvent ? '全知' : '公开'}
        </span>
      </div>
      <h3>{eventTitle(event)}</h3>
      <p>{eventDescription(event)}</p>
      {event.type === 'day_vote' && (
        <div className="suspicion">
          <Vote size={14} /> 怀疑值 {String(event.payload.suspicion_level ?? '—')}/10
        </div>
      )}
    </article>
  )
}

function eventTitle(event: GameEvent): string {
  const titles: Record<string, string> = {
    game_started: '群雄入席',
    night_started: '夜幕降临',
    day_started: '晨光初现',
    discussion_started: event.payload.discussion_kind === 'werewolf' ? '狼群密议' : '公开议事',
    speech: `${text(event.payload.player) ?? '玩家'}发言`,
    werewolf_vote: '狼人落刀',
    seer_result: '星象查验',
    witch_action: '女巫用药',
    day_vote: '放逐投票',
    hunter_action: '猎人抉择',
    night_result: '昨夜死讯',
    vote_result: '放逐结果',
    roles_revealed: '身份揭晓',
    game_finished: '胜负已分',
    game_cancelled: '对局取消',
    game_interrupted: '对局中断',
    game_failed: '对局异常',
    identity_assigned: '身份密函',
  }
  return titles[event.type] ?? event.type.replaceAll('_', ' ')
}

function eventDescription(event: GameEvent): string {
  const p = event.payload
  switch (event.type) {
    case 'speech':
      return text(p.content) ?? '未留下发言'
    case 'night_started':
    case 'day_started':
      return `第 ${String(p.round ?? '—')} 回合`
    case 'werewolf_vote':
      return `${text(p.player) ?? '狼人'}选择 ${text(p.target) ?? '未知'}：${text(p.kill_strategy) ?? '未说明'}`
    case 'seer_result':
      return `${text(p.target) ?? '目标'}是${p.is_werewolf ? '狼人' : '好人'}`
    case 'witch_action':
      return `${text(p.player) ?? '女巫'}：${text(p.action) ?? '不行动'} ${text(p.target_name) ?? ''}`.trim()
    case 'day_vote':
      return `${text(p.player) ?? '玩家'}投给 ${text(p.vote) ?? '未知'}：${text(p.reason) ?? '未说明'}`
    case 'hunter_action':
      return p.shoot ? `开枪带走 ${text(p.target) ?? '未知'}` : '选择不开枪'
    case 'night_result': {
      const deaths = strings(p.deaths)
      return deaths.length ? `${deaths.join('、')} 倒在夜色中` : '昨夜平安无事'
    }
    case 'vote_result':
      return `${text(p.voted_out) ?? '无人'}被放逐，共 ${String(p.votes ?? 0)} 票${p.hunter_shot ? `；猎人带走 ${String(p.hunter_shot)}` : ''}`
    case 'roles_revealed':
      return arrayObjects(p.players)
        .map((item) => `${String(item.player)}·${String(item.role)}`)
        .join('，')
    case 'game_finished':
      return winnerLabel(text(p.winner))
    case 'identity_assigned':
      return `${text(p.player) ?? ''}收到身份：${text(p.role) ?? ''}`
    default:
      return '局势正在推进'
  }
}

function winnerLabel(winner: string | null): string {
  return (
    { villagers: '好人阵营获胜', werewolves: '狼人阵营获胜', draw: '棋逢对手，本局平局' }[
      winner ?? ''
    ] ?? '本局结束'
  )
}
