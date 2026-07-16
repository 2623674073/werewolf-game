export function seatPosition(index: number, playerCount: number): { x: number; y: number } {
  const angle = (Math.PI * 2 * index) / playerCount - Math.PI / 2
  const radiusX = playerCount >= 10 ? 39 : 38.5
  const radiusY = playerCount >= 10 ? 39 : 38
  return {
    x: 50 + Math.cos(angle) * radiusX,
    y: 50 + Math.sin(angle) * radiusY,
  }
}
