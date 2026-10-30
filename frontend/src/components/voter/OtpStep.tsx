import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { ApiError, OtpChannel, VerifiedVoter } from '../../types'
import { Button } from '../ui/Button'
import { ErrorMessage } from '../ui/ErrorMessage'

interface Props {
  identifyToken: string
  channel: OtpChannel
  contact: string
  resendAfter: number
  onVerified: (v: VerifiedVoter) => void
  onChangeContact: () => void
}

function mask(contact: string, channel: OtpChannel) {
  if (channel === 'phone') return contact.length > 4 ? `••••${contact.slice(-4)}` : contact
  const [user, domain] = contact.split('@')
  return domain ? `${user.slice(0, 2)}•••@${domain}` : contact
}

export default function OtpStep({ identifyToken, channel, contact, resendAfter, onVerified, onChangeContact }: Props) {
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [cooldown, setCooldown] = useState(resendAfter)
  const [resending, setResending] = useState(false)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const verify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      onVerified(await api.verifyOtp(identifyToken, otp))
    } catch (err) {
      setError(err as ApiError)
      setOtp('')
    } finally {
      setLoading(false)
    }
  }

  const resend = async () => {
    setError(null)
    setResending(true)
    try {
      const res = await api.requestOtp(identifyToken, channel, contact)
      setCooldown(res.resendAfter)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setResending(false)
    }
  }

  return (
    <form onSubmit={verify} className="space-y-4">
      <div>
        <h2 className="font-display text-xl font-bold text-paper">Enter the OTP</h2>
        <p className="mt-1 text-xs text-ash">
          We sent a code to <span className="font-mono text-paper">{mask(contact, channel)}</span>.
        </p>
      </div>

      {error && <ErrorMessage error={error} />}

      <div>
        <label htmlFor="otp" className="block font-mono text-[11px] tracking-wide text-ash">
          ONE-TIME CODE
        </label>
        <input
          id="otp"
          value={otp}
          onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 8))}
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          placeholder="••••••"
          className="mt-1.5 w-full rounded-xl border border-white/15 bg-obsidian px-4 py-3 text-center font-mono text-2xl font-bold tracking-[0.5em] text-paper placeholder:text-ash/30 focus:border-electric focus:outline-none"
        />
      </div>

      <Button type="submit" size="lg" className="w-full" isLoading={loading} loadingText="Verifying..." disabled={otp.length < 4}>
        Verify & continue
      </Button>

      <div className="flex items-center justify-between text-xs">
        <button type="button" onClick={onChangeContact} className="text-ash transition hover:text-paper">
          Change {channel === 'email' ? 'email' : 'number'}
        </button>
        <button
          type="button"
          onClick={resend}
          disabled={cooldown > 0 || resending}
          className="text-electric transition hover:underline disabled:text-ash disabled:no-underline"
        >
          {cooldown > 0 ? `Resend in ${cooldown}s` : resending ? 'Sending...' : 'Resend code'}
        </button>
      </div>
    </form>
  )
}
