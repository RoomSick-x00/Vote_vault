import { Link } from 'react-router-dom'
import {
  ArrowRight,
  FileSpreadsheet,
  KeyRound,
  QrCode,
  Shield,
  ShieldCheck,
  UserPlus,
  Vote,
} from 'lucide-react'
import HeroSection from '../components/HeroSection'
import HowItWorks from '../components/HowItWorks'
import { useAuth } from '../context/AuthContext'

const ORGANIZER_STEPS = [
  { icon: UserPlus, title: 'Create an account', body: 'Sign up as an organiser. Your organisation and elections are created in one flow.' },
  { icon: FileSpreadsheet, title: 'Add candidates & eligible voters', body: 'Add candidates to the draft, then whitelist voters by their VoteVault user ID.' },
  { icon: QrCode, title: 'Open voting & share the link', body: 'Open the election and share the link or QR. Ballot commitments publish to the chain as votes arrive.' },
]

const VOTER_STEPS = [
  { icon: KeyRound, title: 'Open the election link', body: 'Open the Voter Hub and paste the election ID or link your organiser shared.' },
  { icon: ShieldCheck, title: 'Sign in', body: 'Sign in with your VoteVault account — only whitelisted voters can cast a ballot.' },
  { icon: Vote, title: 'Vote & keep your receipt', body: 'Cast one ballot and keep the commitment + nonce so you can verify it was recorded.' },
]

function Steps({ steps, tone }: { steps: typeof ORGANIZER_STEPS; tone: 'saffron' | 'electric' }) {
  const text = tone === 'saffron' ? 'text-saffron' : 'text-electric'
  const bg = tone === 'saffron' ? 'bg-saffron/10' : 'bg-electric/10'
  return (
    <ol className="space-y-4">
      {steps.map((s, i) => (
        <li key={s.title} className="flex gap-4">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${bg} ${text}`}>
            <s.icon className="h-5 w-5" />
          </div>
          <div>
            <p className="font-display text-sm font-bold text-paper">
              <span className={`mr-2 font-mono text-xs ${text}`}>0{i + 1}</span>
              {s.title}
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-ash">{s.body}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

export default function Home() {
  const { user } = useAuth()

  return (
    <div className="space-y-20 pb-24">
      <HeroSection />

      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <h2 className="font-display text-3xl font-extrabold text-paper sm:text-4xl">Choose your portal</h2>
          <p className="mt-2 text-sm text-ash">Organisers run the election. Voters open it with the election link.</p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <div className="flex flex-col justify-between rounded-3xl border border-saffron/30 bg-gradient-to-b from-charcoal/80 to-obsidian p-8">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-saffron/10 px-3 py-1 font-mono text-[11px] font-bold text-saffron">
                <Shield className="h-3.5 w-3.5" />
                ORGANISER
              </div>
              <h3 className="mt-4 font-display text-2xl font-bold text-paper">Run an election</h3>
              <div className="mt-6">
                <Steps steps={ORGANIZER_STEPS} tone="saffron" />
              </div>
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              {user ? (
                <Link
                  to="/organizer"
                  className="inline-flex items-center gap-2 rounded-xl bg-saffron px-5 py-3 font-display text-sm font-bold text-obsidian transition hover:bg-[#ffa94d]"
                >
                  Open dashboard <ArrowRight className="h-4 w-4" />
                </Link>
              ) : (
                <>
                  <Link
                    to="/signup"
                    className="inline-flex items-center gap-2 rounded-xl bg-saffron px-5 py-3 font-display text-sm font-bold text-obsidian transition hover:bg-[#ffa94d]"
                  >
                    Create organiser account <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    to="/login"
                    className="inline-flex items-center rounded-xl border border-white/15 px-5 py-3 font-display text-sm font-semibold text-paper transition hover:border-saffron/50"
                  >
                    Sign in
                  </Link>
                </>
              )}
            </div>
          </div>

          <div className="flex flex-col justify-between rounded-3xl border border-electric/30 bg-gradient-to-b from-charcoal/80 to-obsidian p-8">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-electric/10 px-3 py-1 font-mono text-[11px] font-bold text-electric">
                <Vote className="h-3.5 w-3.5" />
                VOTER HUB
              </div>
              <h3 className="mt-4 font-display text-2xl font-bold text-paper">Cast your vote</h3>
              <div className="mt-6">
                <Steps steps={VOTER_STEPS} tone="electric" />
              </div>
            </div>
            <div className="mt-8">
              <Link
                to="/voter"
                className="inline-flex items-center gap-2 rounded-xl border border-electric/40 bg-electric/15 px-5 py-3 font-display text-sm font-bold text-electric transition hover:bg-electric/25"
              >
                Go to Voter Hub <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <HowItWorks />
    </div>
  )
}
