import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { formatPercent } from '../lib/format'

const MIN_VISIBLE_MS = 1500
const RING_RADIUS = 58
const CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS

/**
 * Minimal boot screen. Progress is driven by real initialisation tasks:
 * font loading, the lazy 3D exhibit chunk, and UI mount — smoothed with an
 * eased counter and a small minimum display window so the reveal stays elegant.
 */
export default function LoadingScreen({ onComplete }: { onComplete: () => void }) {
  const [progress, setProgress] = useState(0)
  const [complete, setComplete] = useState(false)
  const displayRef = useRef(0)
  const targetRef = useRef(0)
  const startRef = useRef(0)
  const doneRef = useRef(false)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    let cancelled = false
    let raf = 0
    let finishTimer: number | undefined

    const total = 1
    let accumulated = 0
    const settle = (weight: number) => {
      if (cancelled) return
      accumulated += weight
      targetRef.current = accumulated >= total - 0.001 ? 100 : (accumulated / total) * 100
    }
    /** No single task may hold the vault sealed for ever. */
    const withCap = (task: Promise<unknown>, ms: number) =>
      Promise.race([task, new Promise<never>((resolve) => setTimeout(resolve, ms))])
    const track = (weight: number, task: Promise<unknown>, capMs = 9000) => {
      withCap(task, capMs).then(
        () => settle(weight),
        () => settle(weight),
      )
    }

    // Task 1 — brand + UI fonts (real font fetches)
    const fontsTask = Promise.all([
      document.fonts.load('700 32px "Space Grotesk Variable"'),
      document.fonts.load('600 16px "Inter Variable"'),
      document.fonts.load('500 12px "JetBrains Mono Variable"'),
    ]).then(() => undefined)

    // Task 2 — lazy 3D exhibit chunk (three.js + R3F + drei), shared with the hero
    const sceneTask = import('./BallotBox3D').catch((err) => {
      console.warn('Preload 3D exhibit chunk skipped:', err)
      return null
    })

    track(0.3, fontsTask)
    // The 3D exhibit is a progressive enhancement: preload it here, but never
    // let its weight seal the vault for long — the hero shows a sculpted
    // static fallback until the chunk is ready (zero layout shift).
    track(0.45, sceneTask, 3500)
    track(
      0.15,
      new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))),
    )
    track(0.1, new Promise<void>((resolve) => setTimeout(resolve, 320)))

    startRef.current = performance.now()

    const tick = (now: number) => {
      if (cancelled) return
      const elapsed = now - startRef.current
      // Absolute failsafe — the app always unlocks.
      if (elapsed > 12000) targetRef.current = 100
      const target = targetRef.current
      displayRef.current += (target - displayRef.current) * 0.085

      if (target >= 100 && elapsed >= MIN_VISIBLE_MS && displayRef.current > 96) {
        displayRef.current = 100
        setProgress(100)
        if (!doneRef.current) {
          doneRef.current = true
          setComplete(true)
          finishTimer = window.setTimeout(() => onCompleteRef.current(), 780)
        }
        return
      }

      setProgress(displayRef.current)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      if (finishTimer) window.clearTimeout(finishTimer)
    }
  }, [])

  return (
    <motion.div
      exit={{ opacity: 0, y: -44 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-obsidian"
      role="status"
      aria-live="polite"
      aria-label="Loading VoteVault"
    >
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 46%, rgba(23,25,29,0.55), transparent 70%)',
        }}
      />

      {/* Wordmark */}
      <motion.span
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative pl-[0.42em] font-display text-2xl font-bold tracking-[0.42em] md:text-3xl"
      >
        <span className="text-paper">VOTE</span>
        <span className="text-saffron">VAULT</span>
      </motion.span>

      {/* Circular progress */}
      <motion.div
        initial={{ opacity: 0, scale: 0.94 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
        className="relative mt-10 h-32 w-32"
      >
        <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
          <defs>
            <linearGradient id="vv-ring-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#FF9933" />
              <stop offset="100%" stopColor="#F5F3ED" />
            </linearGradient>
          </defs>
          <circle cx="64" cy="64" r={RING_RADIUS} fill="none" stroke="rgba(245,243,237,0.10)" strokeWidth="1.5" />
          <circle
            cx="64"
            cy="64"
            r={RING_RADIUS}
            fill="none"
            stroke={complete ? '#18A024' : 'url(#vv-ring-grad)'}
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={CIRCUMFERENCE * (1 - progress / 100)}
            style={{ transition: 'stroke 400ms ease' }}
          />
        </svg>

        {/* Orbiting indicator */}
        <div aria-hidden className="anim-orbit absolute inset-[6px]">
          <span
            className={`absolute left-1/2 top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full transition-colors duration-500 ${
              complete ? 'bg-india' : 'bg-saffron'
            }`}
          />
        </div>

        {/* Green confirmation pulse */}
        {complete && (
          <motion.span
            initial={{ opacity: 0.55, scale: 1 }}
            animate={{ opacity: 0, scale: 1.42 }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
            className="absolute inset-[-6px] rounded-full border border-india"
            aria-hidden
          />
        )}

        <span className="absolute inset-0 flex items-center justify-center font-mono text-[15px] tracking-[0.08em] text-paper tabular-nums">
          {formatPercent(progress)}
        </span>
      </motion.div>

      {/* Caption */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.35 }}
        className="relative mt-9 flex items-center gap-2.5 font-mono text-[10px] tracking-[0.34em] text-ash"
      >
        {complete && <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-india" />}
        <span className={complete ? 'text-paper/80' : undefined}>
          {complete ? 'SECURE ENVIRONMENT READY' : 'INITIALISING SECURE ENVIRONMENT'}
        </span>
      </motion.p>
    </motion.div>
  )
}
