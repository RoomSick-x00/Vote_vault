import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Keyboard, QrCode, Vote } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import QrScanner from '../components/QrScanner'
import { extractElectionCode } from '../lib/code'

export default function VoterHub() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'code' | 'scan'>('code')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  const join = (value: string) => {
    const clean = extractElectionCode(value)
    if (clean.length < 4) {
      setError('Enter a valid election code.')
      setMode('code')
      return
    }
    navigate(`/vote/${clean}`)
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-140px)] max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-3xl border border-white/10 bg-charcoal/70 p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-electric/10 text-electric">
            <Vote className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-paper">Voter Hub</h1>
            <p className="text-xs text-ash">Join an election with its code or QR.</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-1 rounded-xl bg-obsidian p-1">
          <button
            type="button"
            onClick={() => {
              setError(null)
              setMode('code')
            }}
            className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 font-mono text-xs font-semibold transition ${
              mode === 'code' ? 'bg-electric text-obsidian' : 'text-ash hover:text-paper'
            }`}
          >
            <Keyboard className="h-3.5 w-3.5" />
            Enter code
          </button>
          <button
            type="button"
            onClick={() => {
              setError(null)
              setMode('scan')
            }}
            className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 font-mono text-xs font-semibold transition ${
              mode === 'scan' ? 'bg-electric text-obsidian' : 'text-ash hover:text-paper'
            }`}
          >
            <QrCode className="h-3.5 w-3.5" />
            Scan QR
          </button>
        </div>

        {error && <ErrorMessage error={error} className="mt-5" />}

        {mode === 'code' ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              join(code)
            }}
            className="mt-6 space-y-4"
          >
            <div>
              <label htmlFor="election-code" className="block font-mono text-[11px] tracking-wide text-ash">
                ELECTION CODE
              </label>
              <input
                id="election-code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                maxLength={32}
                placeholder="e.g. K7M2QX"
                className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 text-center font-mono text-2xl font-bold tracking-[0.3em] text-paper placeholder:text-ash/30 focus:border-electric focus:outline-none"
              />
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={!code.trim()}>
              Continue
              <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        ) : (
          <div className="mt-6 space-y-3">
            <QrScanner onDetect={join} onError={setError} />
            <p className="text-center text-xs text-ash">Point your camera at the election QR code.</p>
          </div>
        )}
      </div>
    </div>
  )
}
