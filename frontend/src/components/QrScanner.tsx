import { useEffect, useRef, useState } from 'react'
import jsQR from 'jsqr'

interface QrScannerProps {
  onDetect: (text: string) => void
  onError?: (message: string) => void
}

/** Camera based QR scanner. Stops the camera as soon as a code is read or the component unmounts. */
export default function QrScanner({ onDetect, onError }: QrScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [starting, setStarting] = useState(true)

  useEffect(() => {
    let stream: MediaStream | null = null
    let raf = 0
    let stopped = false
    let last = 0

    const stop = () => {
      stopped = true
      cancelAnimationFrame(raf)
      stream?.getTracks().forEach((t) => t.stop())
    }

    const tick = (time: number) => {
      if (stopped) return
      const video = videoRef.current
      const canvas = canvasRef.current
      if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA && time - last > 100) {
        last = time
        const w = video.videoWidth
        const h = video.videoHeight
        if (w && h) {
          canvas.width = w
          canvas.height = h
          const ctx = canvas.getContext('2d', { willReadFrequently: true })
          if (ctx) {
            ctx.drawImage(video, 0, 0, w, h)
            const result = jsQR(ctx.getImageData(0, 0, w, h).data, w, h, { inversionAttempts: 'dontInvert' })
            if (result?.data) {
              stop()
              onDetect(result.data)
              return
            }
          }
        }
      }
      raf = requestAnimationFrame(tick)
    }

    const start = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        onError?.('Camera access needs a secure (HTTPS) connection. Enter the code instead.')
        setStarting(false)
        return
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        })
        if (stopped) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        const video = videoRef.current
        if (video) {
          video.srcObject = stream
          await video.play()
        }
        setStarting(false)
        raf = requestAnimationFrame(tick)
      } catch (err) {
        const denied = err instanceof DOMException && err.name === 'NotAllowedError'
        onError?.(
          denied
            ? 'Camera permission was denied. Allow camera access or enter the code instead.'
            : 'Could not start the camera. Enter the code instead.'
        )
        setStarting(false)
      }
    }

    start()
    return stop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-2xl border border-white/15 bg-black">
      <video ref={videoRef} playsInline muted className="h-full w-full object-cover" />
      <canvas ref={canvasRef} className="hidden" />
      <div className="pointer-events-none absolute inset-8 rounded-2xl border-2 border-saffron/70" />
      {starting && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70 font-mono text-xs text-ash">
          Starting camera...
        </div>
      )}
    </div>
  )
}
