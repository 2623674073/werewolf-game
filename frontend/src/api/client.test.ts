import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  TOKEN_KEY,
  cancelGame,
  clearToken,
  createGame,
  deleteGame,
  getGame,
  getToken,
  listGames,
  setToken,
  startGame,
  validateSession,
} from './client'

const game = {
  id: 'g',
  player_count: 6,
  status: 'created',
  phase: 'setup',
  round_number: 0,
  players: [],
  winner: null,
  error_code: null,
  created_at: '2026-01-01',
  started_at: null,
  finished_at: null,
}

describe('api client', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('stores tokens only in session storage', () => {
    setToken('secret')
    expect(getToken()).toBe('secret')
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('secret')
    clearToken()
    expect(getToken()).toBeNull()
  })

  it('calls session and game endpoints with bearer auth', async () => {
    setToken('secret')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          authenticated: true,
          capabilities: ['control', 'public_view', 'god_view'],
          runtime_mode: 'demo',
          version: '0.3.0',
        }),
      )
      .mockResolvedValueOnce(response([game]))
      .mockResolvedValueOnce(response(game))
      .mockResolvedValueOnce(response(game))
      .mockResolvedValueOnce(response(game))
      .mockResolvedValueOnce(response(game))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    await validateSession()
    await listGames()
    await createGame(6)
    await startGame('g')
    await cancelGame('g')
    await getGame('g', 'god')
    await deleteGame('g')
    expect(fetchMock).toHaveBeenCalledTimes(7)
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toMatchObject({
      Authorization: 'Bearer secret',
    })
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ player_count: 6 }),
    })
    expect(fetchMock.mock.calls[5]?.[0]).toContain('view=god')
    expect(fetchMock.mock.calls[6]?.[1]).toMatchObject({ method: 'DELETE' })
  })

  it('normalizes structured and non-json errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          response({ error: { code: 'bad', message: '错误', request_id: 'r1' } }, 409),
        ),
    )
    await expect(startGame('g')).rejects.toEqual(
      expect.objectContaining({ status: 409, code: 'bad', requestId: 'r1' }),
    )
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(new Response('gateway down', { status: 503 })),
    )
    await expect(listGames()).rejects.toEqual(
      expect.objectContaining({ status: 503, code: 'request_failed' }),
    )
  })
})

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
