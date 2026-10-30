import { useState } from 'react'
import { api } from '../../services/api'
import type { ApiError, OtpChannel, OtpRequestResponse } from '../../types'
import { Button } from '../ui/Button'
import { ErrorMessage } from '../ui/ErrorMessage'
import { Field } from '../ui/Field'

interface Props {
  identifyToken: string
  channels: OtpChannel[]
  onDone: (info: OtpRequestResponse & { contact: string }) => void
}

export default function ContactStep({ identifyToken, channels, onDone }: Props) {
  const [channel, setChannel] = useState<OtpChannel>(channels[0])
  const [contact, setContact] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const value = contact.trim()
      const res = await api.requestOtp(identifyToken, channel, value)
      onDone({ ...res, contact: value })
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <h2 className="font-display text-xl font-bold text-paper">Verify it’s you</h2>
        <p className="mt-1 text-xs text-ash">
          Enter your registered {channels.length > 1 ? 'email or phone number' : channel === 'email' ? 'email' : 'phone number'}.
          We will send a one-time code to it.
        </p>
      </div>

      {channels.length > 1 && (
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-obsidian p-1">
          {channels.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => {
                setChannel(c)
                setContact('')
              }}
              className={`rounded-lg px-3 py-2 font-mono text-xs font-semibold transition ${
                channel === c ? 'bg-electric text-obsidian' : 'text-ash hover:text-paper'
              }`}
            >
              {c === 'email' ? 'Email' : 'Phone'}
            </button>
          ))}
        </div>
      )}

      {error && <ErrorMessage error={error} />}

      <Field
        label={channel === 'email' ? 'Email' : 'Phone number'}
        type={channel === 'email' ? 'email' : 'tel'}
        autoComplete={channel === 'email' ? 'email' : 'tel'}
        value={contact}
        onChange={(e) => setContact(e.target.value)}
        required
      />

      <Button type="submit" size="lg" className="w-full" isLoading={loading} loadingText="Sending code...">
        Send OTP
      </Button>
    </form>
  )
}
