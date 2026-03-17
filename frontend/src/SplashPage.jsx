// SplashPage -- landing page for the website if you aren't signed in
import { useState } from 'react'
import { useAuth } from './useAuth'
import './SplashPage.css'

export function SplashPage() {
  const { signIn, signUp } = useAuth()
  const [showAuth, setShowAuth] = useState(false)
  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'signin') {
        await signIn(email, password)
      } else {
        await signUp(email, password)
      }
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const openSignIn = () => {
    setMode('signin')
    setError('')
    setShowAuth(true)
  }

  const openSignUp = () => {
    setMode('signup')
    setError('')
    setShowAuth(true)
  }

  const goBack = () => {
    setShowAuth(false)
    setError('')
    setEmail('')
    setPassword('')
  }

  if (showAuth) {
    return (
      <div className="splash">
        <div className="splash-card splash-auth">
          <button type="button" className="splash-back" onClick={goBack}>
            ← Back
          </button>
          <div className="splash-logo">
            <img src="/logo.svg" alt="AceMarket" />
            <h1>AceMarket</h1>
          </div>

          <div className="splash-tabs">
            <button
              type="button"
              className={mode === 'signin' ? 'active' : ''}
              onClick={() => { setMode('signin'); setError('') }}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === 'signup' ? 'active' : ''}
              onClick={() => { setMode('signup'); setError('') }}
            >
              Create account
            </button>
          </div>

          <form className="splash-form" onSubmit={handleSubmit}>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              minLength={6}
            />
            {error && <div className="splash-error">{error}</div>}
            <button type="submit" disabled={loading}>
              {loading ? '…' : mode === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="splash">
      <div className="splash-card splash-landing">
        <div className="splash-hero">
          <img src="/logo.svg" alt="" className="splash-hero-logo" />
          <h1>AceMarket</h1>
          <p className="splash-hero-tagline">Paper trade, test ideas, and stress‑test strategies before you risk a dollar.</p>
        </div>

        <div className="splash-features">
          <div className="splash-features-title">What you can do</div>
          <ul className="splash-feature-list">
            <li>Stream real‑time charts and candlesticks for U.S. stocks</li>
            <li>Paper trade with configurable slippage, commission, and position sizing</li>
            <li>Write Python strategies and run historical backtests in the browser IDE</li>
            <li>Generate Monte Carlo scenarios to see best, typical, and worst‑case equity curves</li>
            <li>Track portfolio P&amp;L and export results for further analysis</li>
          </ul>
        </div>

        <div className="splash-features">
          <div className="splash-features-title">Under the hood</div>
          <ul className="splash-feature-list">
            <li>Built with Python/FastAPI, React + Vite</li>
            <li>PostgreSQL on Render for persistent strategies, runs, and positions</li>
            <li>Firebase Auth and Firebase Hosting for secure, simple sign‑in</li>
          </ul>
        </div>

        <div className="splash-cta">
          <button type="button" className="splash-btn splash-btn-primary" onClick={openSignIn}>
            Sign in
          </button>
          <button type="button" className="splash-btn splash-btn-secondary" onClick={openSignUp}>
            Create account
          </button>
        </div>
      </div>
    </div>
  )
}
