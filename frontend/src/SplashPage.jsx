// SplashPage -- landing page for the website if you aren't signed in
import { useState } from 'react'
import { useAuth } from './useAuth'
import './SplashPage.css'

function SplashShot({ src, alt, variant = 'default' }) {
  const [ok, setOk] = useState(true)

  return (
    <figure className={`splash-shot splash-shot--${variant}`}>
      <div className={`splash-shot-frame ${!ok ? 'splash-shot-frame--empty' : ''}`}>
        {ok ? (
          <img
            src={src}
            alt={alt}
            className="splash-shot-img"
            onError={() => setOk(false)}
          />
        ) : null}
      </div>
    </figure>
  )
}

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
      <div className="splash splash-auth-page">
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
    <div className="splash splash-landing-page">
      <header className="splash-nav">
        <div className="splash-nav-inner">
          <div className="splash-nav-brand">
            <img src="/logo.svg" alt="" className="splash-nav-logo" />
            <span className="splash-nav-title">AceMarket</span>
          </div>
          <div className="splash-nav-actions">
            <button type="button" className="splash-nav-link" onClick={openSignIn}>
              Sign in
            </button>
            <button type="button" className="splash-nav-cta" onClick={openSignUp}>
              Create account
            </button>
          </div>
        </div>
      </header>

      <div className="splash-landing-inner">
        <section className="splash-hero" aria-labelledby="splash-hero-heading">
          <div className="splash-hero-split">
            <div className="splash-hero-copy">
              <p className="splash-hero-kicker">Paper trading · Backtests · Monte Carlo</p>
              <h1 id="splash-hero-heading">A full-stack workbench for strategy research</h1>
              <p className="splash-hero-tagline">
                Use real charts, a Python strategy IDE, variable risk settings, historical backtests, and Monte Carlo stress tests —
                all before you risk real capital.
              </p>
              <p className="splash-hero-lede">
                Paper trade U.S. equities with configurable slippage and commissions, iterate on strategies in code,
                and turn years of OHLC history into equity curves, trade logs, and distributions across thousands of
                synthetic paths.
              </p>
              <div className="splash-hero-pills">
                <span className="splash-pill">Python strategies</span>
                <span className="splash-pill">Multi-symbol backtests</span>
                <span className="splash-pill">Monte Carlo engine</span>
                <span className="splash-pill">Lookahead controls</span>
              </div>
              <div className="splash-hero-cta-inline">
                <button type="button" className="splash-btn splash-btn-primary" onClick={openSignUp}>
                  Get started
                </button>
                <button type="button" className="splash-btn splash-btn-ghost" onClick={openSignIn}>
                  I have an account
                </button>
              </div>
            </div>
            <div className="splash-hero-visual">
              <SplashShot variant="hero" src="/splash-chart.png" alt="AceMarket chart and watchlist" />
            </div>
          </div>
        </section>

        <section className="splash-showcase" aria-label="Workspace">
          <div className="splash-showcase-row">
            <div className="splash-showcase-copy">
              <h2 className="splash-showcase-label">Strategy IDE &amp; runs</h2>
              <p>
                Write Python strategies with the engine's own API, run multi-symbol backtests and Monte Carlo jobs in the
                background, and see engine and strategy errors in the console. Runs are saved and persist between sessions.
              </p>
            </div>
            <div className="splash-showcase-figure">
              <SplashShot src="/splash-strategies.png" alt="AceMarket strategy editor and runs" />
            </div>
          </div>
          <div className="splash-showcase-row splash-showcase-row--flip">
            <div className="splash-showcase-figure">
              <SplashShot src="/splash-report.png" alt="AceMarket report and equity curve" />
            </div>
            <div className="splash-showcase-copy">
              <h2 className="splash-showcase-label">Reports &amp; equity</h2>
              <p>
                Every run produces a trade history, P&amp;L, and equity curve you can line up with the chart. You can export the data to JSON for further analysis or porting your work to another platform.
              </p>
            </div>
          </div>
        </section>

        <section className="splash-panel splash-section" aria-labelledby="splash-tools-heading">
          <div className="splash-panel-head">
            <h2 id="splash-tools-heading" className="splash-section-title">Tools in the box</h2>
            <p className="splash-section-intro">

            </p>
          </div>
          <ul className="splash-tool-grid">
            <li className="splash-tool-card splash-tool-card-wide">
              <span className="splash-tool-card-num">01</span>
              <div className="splash-tool-card-body">
                <strong>Market data &amp; charts</strong>
                <span>
                  Decades of daily OHLC with batched loading. Toggle SMA, EMA, and RSI on a lightweight candlestick
                  engine built for clarity.
                </span>
              </div>
            </li>
            <li className="splash-tool-card splash-tool-card-paper">
              <span className="splash-tool-card-num">02</span>
              <div className="splash-tool-card-body">
                <strong>Paper trading &amp; portfolio</strong>
                <span>
                  Long and short, realistic fills, slippage, per-order and per-share fees, min trade size, reserves,
                  and risk caps.
                </span>
              </div>
            </li>
            <li className="splash-tool-card splash-tool-card-strategy">
              <span className="splash-tool-card-num">03</span>
              <div className="splash-tool-card-body">
                <strong>Strategy IDE &amp; sandbox</strong>
                <span>
                  Python classes against a curated API, whitelisted stdlib imports, optional lookahead blocking for
                  honest backtests.
                </span>
              </div>
            </li>
            <li className="splash-tool-card splash-tool-card-tall">
              <span className="splash-tool-card-num">04</span>
              <div className="splash-tool-card-body">
                <strong>Backtest &amp; Monte Carlo</strong>
                <span>
                  Multi-ticker historical runs and parallel Monte Carlo paths with synthetic price evolution — see
                  central tendency and tail risk, not a single lucky backtest. Background jobs keep long runs off the
                  request timeout so you can poll results while the engine works.
                  Jobs are multi-threaded for maximum speed.
                </span>
              </div>
            </li>
            <li className="splash-tool-card splash-tool-card-reports">
              <span className="splash-tool-card-num">05</span>
              <div className="splash-tool-card-body">
                <strong>Reports &amp; console</strong>
                <span>
                  Blotters, P&amp;L, equity curves, chart framing from runs — plus a console for strategy feedback.
                </span>
              </div>
            </li>
            <li className="splash-tool-card splash-tool-card-cloud">
              <span className="splash-tool-card-num">06</span>
              <div className="splash-tool-card-body">
                <strong>Cloud-native stack</strong>
                <span>
                  FastAPI + PostgreSQL for durable data; React + Vite; Firebase Auth &amp; Hosting — your workspace
                  persists.
                </span>
              </div>
            </li>
          </ul>
        </section>
      </div>
    </div>
  )
}
