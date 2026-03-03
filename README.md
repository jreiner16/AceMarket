# AceMarket

A full-stack paper trading platform with a Python strategy IDE, backtester, and Monte Carlo simulator.

## Getting Started

```bash
cd backend && uvicorn api:app
cd frontend && npm run dev
```

Run backend and frontend in separate terminals.

## Documentation

- [Strategy Rules](docs/STRATEGY_RULES.md)
- [API Reference](docs/API.md)

## Deployment

Deploy frontend and backend separately. The frontend uses `VITE_API_BASE` at build time.

**Backend** — Deploy `backend/` (Docker or uvicorn). Set `CORS_ORIGINS`, `ENVIRONMENT=production`, `GOOGLE_APPLICATION_CREDENTIALS`, `ACEMARKET_DB`. See `backend/.env.example`.

**Frontend** — Build with `npm run build`. Set `VITE_API_BASE` and `VITE_FIREBASE_*`. See `frontend/.env.example`.

**Firebase** — Create project, enable auth, add frontend URL to Authorized domains, configuring the Admin SDK on backend.

## Limitations

This engine is an educational tool for strategy testing. It doesn't allow for intraday trading or trading of real shares. However, strategies implemented in this engine can be translated for real trading software.

## License

All Rights Reserved — see [LICENSE](LICENSE).
