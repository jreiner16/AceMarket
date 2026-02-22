# AceMarket — Paper Trading Platform

A full-stack paper trading platform with a TradingView-style frontend. Search stocks, view candlestick charts with technical indicators, open long/short positions, backtest custom strategies, and manage your portfolio.

## Quick Start

### 1. Environment setup

**Backend:** Create `backend/.env` with:
- `GOOGLE_APPLICATION_CREDENTIALS` — Path to Firebase service account JSON
- `ACEMARKET_DB` — SQLite path (default: acemarket.db)
- `CORS_ORIGINS` — Comma-separated frontend origins (default: localhost:5173)

**Frontend:** Create `frontend/.env` with your Firebase config (VITE_FIREBASE_API_KEY, VITE_FIREBASE_AUTH_DOMAIN, etc.).

### 2. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Start the API server

```bash
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Auth is bypassed by default when `GOOGLE_APPLICATION_CREDENTIALS` points to a missing file (e.g. the placeholder path). For production, set `ENVIRONMENT=production` and a valid Firebase service account path.

### 4. Start the frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Features

- **Stock search** — Search by symbol or company name (Yahoo Finance)
- **Candlestick charts** — TradingView Lightweight Charts with SMA overlay
- **Long/Short positions** — Open and close paper trades
- **Portfolio** — Track cash, positions, and P&L
- **Strategy backtesting** — Write Python strategies and backtest on historical data
- **Settings** — Configure initial cash, slippage, commission, risk limits

## Project Structure

```
AceMarket/
├── backend/
│   ├── api.py          # FastAPI server
│   ├── auth.py         # Firebase auth verification
│   ├── db.py           # SQLite persistence
│   ├── data_provider.py # Yahoo Finance market data
│   ├── stock.py        # Stock data & indicators
│   ├── portfolio.py    # Portfolio management
│   ├── backtest.py     # Strategy backtesting
│   ├── analytics.py    # Performance metrics
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── apiClient.js
│   │   ├── StockChart.jsx
│   │   ├── OrderPanel.jsx
│   │   ├── PortfolioPanel.jsx
│   │   └── SettingsModal.jsx
│   └── ...
├── Dockerfile
└── README.md
```

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
ENVIRONMENT=development DISABLE_AUTH=1 ACEMARKET_DB=:memory: pytest tests/ -v
```

## API Documentation

When the backend is running, see [http://localhost:8000/docs](http://localhost:8000/docs) for OpenAPI/Swagger documentation.

## Deployment

See `DEPLOYMENT.md` for Docker and production deployment instructions.

## License

MIT — see [LICENSE](LICENSE) for details.
