export default function LogoMark({ size = 28, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="16" cy="16" r="13.4" stroke="currentColor" strokeWidth="1.7" />
      <rect x="9.4" y="14.5" width="13.2" height="3" rx="1.5" fill="#FF9933" />
    </svg>
  )
}
