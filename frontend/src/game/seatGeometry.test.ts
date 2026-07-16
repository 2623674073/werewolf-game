import { describe, expect, it } from 'vitest'

import { seatPosition } from './seatGeometry'

describe('player board geometry', () => {
  it.each([6, 12])('places %i players on the same safe ellipse', (playerCount) => {
    const positions = Array.from({ length: playerCount }, (_, index) =>
      seatPosition(index, playerCount),
    )

    for (const position of positions) {
      const ellipse = ((position.x - 50) / 38) ** 2 + ((position.y - 50) / 36) ** 2
      expect(ellipse).toBeCloseTo(1, 8)
      expect(position.x).toBeGreaterThanOrEqual(12)
      expect(position.x).toBeLessThanOrEqual(88)
      expect(position.y).toBeGreaterThanOrEqual(14)
      expect(position.y).toBeLessThanOrEqual(86)
    }
  })
})
