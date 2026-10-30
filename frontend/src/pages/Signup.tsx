import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { UserPlus } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'
import { Field } from '../components/ui/Field'
import { ErrorMessage } from '../components/ui/ErrorMessage'
import type { ApiError } from '../types'

export default function Signup() {
  const { user, register } = useAuth()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [organization, setOrganization] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  if (user) return <Navigate to="/organizer" replace />

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError({ error: 'VALIDATION_ERROR', message: 'Password must be at least 8 characters.' })
      return
    }
    if (password !== confirm) {
      setError({ error: 'VALIDATION_ERROR', message: 'Passwords do not match.' })
      return
    }
    setLoading(true)
    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
        organization: organization.trim() || undefined,
      })
      navigate('/organizer', { replace: true })
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
            <UserPlus className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-paper">Create organiser account</h1>
            <p className="text-xs text-ash">Required before you can create an election.</p>
          </div>
        </div>

        {error && <ErrorMessage error={error} className="mt-6" />}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Field label="Full name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required />
          <Field
            label="Institution / organisation"
            autoComplete="organization"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
            placeholder="e.g. College Student Council"
          />
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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint="At least 8 characters."
            required
          />
          <Field
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
          <Button type="submit" size="lg" isLoading={loading} loadingText="Creating account..." className="w-full">
            Create account
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-ash">
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-saffron hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
