import { motion } from 'framer-motion'
import type { Variants } from 'framer-motion'

function CredentialIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-6 w-6" fill="none" aria-hidden="true">
      <rect x="3.75" y="6.75" width="24.5" height="18.5" rx="3" stroke="#F5F3ED" strokeWidth="1.5" />
      <circle cx="11.5" cy="13.5" r="2.4" stroke="#F5F3ED" strokeWidth="1.5" />
      <path
        d="M7.8 20.6c.8-2.1 2.1-3.1 3.7-3.1s2.9 1 3.7 3.1"
        stroke="#F5F3ED"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path d="M19.5 12h5.5M19.5 15.5h4" stroke="#F5F3ED" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="22.2" cy="20.8" r="3.1" fill="#5B8CFF" />
      <path
        d="M20.9 20.8l.95.95 1.7-1.85"
        stroke="#08090B"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function BallotSlotIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-6 w-6" fill="none" aria-hidden="true">
      <path
        d="M5.75 13.5v8.75a3.5 3.5 0 003.5 3.5h13.5a3.5 3.5 0 003.5-3.5V13.5"
        stroke="#F5F3ED"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <g transform="rotate(9 15.7 8.65)">
        <rect x="11.2" y="2.9" width="9" height="11.5" rx="1.2" stroke="#F5F3ED" strokeWidth="1.5" />
        <path d="M13.9 6.3h4.4" stroke="#85878E" strokeWidth="1.3" strokeLinecap="round" />
      </g>
      <rect x="10.4" y="12.9" width="11.2" height="2.4" rx="1.2" fill="#FF9933" />
    </svg>
  )
}

function LedgerIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-6 w-6" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="10.25" stroke="#F5F3ED" strokeWidth="1.5" strokeDasharray="3 3.4" />
      <circle cx="16" cy="5.75" r="2.3" fill="#18A024" />
      <circle cx="24.9" cy="21.1" r="2.3" fill="#F5F3ED" fillOpacity="0.85" />
      <circle cx="7.1" cy="21.1" r="2.3" fill="#FF9933" fillOpacity="0.9" />
      <circle cx="16" cy="16" r="4.4" stroke="#F5F3ED" strokeWidth="1.5" />
      <path
        d="M14.1 16.1l1.4 1.4 2.5-2.8"
        stroke="#18A024"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const STEPS = [
  {
    id: '01',
    accent: '#5B8CFF',
    tag: 'CREDENTIAL CHECK',
    title: 'Verify Eligibility',
    body: 'Confirm that the voter is eligible to participate.',
    Icon: CredentialIcon,
  },
  {
    id: '02',
    accent: '#FF9933',
    tag: 'BALLOT SUBMISSION',
    title: 'Cast a Ballot',
    body: 'Submit a vote and receive a commitment receipt.',
    Icon: BallotSlotIcon,
  },
  {
    id: '03',
    accent: '#18A024',
    tag: 'PUBLIC AUDIT',
    title: 'Inspect the Records',
    body: 'Compare public commitments with blockchain records. This does not prove tally correctness.',
    Icon: LedgerIcon,
  },
] as const

const card: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, delay: i * 0.09, ease: [0.22, 1, 0.36, 1] },
  }),
}

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative scroll-mt-20 border-t border-white/6">
      <div className="mx-auto max-w-7xl px-5 py-24 md:px-8 md:py-32">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="flex items-center gap-3 font-mono text-[11px] tracking-[0.32em] text-ash">
              <span aria-hidden className="h-px w-10 bg-saffron/90" />
              THE WORKFLOW
            </p>
            <h2 className="mt-5 font-display text-4xl font-bold tracking-tight text-paper md:text-5xl">
              How it works.
            </h2>
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-ash">
            Follow voter verification, ballot submission, and public record inspection.
          </p>
        </div>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <motion.article
              key={step.id}
              variants={card}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-70px' }}
              custom={i}
              whileHover={{ y: -6 }}
              className="group relative overflow-hidden rounded-2xl border border-white/8 bg-charcoal p-7 transition-colors duration-300 hover:border-white/16 md:p-8"
            >
              <span
                aria-hidden
                className="absolute right-6 top-5 select-none font-display text-6xl font-bold text-white/5"
              >
                {step.id}
              </span>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-ink">
                <step.Icon />
              </div>
              <p className="mt-7 font-mono text-[10px] tracking-[0.3em]" style={{ color: step.accent }}>
                {step.tag}
              </p>
              <h3 className="mt-2.5 font-display text-xl font-bold text-paper">{step.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ash">{step.body}</p>
              <div className="mt-8 h-px w-full bg-white/6">
                <motion.span
                  className="block h-px origin-left"
                  style={{ background: step.accent }}
                  initial={{ scaleX: 0 }}
                  whileInView={{ scaleX: 0.42 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.9, delay: 0.3 + i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}
