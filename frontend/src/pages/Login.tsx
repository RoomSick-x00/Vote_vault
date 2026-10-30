import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AlertTriangle, KeyRound } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'
import { Field } from '../components/ui/Field'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import type { ApiError } from '../types'

export default function Login() {
  const { user, login, sessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from || '/organizer'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  if (user) return <Navigate to={from} replace />

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-80px)] max-w-md flex-col justify-center px-4 py-12">
      <div className="rounded-3xl border border-white/10 bg-charcoal/70 p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-saffron/10 text-saffron">
            <KeyRound className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-paper">Organiser sign in</h1>
            <p className="text-xs text-ash">Manage your elections and voter lists.</p>
          </div>
        </div>

        {sessionExpired && (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-500/40 bg-amber-950/20 p-4 text-xs text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            Your session expired. Please sign in again.
          </div>
        )}

        {error && <ErrorMessage error={error} className="mt-6" />}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
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
          <Button type="submit" size="lg" isLoading={loading} loadingText="Signing in..." className="w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-ash">
          New organiser?{' '}
          <Link to="/signup" className="font-semibold text-saffron hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  )
}
