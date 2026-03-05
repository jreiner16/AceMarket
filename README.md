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

Then open http://localhost:5173. **Make sure to set up a `.env.development`** so API calls go to localhost:8000 via the Vite proxy.

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

## Deployment

Deploy frontend and backend separately. The frontend uses `VITE_API_BASE` at build time.

**Backend** — Deploy `backend/` (Docker or uvicorn). **Set `DATABASE_URL` to a PostgreSQL connection string** (e.g. Render Postgres) — without it, SQLite is used and **all data is lost on restart**. Set `CORS_ORIGINS`, `ENVIRONMENT=production`, Firebase credentials. See `backend/.env.example` and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

**Frontend** — Build with `npm run build`. Set `VITE_API_BASE` and `VITE_FIREBASE_*`. See `frontend/.env.example`.

**Firebase** — Create project, enable auth, add frontend URL to Authorized domains, configuring the Admin SDK on backend.

**Render (API)** - Create project, connect to this project's GitHub repo, set up important key/value pairs like credentials, database URLs, etc. 

**Render (Data persistence)** - Create PostGreS database and connect it to your API project. 

When you commit and push any changes, make sure to wait for Render API to redeploy and (in ./frontend) npm run build to finish. Then run firebase deploy. 

## Limitations

This engine is an educational tool for strategy testing. It doesn't allow for intraday trading or trading of real shares. However, strategies implemented in this engine can be translated for real trading software.

## License

All Rights Reserved — see [LICENSE](LICENSE).
