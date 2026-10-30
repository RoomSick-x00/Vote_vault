import { useState, useEffect } from 'react'
import VoteVaultCore from './votevault/VoteVaultCore'
import BallotFallback from './BallotFallback'
import ErrorBoundary from './ui/ErrorBoundary'

function checkWebGLSupport(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl')
    return Boolean(gl)
  } catch {
    return false
  }
}

export default function BallotBox3D() {
  const [supported, setSupported] = useState<boolean | null>(null)

  useEffect(() => {
    setSupported(checkWebGLSupport())
  }, [])

  if (supported === false) {
    return <BallotFallback showNote />
  }

  return (
    <ErrorBoundary fallback={<BallotFallback showNote />}>
      <VoteVaultCore />
    </ErrorBoundary>
  )
}
