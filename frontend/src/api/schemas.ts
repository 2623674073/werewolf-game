import { z } from 'zod'

export const playerSchema = z.object({
  name: z.string(),
  character: z.string(),
  is_alive: z.boolean(),
  role: z.string().nullable().optional(),
  has_antidote: z.boolean().nullable().optional(),
  has_poison: z.boolean().nullable().optional(),
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
