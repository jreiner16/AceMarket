import { useState } from 'react'
import { useAuth } from './authContext'
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
          <p className="splash-hero-tagline">Paper trading and strategy backtesting</p>
        </div>

        <div className="splash-features">
          <div className="splash-features-title">What you can do</div>
          <ul className="splash-feature-list">
            <li>View real-time charts and candlesticks</li>
            <li>Paper trade with configurable slippage and commission</li>
            <li>Write and run Python strategy backtests</li>
            <li>Track portfolio performance (long and short)</li>
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
