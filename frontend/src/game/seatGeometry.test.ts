import { describe, expect, it } from 'vitest'

import { seatPosition } from './seatGeometry'

describe('player board geometry', () => {
  it.each([6, 12])('places %i players on the same safe ellipse', (playerCount) => {
    const positions = Array.from({ length: playerCount }, (_, index) =>
      seatPosition(index, playerCount),
    )

    for (const position of positions) {
      const radiusX = playerCount >= 10 ? 39 : 38.5
      const radiusY = playerCount >= 10 ? 39 : 38
      const ellipse = ((position.x - 50) / radiusX) ** 2 + ((position.y - 50) / radiusY) ** 2
      expect(ellipse).toBeCloseTo(1, 8)
      expect(position.x).toBeGreaterThanOrEqual(11)
      expect(position.x).toBeLessThanOrEqual(89)
      expect(position.y).toBeGreaterThanOrEqual(11)
      expect(position.y).toBeLessThanOrEqual(89)
    }
  })
})
