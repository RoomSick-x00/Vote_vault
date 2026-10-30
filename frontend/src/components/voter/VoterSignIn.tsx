import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { api, getVoterToken } from '../../services/api'
import type { ApiError } from '../../types'
import { Button } from '../ui/Button'
import { ErrorMessage } from '../ui/ErrorMessage'
import { Field } from '../ui/Field'

/**
 * Inline voter sign-in (same Supabase accounts as organizers — the backend has a
 * single auth system). The voter token is kept per browser tab only.
 */
export default function VoterSignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  // Already signed in in this tab — nothing to do.
  if (getVoterToken()) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await api.voterLogin(email.trim(), password)
      onSignedIn()
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-electric/10 text-electric">
          <KeyRound className="h-4 w-4" />
        </div>
        <div>
          <h2 className="font-display text-base font-bold text-paper">Sign in to continue</h2>
          <p className="text-[11px] text-ash">Use your VoteVault account (same as organizers).</p>
        </div>
      </div>

      {error && <ErrorMessage error={error} />}

      <Field
        label="Email"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <Field
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <Button type="submit" className="w-full" isLoading={loading} loadingText="Signing in...">
        Sign in
      </Button>
      <p className="text-center font-mono text-[10px] text-ash/70">
        No account yet? The organizer must add you to the roster first — sign up from the home page, then share
        your user ID with them.
      </p>
    </form>
  )
}
