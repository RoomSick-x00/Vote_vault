import { Suspense, lazy } from 'react'
import type { Variants } from 'framer-motion'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowRight, Shield, Vote } from 'lucide-react'
import { useUIStore } from '../store/ui'
import BallotFallback from './BallotFallback'
import ErrorBoundary from './ui/ErrorBoundary'

const BallotBox3D = lazy(() =>
  import('./BallotBox3D').catch((err) => {
    console.warn('Could not load 3D BallotBox canvas, falling back to 2D view:', err)
    return { default: BallotFallback }
  })
)

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.15 } },
}

const item: Variants = {
  hidden: { opacity: 0, y: 28 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.75, ease: [0.22, 1, 0.36, 1] } },
}

const TRUST_POINTS = ['Secret Ballots', 'Tamper-Evident Records', 'Verifiable Results']

export default function HeroSection() {
  const appReady = useUIStore((s) => s.appReady)

  return (
    <section className="relative mx-auto flex min-h-[92vh] max-w-7xl flex-col justify-center px-5 pb-16 pt-24 md:px-8 md:pt-28">
      <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-8">
        {/* Copy (Left side) */}
        <motion.div
          variants={container}
          initial="hidden"
          animate={appReady ? 'visible' : 'hidden'}
          className="pointer-events-auto max-w-xl"
        >
          <motion.div variants={item} className="inline-flex items-center gap-2 rounded-full border border-saffron/30 bg-saffron/10 px-3 py-1 font-mono text-[11px] text-saffron">
            <span className="h-1.5 w-1.5 rounded-full bg-saffron animate-ping" />
            A NEW STANDARD FOR DIGITAL DEMOCRACY
          </motion.div>

          <motion.h1
            variants={item}
            className="mt-6 font-display text-[clamp(2.8rem,5.8vw,4.6rem)] font-bold leading-[1.04] tracking-tight"
          >
            <span className="block text-paper">Your Vote.</span>
            <span className="text-outline block">Your Voice.</span>
            <span className="block text-saffron">Your Proof.</span>
          </motion.h1>

          <motion.p variants={item} className="mt-6 max-w-lg text-[15px] leading-relaxed text-ash md:text-base">
            Run campus and community elections end to end. Upload your voter list, share a code or QR, verify each voter by OTP, and publish tamper-evident results with a receipt every voter can check.
          </motion.p>

          {/* Primary Portal Navigation Links */}
          <motion.div variants={item} className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to="/organizer"
              className="group inline-flex items-center gap-2 rounded-xl bg-saffron px-5 py-3 font-display text-sm font-bold text-obsidian shadow-lg shadow-saffron/10 transition hover:-translate-y-0.5 hover:bg-[#ffa94d] active:translate-y-0"
            >
              <Shield className="h-4 w-4 text-obsidian" />
              Organiser Portal
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>

            <Link
              to="/voter"
              className="group inline-flex items-center gap-2 rounded-xl border border-electric/40 bg-electric/15 px-5 py-3 font-display text-sm font-bold text-electric transition hover:-translate-y-0.5 hover:bg-electric/25 active:translate-y-0"
            >
              <Vote className="h-4 w-4 text-electric" />
              Voter Hub
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>

          </motion.div>

          <motion.ul
            variants={item}
            className="mt-10 flex max-w-xl flex-wrap gap-x-8 gap-y-2 border-t border-white/8 pt-6"
          >
            {TRUST_POINTS.map((point, i) => (
              <li key={point} className="flex items-center gap-2 font-mono text-[11px] tracking-[0.14em] text-ash">
                <span className="font-bold text-saffron">0{i + 1}</span>
                <span>—</span>
                <span>{point}</span>
              </li>
            ))}
          </motion.ul>
        </motion.div>

        {/* Right side: 3D Ballot Vault Core Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: appReady ? 1 : 0, scale: appReady ? 1 : 0.96 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="relative flex flex-col items-center justify-center"
        >
          {/* Viewport frame with subtle edge */}
          <div
            className="relative h-[440px] sm:h-[500px] lg:h-[560px] w-full rounded-3xl overflow-hidden border border-white/10 bg-gradient-to-b from-charcoal/20 to-obsidian shadow-2xl flex items-center justify-center"
          >
            {/* 3D Canvas / Fallback */}
            <ErrorBoundary fallback={<BallotFallback showNote />}>
              <Suspense fallback={<BallotFallback showNote />}>
                <BallotBox3D />
              </Suspense>
            </ErrorBoundary>
          </div>
        </motion.div>
      </div>
    </section>
  )
}

