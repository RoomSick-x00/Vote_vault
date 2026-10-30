'use client';

import { create } from 'zustand';
import { clamp01, nowSec } from './utils';

/** Phases of the voting ceremony. */
export type Phase = 'idle' | 'casting' | 'verifying' | 'verified' | 'reset';

export const PHASE_DURATION: Record<Phase, number> = {
  idle: Infinity,
  casting: 1.7,
  verifying: 2.3,
  verified: 2.8,
  reset: 1.5,
};

interface VoteState {
  phase: Phase;
  /** Seconds (performance clock) at which the current phase began. */
  phaseStart: number;
  /** Successfully sealed ballots. */
  votes: number;
  /** Begin the ceremony — only from idle. */
  start: () => void;
  /** Internal: move to the next phase. Driven by the Director. */
  advance: () => void;
}

export const useVoteStore = create<VoteState>((set, get) => ({
  phase: 'idle',
  phaseStart: 0,
  votes: 0,
  start: () => {
    if (get().phase !== 'idle') return;
    set({ phase: 'casting', phaseStart: nowSec() });
  },
  advance: () => {
    const { phase, votes } = get();
    if (phase === 'idle') return;
    const next: Phase =
      phase === 'casting'
        ? 'verifying'
        : phase === 'verifying'
          ? 'verified'
          : phase === 'verified'
            ? 'reset'
            : 'idle';
    set({
      phase: next,
      phaseStart: nowSec(),
      votes: phase === 'verifying' ? votes + 1 : votes,
    });
  },
}));

/**
 * Frame-safe progress of a phase (0..1) without triggering React re-renders.
 * Read this inside useFrame; use the `useVoteStore` hook for UI.
 */
export function phaseProgress(t: number, phase?: Phase): number {
  const s = useVoteStore.getState();
  if (phase !== undefined && s.phase !== phase) return 0;
  const d = PHASE_DURATION[s.phase];
  if (!isFinite(d)) return 0;
  return clamp01((t - s.phaseStart) / d);
}
