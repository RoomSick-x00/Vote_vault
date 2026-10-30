/** Accepts a raw election code or a full /vote/<code> link (from a QR) and returns the clean code. */
export function extractElectionCode(input: string): string {
  const text = input.trim()
  const match = text.match(/\/vote\/([A-Za-z0-9-]+)/)
  const raw = match ? match[1] : text
  return raw.replace(/[^A-Za-z0-9]/g, '').toUpperCase()
}
