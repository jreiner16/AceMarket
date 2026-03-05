# AceMarket

A full-stack paper trading platform with a Python strategy IDE, backtester, and Monte Carlo simulator.

**Live:** [acemarketengine.web.app](https://acemarketengine.web.app)

## Getting Started

**Local dev** (frontend proxies `/api` to backend):

```bash
# Terminal 1 — backend (DISABLE_AUTH=1 for local without Firebase)
cd backend && DISABLE_AUTH=1 uvicorn api:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Then open http://localhost:5173. Copy `frontend/.env.example` to `frontend/.env` and fill in your Firebase config; for local dev leave `VITE_API_BASE` unset or set to `http://localhost:8000/api/v1` if the frontend is not proxying.

## Tests

```bash
# Backend (from project root)
cd backend && pip install -r requirements.txt -r requirements-dev.txt
DISABLE_AUTH=1 ACEMARKET_DB=:memory: pytest tests/ -v

# Frontend
cd frontend && npm ci && npm run lint && npm run test:run && npm run build
```

## Documentation

- [Strategy Rules](docs/STRATEGY_RULES.md)
- [API Reference](docs/API.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Security](docs/SECURITY.md)

## Deployment

Deploy frontend and backend separately. Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` → `frontend/.env` (or set env vars in your host); see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and [docs/SECURITY.md](docs/SECURITY.md).

**Backend** — Set `DATABASE_URL` (PostgreSQL in production), `CORS_ORIGINS`, `ENVIRONMENT=production`, and Firebase Admin credentials. Run with uvicorn or Docker.

**Frontend** — Set `VITE_API_BASE` and `VITE_FIREBASE_*` in `.env`, then `npm run build`. Deploy the `dist/` output (e.g. Firebase Hosting).

**Firebase** — Create a project, enable Auth, add your frontend URL to Authorized domains, and configure the Admin SDK on the backend. 

## Limitations

This engine is an educational tool for strategy testing. It doesn't allow for intraday trading or trading of real shares. However, strategies implemented in this engine can be translated for real trading software.

## License

All Rights Reserved — see [LICENSE](LICENSE).
