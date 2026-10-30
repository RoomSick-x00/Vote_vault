import { useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Check, Copy, Download } from 'lucide-react'

interface ShareCardProps {
  code: string
  title: string
}

/** Join code + QR that voters use to reach the election from the Voter Hub. */
export default function ShareCard({ code, title }: ShareCardProps) {
  const [copied, setCopied] = useState<'code' | 'link' | null>(null)
  const qrRef = useRef<HTMLDivElement>(null)
  const link = `${window.location.origin}/vote/${code}`

  const copy = async (kind: 'code' | 'link') => {
    try {
      await navigator.clipboard.writeText(kind === 'code' ? code : link)
      setCopied(kind)
      setTimeout(() => setCopied(null), 1800)
    } catch {
      /* clipboard unavailable */
    }
  }

  const downloadQr = () => {
    const svg = qrRef.current?.querySelector('svg')
    if (!svg) return
    const xml = new XMLSerializer().serializeToString(svg)
    const img = new Image()
    img.onload = () => {
      const size = 1024
      const canvas = document.createElement('canvas')
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, size, size)
      ctx.drawImage(img, 0, 0, size, size)
      const a = document.createElement('a')
      a.href = canvas.toDataURL('image/png')
      a.download = `votevault-${code}.png`
      a.click()
    }
    img.src = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(xml)))}`
  }

  return (
    <div className="flex flex-col items-center gap-5 rounded-3xl border border-white/10 bg-charcoal/50 p-6 sm:flex-row">
      <div ref={qrRef} className="shrink-0 rounded-2xl bg-white p-3">
        <QRCodeSVG value={link} size={148} level="M" marginSize={0} title={`QR for ${title}`} />
      </div>

      <div className="w-full min-w-0 space-y-3 text-center sm:text-left">
        <div>
          <p className="font-mono text-[10px] tracking-wider text-ash">ELECTION CODE</p>
          <p className="mt-1 font-mono text-3xl font-bold tracking-[0.3em] text-saffron">{code}</p>
        </div>
        <p className="truncate font-mono text-[11px] text-ash" title={link}>
          {link}
        </p>
        <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
          <button
            type="button"
            onClick={() => copy('code')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-1.5 font-mono text-xs text-paper transition hover:border-saffron/60"
          >
            {copied === 'code' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            Copy code
          </button>
          <button
            type="button"
            onClick={() => copy('link')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-1.5 font-mono text-xs text-paper transition hover:border-saffron/60"
          >
            {copied === 'link' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            Copy link
          </button>
          <button
            type="button"
            onClick={downloadQr}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-1.5 font-mono text-xs text-paper transition hover:border-saffron/60"
          >
            <Download className="h-3.5 w-3.5" />
            Download QR
          </button>
        </div>
      </div>
    </div>
  )
}
