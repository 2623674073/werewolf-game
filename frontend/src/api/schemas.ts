import { z } from 'zod'

export const playerSchema = z.object({
  name: z.string(),
  character: z.string(),
  is_alive: z.boolean(),
  role: z.string().nullable().optional(),
  has_antidote: z.boolean().nullable().optional(),
  has_poison: z.boolean().nullable().optional(),
  persona_tags: z.array(z.string()).default([]),
})

export const gameSchema = z.object({
  id: z.string(),
  player_count: z.number(),
  status: z.enum(['created', 'running', 'completed', 'draw', 'cancelled', 'interrupted', 'failed']),
  phase: z.enum(['setup', 'night', 'day', 'finished']),
  round_number: z.number(),
  players: z.array(playerSchema),
  winner: z.string().nullish().default(null),
  error_code: z.string().nullish().default(null),
  created_at: z.string(),
  started_at: z.string().nullish().default(null),
  finished_at: z.string().nullish().default(null),
})

export const sessionSchema = z.object({
  authenticated: z.literal(true),
  capabilities: z.array(z.enum(['control', 'public_view', 'god_view'])),
})

export const eventSchema = z.object({
  game_id: z.string(),
  seq: z.number().int().positive(),
  type: z.string(),
  phase: z.enum(['setup', 'night', 'day', 'finished']),
  visibility: z.enum(['public', 'private', 'internal']),
  recipients: z.array(z.string()),
  payload: z.record(z.string(), z.unknown()),
  created_at: z.string(),
})

export const speechStreamFrameSchema = z.object({
  game_id: z.string(),
  type: z.enum(['speech_delta', 'speech_failed']),
  phase: z.enum(['setup', 'night', 'day', 'finished']),
  visibility: z.enum(['public', 'private', 'internal']),
  recipients: z.array(z.string()),
  payload: z.record(z.string(), z.unknown()),
  created_at: z.string(),
})

const turningPointSchema = z.object({
  title: z.string(),
  analysis: z.string(),
  event_seqs: z.array(z.number().int().positive()),
})

const playerReviewSchema = z.object({
  player: z.string(),
  character: z.string(),
  role: z.string(),
  score: z.number().min(0).max(10),
  role_completion: z.string(),
  highlights: z.array(z.string()),
  mistakes: z.array(z.string()),
  evidence_event_seqs: z.array(z.number().int().positive()),
})

export const gameReviewSchema = z.object({
  game_id: z.string(),
  status: z.enum(['pending', 'completed', 'failed']),
  result: z
    .object({
      title: z.string(),
      overview: z.string(),
      turning_points: z.array(turningPointSchema),
      winning_factors: z.array(z.string()),
      player_reviews: z.array(playerReviewSchema),
      mvp: z.string(),
      closing_comment: z.string(),
    })
    .nullable()
    .optional(),
  error_code: z.string().nullable().optional(),
  created_at: z.string(),
  completed_at: z.string().nullable().optional(),
})
