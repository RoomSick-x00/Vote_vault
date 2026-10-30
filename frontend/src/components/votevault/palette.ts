/**
 * VoteVault — Verifiable Ballot Core
 * Shared art-direction palette (locked to the supplied visual reference)
 * and scene layout constants (all units are world-space meters).
 */

export const COLORS = {
  /** Near-black scene background */
  obsidian: '#08090B',
  /** Black metal used for the pedestal + cap */
  charcoal: '#171719',
  /** Warm amber — insertion slot glow */
  amber: '#FF9D00',
  /** Radiant golden yellow — chevron, verification mark */
  gold: '#FFD166',
  /** Champagne gold — trims, typography, soft metals */
  champagne: '#E9C982',
  /** Glass highlight white */
  glassHighlight: '#F5F5F5',
  /** Ballot paper surface */
  ballot: '#F2F0EA',
  /** Warm under-ballot light */
  warmLight: '#FFB35C',
  /** Glass attenuation (internal golden tint) */
  glassTint: '#FFC46B',
} as const;

export const LAYOUT = {
  /** Vertical offset of the whole artifact group (world space) */
  groupY: 0.3,
  /** Half height of the glass chamber (it spans -1.39 .. +1.39) */
  chamberHalfH: 1.39,
  /** Vertical position of the insertion-slot cap assembly */
  capY: 1.45,
  /** Where the ballot rests inside the chamber */
  ballotRestY: 0.02,
  /** How far above the slot the ballot travels while casting */
  ballotExitY: 2.42,
  /** Y of the glowing slit the ballot passes through */
  slotY: 1.5,
  /** Resting height of the verification checkmark */
  checkY: 2.12,
  /** Bottom of the metal base (chamber-local) */
  baseBottomY: -2.18,
  /** Luminous ring in the gap between base top and chamber bottom */
  gapRingY: -1.455,
  /** World-space floor level */
  floorY: -2.05,
} as const;
