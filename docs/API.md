# API Reference

Base path: `/api/v1`

All endpoints except `/health` require `Authorization: Bearer <Firebase ID token>`.

## Health

- `GET /health` — Returns `{ status: "ok", service: "acemarket-api" }`

## Search

- `GET /search?q=<query>` — Search stocks via Yahoo Finance. Returns `[{ symbol, name, type }]`

## Stock Data

- `GET /stock/{symbol}?start_date=&end_date=&limit=5000` — OHLC candles with SMA, EMA, RSI
- `GET /stock/{symbol}/price` — Current (latest) price

## Watchlist

- `GET /watchlist` — Returns `{ watchlist: string[] }`
- `PUT /watchlist` — Body: `{ watchlist: string[] }` (max 30 symbols)

## Portfolio

- `GET /portfolio` — Full portfolio state (positions, trade_log, equity_curve, metrics)
- `POST /portfolio/position` — Open position. Body: `{ symbol, quantity, side: "long"|"short" }`
- `POST /portfolio/position/close` — Close position. Body: `{ symbol, quantity }`
- `POST /portfolio/clear` — Reset portfolio

## Settings

- `GET /settings` — User settings
- `PUT /settings` — Update. Body: partial settings (initial_cash, slippage, commission, etc.)

## Strategies

- `GET /strategies` — List user strategies
- `POST /strategies` — Create. Body: `{ name, code }`
- `PUT /strategies/{id}` — Update. Body: `{ name?, code? }`
- `DELETE /strategies/{id}` — Delete
- `POST /strategies/run` — Run backtest. Body: `{ strategy_id, symbols[], start_date, end_date, train_pct? }`
- `POST /strategies/montecarlo` — Monte Carlo simulation. Body: `{ strategy_id, symbol, n_sims?, horizon? }`. Samples from historical returns, runs strategy on synthetic paths. Returns percentiles, mean, prob. profitable.

## Runs

- `GET /runs` — List backtest runs (last 25)
- `GET /runs/{id}` — Get run details
- `DELETE /runs` — Clear all runs
