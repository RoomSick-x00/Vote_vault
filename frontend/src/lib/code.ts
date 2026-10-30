/** Accept a raw election code or a full /vote/<code> link from a QR. */
export function extractElectionCode(input: string): string {
  const text = input.trim()
  const match = text.match(/\/vote\/([A-Za-z0-9]{8})(?:[/?#]|$)/)
  return (match ? match[1] : text).replace(/\s+/g, '').toUpperCase()
}

export function isElectionCode(value: string): boolean {
  return /^[A-Z0-9]{8}$/.test(value)
}
