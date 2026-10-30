import { create } from 'zustand'

const MOTION_KEY = 'votevault:motion'

function initialMotionEnabled(): boolean {
  try {
    const stored = localStorage.getItem(MOTION_KEY)
    if (stored === 'on') return true
    if (stored === 'off') return false
  } catch {
    /* storage unavailable */
  }
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

interface UIState {
  /** Flips to true once the loading screen has completed its reveal. */
  appReady: boolean
  /** Master switch for ambient/3D motion (respects system + manual preference). */
  motionEnabled: boolean
  setAppReady: (v: boolean) => void
  setMotionEnabled: (v: boolean) => void
}

export const useUIStore = create<UIState>((set) => ({
  appReady: false,
  motionEnabled: initialMotionEnabled(),
  setAppReady: (v) => set({ appReady: v }),
  setMotionEnabled: (v) => {
    try {
      localStorage.setItem(MOTION_KEY, v ? 'on' : 'off')
    } catch {
      /* storage unavailable */
    }
    set({ motionEnabled: v })
  },
}))
