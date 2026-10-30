import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { api } from '../../services/api'
import type { ApiError, IdentifyResponse, PublicElection } from '../../types'
import { Button } from '../ui/Button'
import { ErrorMessage } from '../ui/ErrorMessage'
import { Field } from '../ui/Field'

interface Props {
  election: PublicElection
  onDone: (res: IdentifyResponse) => void
}

export default function IdentifyStep({ election, onDone }: Props) {
  const cols = election.voterSchema.identityColumns
  const [name, setName] = useState('')
  const [rollNo, setRollNo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const identity: { name?: string; rollNo?: string } = {}
      if (cols.includes('name')) identity.name = name.trim()
      if (cols.includes('rollNo')) identity.rollNo = rollNo.trim()
      onDone(await api.identifyVoter(election.code, identity))
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <h2 className="font-display text-xl font-bold text-paper">Confirm your identity</h2>
        <p className="mt-1 text-xs text-ash">Enter your details exactly as registered by the organiser.</p>
      </div>
      {error && <ErrorMessage error={error} />}
      {cols.includes('name') && (
        <Field
          label="Full name"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      )}
      {cols.includes('rollNo') && (
        <Field
          label="Roll number"
          autoComplete="off"
          value={rollNo}
          onChange={(e) => setRollNo(e.target.value)}
          required
        />
      )}
      <Button type="submit" size="lg" className="w-full" isLoading={loading} loadingText="Checking...">
        Continue
        <ArrowRight className="h-4 w-4" />
      </Button>
    </form>
  )
}
