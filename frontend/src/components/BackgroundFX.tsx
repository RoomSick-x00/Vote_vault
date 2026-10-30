import { useEffect, useMemo } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useUIStore } from '../store/ui'

interface TriangleSpec {
  id: number
  x: number // percentage
  y: number // percentage
  size: number
  rotation: number
  fill: string
  stroke: string
  strokeWidth: number
  opacity: number
  animType: 'drift-a' | 'drift-b'
}

/**
 * Procedural deterministic pseudo-random generator
 */
function seededRandom(seed: number) {
  let s = seed
  return () => {
    s = (s * 9301 + 49297) % 233280
    return s / 233280
  }
}

/**
 * Ambient background with geometric triangular tessellation,
 * drifting geometric triangles across the viewport, fine technical grid,
 * and soft ambient lighting pools that respond to pointer parallax.
 */
export default function BackgroundFX() {
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const sx = useSpring(mx, { stiffness: 42, damping: 22, mass: 0.6 })
  const sy = useSpring(my, { stiffness: 42, damping: 22, mass: 0.6 })

  const gridX = useTransform(sx, (v) => v * -12)
  const gridY = useTransform(sy, (v) => v * -8)
  const triNearX = useTransform(sx, (v) => v * -24)
  const triNearY = useTransform(sy, (v) => v * -18)
  const triFarX = useTransform(sx, (v) => v * -12)
  const triFarY = useTransform(sy, (v) => v * -8)

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!useUIStore.getState().motionEnabled) return
      mx.set(e.clientX / window.innerWidth - 0.5)
      my.set(e.clientY / window.innerHeight - 0.5)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => window.removeEventListener('pointermove', onMove)
  }, [mx, my])

  // Pre-calculate 32 deterministic scattered triangles across the background
  const triangles = useMemo<TriangleSpec[]>(() => {
    const rand = seededRandom(42)

    return Array.from({ length: 32 }, (_, i) => {
      const isSaffron = rand() > 0.45
      const isFilled = rand() > 0.65
      const size = Math.round(16 + rand() * 26)
      return {
        id: i,
        x: Math.round(4 + rand() * 92),
        y: Math.round(4 + rand() * 92),
        size,
        rotation: Math.round(rand() * 360),
        fill: isFilled
          ? isSaffron
            ? 'rgba(255, 153, 51, 0.05)'
            : 'rgba(245, 243, 237, 0.03)'
          : 'none',
        stroke: isSaffron ? 'rgba(255, 153, 51, 0.35)' : 'rgba(245, 243, 237, 0.22)',
        strokeWidth: rand() > 0.6 ? 1.4 : 0.9,
        opacity: 0.4 + rand() * 0.5,
        animType: i % 2 === 0 ? 'drift-a' : 'drift-b',
      }
    })
  }, [])

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* 1. Isometric Triangular Mesh Pattern */}
      <motion.div
        style={{ x: gridX, y: gridY }}
        className="absolute -inset-24 [mask-image:radial-gradient(ellipse_80%_65%_at_50%_40%,black_30%,transparent_80%)]"
      >
        <svg className="h-full w-full opacity-45" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern
              id="tri-pattern"
              width="90"
              height="155.88"
              patternUnits="userSpaceOnUse"
            >
              {/* Triangular isometric grid hairlines */}
              <path
                d="M 0 0 L 45 77.94 L 0 155.88 L 90 155.88 L 45 77.94 L 90 0 Z M 0 77.94 L 90 77.94"
                fill="none"
                stroke="rgba(245, 243, 237, 0.04)"
                strokeWidth="0.8"
              />
              {/* Subtle accent triangle facets */}
              <polygon
                points="45,77.94 90,0 90,155.88"
                fill="rgba(255, 153, 51, 0.015)"
              />
              <polygon
                points="0,0 45,77.94 0,77.94"
                fill="rgba(91, 140, 255, 0.012)"
              />
              {/* Vertex accent dots */}
              <circle cx="45" cy="77.94" r="1.2" fill="rgba(255, 153, 51, 0.2)" />
              <circle cx="0" cy="0" r="1" fill="rgba(245, 243, 237, 0.15)" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#tri-pattern)" />
        </svg>
      </motion.div>

      {/* 2. Ultra-subtle light pools */}
      <div className="anim-glow-a absolute -top-44 right-[-10%] h-[560px] w-[560px] rounded-full bg-saffron/5 blur-[140px]" />
      <div className="anim-glow-b absolute bottom-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-electric/5 blur-[140px]" />

      {/* 3. Floating Geometric Triangles All Over App Background (Responsive absolute positioning) */}
      <motion.div style={{ x: triNearX, y: triNearY }} className="absolute inset-0">
        {triangles.slice(0, 16).map((tri) => (
          <div
            key={tri.id}
            style={{ left: `${tri.x}%`, top: `${tri.y}%` }}
            className={`absolute -translate-x-1/2 -translate-y-1/2 ${
              tri.animType === 'drift-a' ? 'anim-drift-a' : 'anim-drift-b'
            }`}
          >
            <svg
              width={tri.size}
              height={tri.size}
              viewBox="-20 -20 40 40"
              style={{ transform: `rotate(${tri.rotation}deg)` }}
            >
              <polygon
                points="0,-16 14,12 -14,12"
                fill={tri.fill}
                stroke={tri.stroke}
                strokeWidth={tri.strokeWidth}
                strokeLinejoin="round"
                opacity={tri.opacity}
              />
            </svg>
          </div>
        ))}
      </motion.div>

      <motion.div style={{ x: triFarX, y: triFarY }} className="absolute inset-0">
        {triangles.slice(16).map((tri) => (
          <div
            key={tri.id}
            style={{ left: `${tri.x}%`, top: `${tri.y}%` }}
            className={`absolute -translate-x-1/2 -translate-y-1/2 ${
              tri.animType === 'drift-a' ? 'anim-drift-b' : 'anim-drift-a'
            }`}
          >
            <svg
              width={tri.size}
              height={tri.size}
              viewBox="-20 -20 40 40"
              style={{ transform: `rotate(${tri.rotation}deg)` }}
            >
              <polygon
                points="0,-16 14,12 -14,12"
                fill={tri.fill}
                stroke={tri.stroke}
                strokeWidth={tri.strokeWidth}
                strokeLinejoin="round"
                opacity={tri.opacity * 0.75}
              />
            </svg>
          </div>
        ))}
      </motion.div>
    </div>
  )
}
