/**
 * Static, accessible fallback sculpture used when WebGL is unavailable
 * or during lazy loading. Matches the 3D core with faceted transmission glass,
 * lathe pedestal, floating particles, and ballot card.
 */
export default function BallotFallback({ showNote = false }: { showNote?: boolean }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center">
      <svg viewBox="0 0 560 500" className="h-auto w-full max-w-[480px]" aria-hidden="true">
        <defs>
          <linearGradient id="glassGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.18" />
            <stop offset="35%" stopColor="#FFD9A0" stopOpacity="0.08" />
            <stop offset="70%" stopColor="#0A0A0C" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.12" />
          </linearGradient>
          <linearGradient id="pedestalGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#121316" />
            <stop offset="40%" stopColor="#22242B" />
            <stop offset="70%" stopColor="#18191E" />
            <stop offset="100%" stopColor="#0D0E11" />
          </linearGradient>
        </defs>

        {/* Sculpted Pedestal Base */}
        <path
          d="M210 440 C 210 420, 225 390, 235 375 L 325 375 C 335 390, 350 420, 350 440 Z"
          fill="url(#pedestalGrad)"
        />
        {/* Waist amber emissive band */}
        <rect x="236" y="380" width="88" height="5" rx="2.5" fill="#FF9D00" opacity="0.85" />
        <ellipse cx="280" cy="382" rx="44" ry="4" fill="#FF9D00" opacity="0.4" />

        {/* Pedestal Top Chamfer Plate */}
        <ellipse cx="280" cy="370" rx="60" ry="12" fill="#1A1B20" stroke="rgba(233,201,130,0.3)" strokeWidth="1" />
        <ellipse cx="280" cy="365" rx="46" ry="6" fill="#FF9D00" opacity="0.6" />

        {/* Wordmark Plaque & Chevron */}
        <rect x="254" y="405" width="52" height="18" rx="2" fill="#0C0D10" stroke="rgba(233,201,130,0.4)" strokeWidth="0.8" />
        <path d="M274 412 L280 408 L286 412" fill="none" stroke="#FFD166" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <text x="280" y="419" textAnchor="middle" fill="#E9C982" fontSize="5" fontFamily="monospace" letterSpacing="1.2">VOTEVAULT</text>

        {/* Faceted Glass Chamber Body */}
        {/* Rear internal glow */}
        <rect x="210" y="150" width="140" height="205" rx="16" fill="rgba(255, 157, 0, 0.05)" />

        {/* Under-ballot light puck */}
        <ellipse cx="280" cy="345" rx="34" ry="8" fill="#FFB35C" opacity="0.75" />
        <ellipse cx="280" cy="345" rx="48" ry="12" fill="none" stroke="#FF9D00" strokeWidth="1" opacity="0.4" />

        {/* Sealed Ballot Card inside Chamber */}
        <g transform="rotate(-6 280 250)">
          <rect x="242" y="195" width="76" height="106" rx="4" fill="#F2F0EA" stroke="#DBD7C9" strokeWidth="1" />
          {/* Checkbox */}
          <rect x="264" y="210" width="32" height="32" rx="3" fill="none" stroke="#26262A" strokeWidth="1.4" />
          {/* Black checkmark */}
          <path d="M271 226 L278 233 L290 218" fill="none" stroke="#0B0B0D" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
          {/* Printed lines */}
          <line x1="252" y1="260" x2="304" y2="260" stroke="#D9D5C6" strokeWidth="1.6" strokeLinecap="round" />
          <line x1="256" y1="268" x2="298" y2="268" stroke="#DDD9CB" strokeWidth="1.6" strokeLinecap="round" />
          <line x1="252" y1="276" x2="284" y2="276" stroke="#DBD7C9" strokeWidth="1.6" strokeLinecap="round" />
          {/* Header accent */}
          <rect x="256" y="202" width="24" height="3.5" rx="1" fill="#C9A86A" />
        </g>

        {/* Glass Outer Wall & Chamfered Bevels */}
        <polygon
          points="220,150 340,150 360,175 360,330 340,355 220,355 200,330 200,175"
          fill="url(#glassGrad)"
          stroke="rgba(245, 245, 245, 0.4)"
          strokeWidth="1.4"
        />
        {/* Chamfer corner accent lines */}
        <line x1="220" y1="150" x2="220" y2="355" stroke="rgba(245,245,245,0.2)" strokeWidth="0.8" />
        <line x1="340" y1="150" x2="340" y2="355" stroke="rgba(245,245,245,0.2)" strokeWidth="0.8" />

        {/* Top Cap with Amber Insertion Slot */}
        <polygon
          points="225,142 335,142 345,152 215,152"
          fill="#1A1B20"
          stroke="rgba(233,201,130,0.5)"
          strokeWidth="1"
        />
        {/* Glowing Amber Slit */}
        <rect x="238" y="137" width="84" height="6" rx="3" fill="#FF9D00" />
        <rect x="240" y="138.5" width="80" height="3" rx="1.5" fill="#FFE29A" />
        <ellipse cx="280" cy="140" rx="46" ry="12" fill="#FF9D00" opacity="0.3" />

        {/* Floating Geometric Particles */}
        <polygon points="175,190 180,182 185,190 180,198" fill="#FFD166" opacity="0.7" />
        <polygon points="385,290 392,293 388,300" fill="#E9C982" opacity="0.6" />
        <polygon points="195,305 202,300 200,312" fill="#F5F5F5" opacity="0.5" />
        <circle cx="365" cy="170" r="2.2" fill="#FF9D00" opacity="0.8" />
        <polygon points="390,210 396,202 402,210 396,218" fill="#FFD166" opacity="0.6" />
      </svg>
    </div>
  )
}
