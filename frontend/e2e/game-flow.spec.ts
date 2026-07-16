import { expect, test } from '@playwright/test'

test('login, launch, watch, switch view and replay a deterministic game', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('输入管理令牌').fill('e2e-token-at-least-24-characters')
  await page.getByRole('button', { name: '持令入席' }).click()
  await expect(page.getByRole('heading', { name: '今夜，谁在说谎？' })).toBeVisible()

  await page.getByRole('button', { name: /一键开局/ }).click()
  await expect(page).toHaveURL(/\/games\/[a-f0-9-]+/)
  await expect(page.getByText('公开', { exact: true })).toBeVisible()
  await expectSeatsOnBoardEllipse(page)
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

async function expectSeatsOnBoardEllipse(page: import('@playwright/test').Page) {
  const board = await page.locator('.game-board').boundingBox()
  const seats = page.locator('.player-seat')
  expect(board).not.toBeNull()
  expect(await seats.count()).toBe(6)
  if (!board) return

  for (let index = 0; index < (await seats.count()); index += 1) {
    const seat = await seats.nth(index).boundingBox()
    expect(seat).not.toBeNull()
    if (!seat) continue
    expect(seat.x).toBeGreaterThanOrEqual(board.x)
    expect(seat.y).toBeGreaterThanOrEqual(board.y)
    expect(seat.x + seat.width).toBeLessThanOrEqual(board.x + board.width)
    expect(seat.y + seat.height).toBeLessThanOrEqual(board.y + board.height)

    const x = ((seat.x + seat.width / 2 - board.x) / board.width) * 100
    const y = ((seat.y + seat.height / 2 - board.y) / board.height) * 100
    const ellipse = ((x - 50) / 38) ** 2 + ((y - 50) / 36) ** 2
    expect(ellipse).toBeCloseTo(1, 1)
  }
}
