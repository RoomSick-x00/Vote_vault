import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { AuthProvider } from './context/AuthContext'
import Navbar from './components/Navbar'
import BackgroundFX from './components/BackgroundFX'
import LoadingScreen from './components/LoadingScreen'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ui/ErrorBoundary'
import Home from './pages/Home'
import Login from './pages/Login'
import Signup from './pages/Signup'
import OrganizerDashboard from './pages/OrganizerDashboard'
import CreateElection from './pages/CreateElection'
import ManageElection from './pages/ManageElection'
import VoterHub from './pages/VoterHub'
import VoterSession from './pages/VoterSession'
import ReceiptScreen from './pages/ReceiptScreen'
import ResultsAudit from './pages/ResultsAudit'
import { useUIStore } from './store/ui'

export default function App() {
  const appReady = useUIStore((s) => s.appReady)
  const setAppReady = useUIStore((s) => s.setAppReady)
  const { pathname } = useLocation()

  // The intro animation only plays on the landing page; voters arriving via QR go straight in.
  const showSplash = !appReady && pathname === '/'
  useEffect(() => {
    if (!appReady && pathname !== '/') setAppReady(true)
  }, [appReady, pathname, setAppReady])

  return (
    <AuthProvider>
      <div className="relative flex min-h-screen flex-col bg-obsidian font-sans text-paper selection:bg-saffron/20 selection:text-saffron">
        <AnimatePresence mode="wait">
          {showSplash && <LoadingScreen onComplete={() => setAppReady(true)} />}
        </AnimatePresence>

        <BackgroundFX />
        <Navbar />

        <main className="relative z-10 flex-1">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />

              <Route element={<ProtectedRoute />}>
                <Route path="/organizer" element={<OrganizerDashboard />} />
                <Route path="/organizer/create" element={<CreateElection />} />
                <Route path="/organizer/elections/:id" element={<ManageElection />} />
              </Route>

              <Route path="/voter" element={<VoterHub />} />
              <Route path="/vote/:code" element={<VoterSession />} />
              <Route path="/receipt/:receiptId" element={<ReceiptScreen />} />
              <Route path="/results/:id" element={<ResultsAudit />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ErrorBoundary>
        </main>

        <footer className="relative z-10 border-t border-white/10 bg-obsidian/80 py-5 text-center font-mono text-[11px] text-ash">
          © {new Date().getFullYear()} VoteVault · Secret ballots, verifiable results
        </footer>
      </div>
    </AuthProvider>
  )
}
