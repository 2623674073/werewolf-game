export function seatPosition(index: number, playerCount: number): { x: number; y: number } {
  const angle = (Math.PI * 2 * index) / playerCount - Math.PI / 2
  return {
    x: 50 + Math.cos(angle) * 38,
    y: 50 + Math.sin(angle) * 36,
  }
}
