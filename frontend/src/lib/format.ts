/** Zero-padded percentage, e.g. 7 -> "07%", 100 -> "100%". */
export function formatPercent(value: number): string {
  const clamped = Math.max(0, Math.min(100, Math.round(value)))
  return `${String(clamped).padStart(2, '0')}%`
}
