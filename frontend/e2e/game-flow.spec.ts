import { expect, test } from '@playwright/test'

test('login, launch, watch, switch view and replay a deterministic game', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('输入管理令牌').fill('e2e-token-at-least-24-characters')
  await page.getByRole('button', { name: '持令入席' }).click()
  await expect(page.getByRole('heading', { name: '今夜，谁在说谎？' })).toBeVisible()
  await expect(page.getByText(/离线演示 · v0.3.0/)).toBeVisible()

  await page.getByRole('button', { name: /一键开局/ }).click()
  await expect(page).toHaveURL(/\/games\/[a-f0-9-]+/)
  await expect(page.getByRole('button', { name: '公开' })).toBeVisible()
  await expectSeatsOnBoardEllipse(page, 6)
  await page.waitForTimeout(800)
  await page.getByRole('button', { name: '追到最新' }).click()
  await expect(page.getByText(/曹操·狼人/)).toBeVisible()
  await expect(page.getByText('好人阵营获胜')).toBeVisible()

  await page.getByRole('button', { name: '全知' }).click()
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: '追到最新' }).click()
  await expect(page.getByText('放逐投票')).toBeVisible()
  await expect(page.getByText(/怀疑值 9\/10/)).toBeVisible()

  await page.reload()
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: '追到最新' }).click()
  await expect(page.getByText('身份揭晓')).toBeVisible()
})

test('keeps a twelve-player board clear of the central dialogue card', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('输入管理令牌').fill('e2e-token-at-least-24-characters')
  await page.getByRole('button', { name: '持令入席' }).click()
  await page.getByLabel('入局人数').selectOption('12')
  await page.getByRole('button', { name: /一键开局/ }).click()
  await expectSeatsOnBoardEllipse(page, 12)
})

test('generates a deterministic historian review and permanently deletes the game', async ({
  page,
}) => {
  await page.goto('/login')
  await page.getByPlaceholder('输入管理令牌').fill('e2e-token-at-least-24-characters')
  await page.getByRole('button', { name: '持令入席' }).click()
  await page.getByRole('button', { name: /一键开局/ }).click()
  await expect(page.getByText('好人阵营获胜')).toBeVisible({ timeout: 5_000 })

  await page.getByRole('button', { name: '请史官复盘' }).click()
  await page.getByRole('button', { name: '生成复盘' }).click()
  await expect(page.getByRole('heading', { name: '群雄夜宴·离线推演录' })).toBeVisible({
    timeout: 5_000,
  })
  await expect(page.getByText('本局 MVP')).toBeVisible()
  await page.getByRole('button', { name: '关闭复盘' }).click()

  await page.getByRole('button', { name: '删除对局' }).click()
  await page.getByRole('button', { name: '永久删除' }).click()
  await expect(page).toHaveURL(/\/games$/)
})

test('reconnects the SSE stream after a transient network failure', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('输入管理令牌').fill('e2e-token-at-least-24-characters')
  await page.getByRole('button', { name: '持令入席' }).click()
  let interrupted = false
  await page.route(/\/api\/v1\/games\/[^/]+\/stream/, async (route) => {
    if (!interrupted) {
      interrupted = true
      await route.abort('connectionfailed')
      return
    }
    await route.continue()
  })
  await page.getByRole('button', { name: /一键开局/ }).click()
  await expect(page.getByText('正在重连')).toBeVisible({ timeout: 3_000 })
  await expect(page.getByText('实时连接')).toBeVisible({ timeout: 4_000 })
  await expect(page.getByText('好人阵营获胜')).toBeVisible({ timeout: 5_000 })
  expect(interrupted).toBe(true)
})

async function expectSeatsOnBoardEllipse(
  page: import('@playwright/test').Page,
  playerCount: number,
) {
  const board = await page.locator('.game-board').boundingBox()
  const stage = await page.locator('.center-stage').boundingBox()
  const seats = page.locator('.player-seat')
  expect(board).not.toBeNull()
  expect(stage).not.toBeNull()
  expect(await seats.count()).toBe(playerCount)
  if (!board) return

  for (let index = 0; index < (await seats.count()); index += 1) {
    const seat = await seats.nth(index).boundingBox()
    expect(seat).not.toBeNull()
    if (!seat) continue
    expect(seat.x).toBeGreaterThanOrEqual(board.x)
    expect(seat.y).toBeGreaterThanOrEqual(board.y)
    expect(seat.x + seat.width).toBeLessThanOrEqual(board.x + board.width)
    expect(seat.y + seat.height).toBeLessThanOrEqual(board.y + board.height)
    if (stage) expect(rectanglesOverlap(seat, stage)).toBe(false)

    const x = ((seat.x + seat.width / 2 - board.x) / board.width) * 100
    const y = ((seat.y + seat.height / 2 - board.y) / board.height) * 100
    const radiusX = playerCount >= 10 ? 39 : 38.5
    const radiusY = playerCount >= 10 ? 39 : 38
    const ellipse = ((x - 50) / radiusX) ** 2 + ((y - 50) / radiusY) ** 2
    expect(ellipse).toBeCloseTo(1, 1)
  }
}

function rectanglesOverlap(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number },
): boolean {
  const tolerance = 2
  return !(
    first.x + first.width <= second.x + tolerance ||
    second.x + second.width <= first.x + tolerance ||
    first.y + first.height <= second.y + tolerance ||
    second.y + second.height <= first.y + tolerance
  )
}
