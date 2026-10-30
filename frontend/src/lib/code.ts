/**
 * Accepts a raw election UUID or a full /vote/<uuid> link (from a QR) and
 * returns the clean election id. Join codes do not exist in this milestone —
 * elections are addressed by their UUID.
 */
export function extractElectionId(input: string): string {
  const text = input.trim()
  const match = text.match(/\/vote\/([0-9a-fA-F-]+)/)
  return (match ? match[1] : text).replace(/\s+/g, '')
}

const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/

export function isElectionId(value: string): boolean {
  return UUID_RE.test(value)
}
