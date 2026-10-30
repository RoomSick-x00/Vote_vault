import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LogIn, LogOut, Menu, PlusCircle, Shield, Vote, X } from 'lucide-react'
import LogoMark from './LogoMark'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const inOrganizer = location.pathname.startsWith('/organizer')
  const inVoter = location.pathname.startsWith('/voter') || location.pathname.startsWith('/vote/')

  const link = (active: boolean, tone: 'saffron' | 'electric' | 'plain' = 'plain') =>
    `flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-mono text-xs font-medium transition ${
      active
        ? tone === 'saffron'
          ? 'bg-saffron/15 font-bold text-saffron'
          : tone === 'electric'
          ? 'bg-electric/15 font-bold text-electric'
          : 'bg-white/10 text-paper'
        : 'text-ash hover:bg-white/5 hover:text-paper'
    }`

  const handleLogout = async () => {
    setOpen(false)
    await logout()
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-obsidian/95 backdrop-blur-md">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8"
      >
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2.5 transition hover:opacity-90">
            <LogoMark size={26} className="text-paper" />
            <span className="font-display text-[15px] font-bold tracking-[0.2em]">
              <span className="text-paper">VOTE</span>
              <span className="text-saffron">VAULT</span>
            </span>
          </Link>

          <div className="hidden items-center gap-1 md:flex">
            <Link to="/" className={link(location.pathname === '/')}>
              Home
            </Link>
            <Link to="/organizer" className={link(inOrganizer, 'saffron')}>
              <Shield className="h-3.5 w-3.5" />
              Organiser
            </Link>
            <Link to="/voter" className={link(inVoter, 'electric')}>
              <Vote className="h-3.5 w-3.5" />
              Voter Hub
            </Link>
            {user && (
              <Link to="/organizer/create" className={link(location.pathname === '/organizer/create', 'saffron')}>
                <PlusCircle className="h-3.5 w-3.5" />
                New election
              </Link>
            )}
          </div>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          {user ? (
            <>
              <span className="max-w-[180px] truncate font-mono text-xs text-ash" title={user.email}>
                {user.full_name || user.email}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-1.5 rounded-full border border-white/15 px-3.5 py-1.5 font-mono text-xs text-paper transition hover:border-saffron/60 hover:text-saffron"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="font-mono text-xs text-ash transition hover:text-paper">
                Sign in
              </Link>
              <Link
                to="/signup"
                className="flex items-center gap-1.5 rounded-full bg-saffron px-4 py-2 font-display text-xs font-bold text-obsidian transition hover:bg-[#ffa94d]"
              >
                <LogIn className="h-3.5 w-3.5" />
                Organiser sign up
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-paper md:hidden"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {open && (
        <div className="space-y-1 border-t border-white/10 bg-obsidian px-4 pb-6 pt-3 md:hidden">
          {[
            { to: '/', label: 'Home' },
            { to: '/organizer', label: 'Organiser dashboard' },
            ...(user ? [{ to: '/organizer/create', label: 'Create election' }] : []),
            { to: '/voter', label: 'Voter Hub' },
          ].map((l) => (
            <Link
              key={l.to}
              to={l.to}
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2 text-sm font-medium text-paper hover:bg-white/5"
            >
              {l.label}
            </Link>
          ))}
          {user ? (
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-paper hover:bg-white/5"
            >
              <LogOut className="h-4 w-4 text-ash" />
              Sign out ({user.full_name || user.email})
            </button>
          ) : (
            <>
              <Link
                to="/login"
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2 text-sm font-medium text-paper hover:bg-white/5"
              >
                Sign in
              </Link>
              <Link
                to="/signup"
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2 text-sm font-bold text-saffron hover:bg-white/5"
              >
                Organiser sign up
              </Link>
            </>
          )}
        </div>
      )}
    </header>
  )
}
